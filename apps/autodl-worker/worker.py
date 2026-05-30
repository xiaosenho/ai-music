#!/usr/bin/env python3
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request


def read_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None and value != "" else default


def read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass
class WorkerConfig:
    control_plane_base_url: str = field(default_factory=lambda: read_env("AIMUSIC_CONTROL_PLANE_BASE_URL", "http://127.0.0.1:8092"))
    provider: str = field(default_factory=lambda: read_env("AIMUSIC_WORKER_PROVIDER", "autodl"))
    worker_version: str = field(default_factory=lambda: read_env("AIMUSIC_WORKER_VERSION", "autodl-worker-dev"))
    supported_job_types: List[str] = field(
        default_factory=lambda: [item.strip().upper() for item in read_env("AIMUSIC_WORKER_SUPPORTED_JOB_TYPES", "PROCESS,TRAIN,INFER").split(",") if item.strip()]
    )
    state_dir: Path = field(default_factory=lambda: Path(read_env("AIMUSIC_WORKER_STATE_DIR", "./.state")).resolve())
    runs_dir: Path = field(default_factory=lambda: Path(read_env("AIMUSIC_WORKER_RUNS_DIR", "./runs")).resolve())
    request_timeout_seconds: int = field(default_factory=lambda: read_int("AIMUSIC_WORKER_REQUEST_TIMEOUT_SECONDS", 30))
    idle_sleep_seconds: int = field(default_factory=lambda: read_int("AIMUSIC_WORKER_IDLE_SLEEP_SECONDS", 5))
    progress_interval_seconds: int = field(default_factory=lambda: read_int("AIMUSIC_WORKER_PROGRESS_INTERVAL_SECONDS", 10))
    mock_delay_seconds: int = field(default_factory=lambda: read_int("AIMUSIC_WORKER_MOCK_DELAY_SECONDS", 2))
    use_mock_executor: bool = field(default_factory=lambda: read_bool("AIMUSIC_WORKER_USE_MOCK_EXECUTOR", True))
    process_command: str = field(default_factory=lambda: read_env("AIMUSIC_PROCESS_COMMAND", ""))
    train_command: str = field(default_factory=lambda: read_env("AIMUSIC_TRAIN_COMMAND", ""))
    infer_command: str = field(default_factory=lambda: read_env("AIMUSIC_INFER_COMMAND", ""))
    hostname: str = field(default_factory=socket.gethostname)
    node_id: Optional[str] = field(default_factory=lambda: read_env("AIMUSIC_WORKER_NODE_ID", "").strip() or None)


class ControlPlaneClient:
    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base_url + path
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError("HTTP %s %s failed: %s" % (exc.code, path, detail))
        except error.URLError as exc:
            raise RuntimeError("Request to %s failed: %s" % (path, exc.reason))


class WorkerState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.status = "IDLE"
        self.running_job_id = None  # type: Optional[str]
        self.last_error = ""
        self.last_progress = 0

    def snapshot(self) -> Tuple[str, Optional[str], str, int]:
        with self._lock:
            return self.status, self.running_job_id, self.last_error, self.last_progress

    def set_idle(self) -> None:
        with self._lock:
            self.status = "IDLE"
            self.running_job_id = None
            self.last_progress = 0

    def set_busy(self, job_id: str) -> None:
        with self._lock:
            self.status = "BUSY"
            self.running_job_id = job_id
            self.last_error = ""
            self.last_progress = 0

    def set_progress(self, progress: int) -> None:
        with self._lock:
            self.last_progress = progress

    def set_error(self, message: str) -> None:
        with self._lock:
            self.last_error = message


class AutoDlWorker:
    def __init__(self, config: WorkerConfig) -> None:
        self.config = config
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self.config.runs_dir.mkdir(parents=True, exist_ok=True)
        self.client = ControlPlaneClient(config.control_plane_base_url, config.request_timeout_seconds)
        self.state = WorkerState()
        self.stop_event = threading.Event()
        self.node_id = self._resolve_node_id()
        self.heartbeat_interval_seconds = 30
        self.pull_interval_seconds = 10
        self.heartbeat_thread = None  # type: Optional[threading.Thread]

    def _resolve_node_id(self) -> str:
        if self.config.node_id:
            return self.config.node_id

        node_id_path = self.config.state_dir / "node_id"
        if node_id_path.exists():
            return node_id_path.read_text(encoding="utf-8").strip()

        node_id = str(uuid.uuid4())
        node_id_path.write_text(node_id, encoding="utf-8")
        return node_id

    def detect_gpu(self) -> Tuple[str, int, int]:
        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                check=True,
                text=True,
            )
        except Exception:
            return "", 0, 0

        rows = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if not rows:
            return "", 0, 0

        names = []
        total_vram = 0
        for row in rows:
            parts = [part.strip() for part in row.split(",")]
            if len(parts) >= 2:
                names.append(parts[0])
                try:
                    total_vram += int(parts[1])
                except ValueError:
                    pass
        primary_name = names[0] if names else ""
        return primary_name, len(rows), total_vram

    def register(self) -> None:
        gpu_name, gpu_count, vram_mb = self.detect_gpu()
        payload = {
            "nodeId": self.node_id,
            "nodeType": "AUTODL",
            "hostname": self.config.hostname,
            "provider": self.config.provider,
            "gpuName": gpu_name,
            "gpuCount": gpu_count,
            "vramMb": vram_mb,
            "supportedJobTypes": self.config.supported_job_types,
            "workerVersion": self.config.worker_version,
            "status": "IDLE",
        }
        response = self.client.post_json("/api/v1/workers/register", payload)
        self.node_id = response.get("nodeId", self.node_id)
        self.heartbeat_interval_seconds = int(response.get("heartbeatIntervalSeconds", self.heartbeat_interval_seconds))
        self.pull_interval_seconds = int(response.get("pullIntervalSeconds", self.pull_interval_seconds))
        (self.config.state_dir / "node_id").write_text(self.node_id, encoding="utf-8")
        print("[worker] registered node_id=%s heartbeat=%ss pull=%ss" % (
            self.node_id,
            self.heartbeat_interval_seconds,
            self.pull_interval_seconds,
        ))

    def start_heartbeat_loop(self) -> None:
        def heartbeat_loop() -> None:
            while not self.stop_event.is_set():
                status, running_job_id, last_error, last_progress = self.state.snapshot()
                payload = {
                    "workerVersion": self.config.worker_version,
                    "lastError": last_error or None,
                    "lastProgress": last_progress,
                }
                try:
                    self.client.post_json("/api/v1/workers/heartbeat", {
                        "nodeId": self.node_id,
                        "status": status,
                        "runningJobId": running_job_id,
                        "payload": payload,
                    })
                except Exception as exc:
                    print("[worker] heartbeat failed: %s" % exc, file=sys.stderr)
                self.stop_event.wait(self.heartbeat_interval_seconds)

        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, name="worker-heartbeat", daemon=True)
        self.heartbeat_thread.start()

    def pull_job(self) -> Optional[Dict[str, Any]]:
        response = self.client.post_json("/api/v1/jobs/pull", {
            "nodeId": self.node_id,
            "supportedJobTypes": self.config.supported_job_types,
        })
        if response.get("assigned"):
            return response.get("job")
        return None

    def report_status(
        self,
        job_id: str,
        status: str,
        progress_percent: Optional[int],
        message: str,
        error_message: Optional[str] = None,
        result_manifest: Optional[Dict[str, Any]] = None,
    ) -> None:
        if progress_percent is not None:
            self.state.set_progress(progress_percent)
        if error_message:
            self.state.set_error(error_message)
        self.client.post_json("/api/v1/jobs/%s/report" % job_id, {
            "nodeId": self.node_id,
            "status": status,
            "progressPercent": progress_percent,
            "message": message,
            "errorMessage": error_message,
            "resultManifest": result_manifest,
        })

    def build_run_context(self, job: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
        payload = parse_json_string(job.get("payload"))
        result_manifest = parse_json_string(job.get("resultManifest"))
        context = {
            "job": job,
            "payload": payload,
            "resultManifest": result_manifest,
            "nodeId": self.node_id,
            "runDir": str(run_dir),
        }
        write_json(run_dir / "context.json", context)
        write_json(run_dir / "payload.json", payload)
        return context

    def command_for_job(self, job_type: str) -> str:
        if job_type == "PROCESS":
            return self.config.process_command
        if job_type == "TRAIN":
            return self.config.train_command
        if job_type == "INFER":
            return self.config.infer_command
        return ""

    def execute_job(self, job: Dict[str, Any]) -> None:
        job_id = str(job["id"])
        job_type = str(job["jobType"]).upper()
        run_dir = self.config.runs_dir / job_id
        run_dir.mkdir(parents=True, exist_ok=True)

        self.state.set_busy(job_id)
        self.report_status(job_id, "RUNNING", 1, "Job started")
        context = self.build_run_context(job, run_dir)

        try:
            command = self.command_for_job(job_type)
            if command:
                result_manifest = self.run_external_command(job, context, run_dir, command)
            elif self.config.use_mock_executor:
                result_manifest = self.run_mock_executor(job, context, run_dir)
            else:
                raise RuntimeError("No command configured for job type %s" % job_type)

            self.report_status(job_id, "SUCCEEDED", 100, "Job finished", result_manifest=result_manifest)
            print("[worker] job %s finished successfully" % job_id)
        except Exception as exc:
            error_message = "%s\n%s" % (exc, traceback.format_exc(limit=3))
            self.state.set_error(str(exc))
            self.report_status(job_id, "FAILED", self.state.snapshot()[3], "Job failed", error_message=error_message)
            print("[worker] job %s failed: %s" % (job_id, exc), file=sys.stderr)
        finally:
            self.state.set_idle()

    def run_external_command(
        self,
        job: Dict[str, Any],
        context: Dict[str, Any],
        run_dir: Path,
        command_template: str,
    ) -> Dict[str, Any]:
        payload = context.get("payload", {})
        values = SafeDict({
            "job_id": job["id"],
            "job_type": job["jobType"],
            "run_dir": str(run_dir),
            "context_path": str(run_dir / "context.json"),
            "payload_path": str(run_dir / "payload.json"),
            "input_asset_ids": ",".join(job.get("inputAssetIds") or []),
            "dataset_version": job.get("datasetVersion") or "",
            "model_version": job.get("modelVersion") or "",
            "workflow": payload.get("workflow", ""),
        })
        command = command_template.format_map(values)
        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"

        with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
            process = subprocess.Popen(
                command,
                cwd=str(run_dir),
                env=self.build_subprocess_env(run_dir),
                shell=True,
                stdout=stdout_file,
                stderr=stderr_file,
            )
            last_report = 0.0
            last_progress = -1
            while process.poll() is None:
                if self.stop_event.is_set():
                    process.terminate()
                    raise RuntimeError("Worker is shutting down")
                now = time.time()
                if now - last_report >= self.config.progress_interval_seconds:
                    progress_data = load_json_if_exists(run_dir / "progress.json")
                    progress = normalize_progress(progress_data.get("progressPercent")) if progress_data else None
                    message = progress_data.get("message", "Job running") if progress_data else "Job running"
                    if progress is not None and progress != last_progress:
                        last_progress = progress
                        self.report_status(str(job["id"]), "RUNNING", progress, str(message))
                    last_report = now
                time.sleep(1)

            if process.returncode != 0:
                stderr_tail = tail_text(stderr_path)
                raise RuntimeError("Command exited with code %s: %s" % (process.returncode, stderr_tail))

        manifest = load_json_if_exists(run_dir / "result_manifest.json")
        return manifest or {}

    def run_mock_executor(self, job: Dict[str, Any], context: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
        payload = context.get("payload", {})
        job_type = str(job["jobType"]).upper()
        steps = [
            (15, "Preparing"),
            (45, "Running core pipeline"),
            (80, "Uploading outputs"),
        ]
        for progress, message in steps:
            if self.stop_event.is_set():
                raise RuntimeError("Worker is shutting down")
            write_json(run_dir / "progress.json", {"progressPercent": progress, "message": message})
            self.report_status(str(job["id"]), "RUNNING", progress, message)
            time.sleep(self.config.mock_delay_seconds)

        if job_type == "PROCESS":
            segment_count = max(len(job.get("inputAssetIds") or []) * 12, 12)
            manifest = {
                "workflow": payload.get("workflow", "asset-process"),
                "segmentCount": segment_count,
                "summary": "mock process complete",
            }
        elif job_type == "TRAIN":
            manifest = {
                "workflow": payload.get("workflow", "dataset-train"),
                "storagePath": "cos://models/%s/model.pth" % job["id"],
                "sampleAudioUrl": "https://example.invalid/previews/%s.wav" % job["id"],
                "metrics": {
                    "epochs": job.get("totalEpoch") or 300,
                    "sampleRate": job.get("sampleRate") or 40000,
                    "loss": 0.042,
                },
            }
        elif job_type == "INFER":
            output_path = run_dir / "output.wav"
            output_path.write_bytes(b"RIFFMOCKAUDIO")
            manifest = {
                "workflow": payload.get("workflow", "model-infer"),
                "outputObjectKey": "outputs/%s/output.wav" % job["id"],
                "outputUrl": str(output_path),
                "outputName": "infer-%s.wav" % job["id"],
            }
        else:
            manifest = {"summary": "mock job complete"}

        write_json(run_dir / "result_manifest.json", manifest)
        return manifest

    def build_subprocess_env(self, run_dir: Path) -> Dict[str, str]:
        env = os.environ.copy()
        env["AIMUSIC_WORKER_NODE_ID"] = self.node_id
        env["AIMUSIC_WORKER_RUN_DIR"] = str(run_dir)
        return env

    def run(self) -> int:
        self.register()
        self.start_heartbeat_loop()
        print("[worker] started, waiting for jobs")
        while not self.stop_event.is_set():
            try:
                job = self.pull_job()
                if not job:
                    self.stop_event.wait(self.pull_interval_seconds or self.config.idle_sleep_seconds)
                    continue
                print("[worker] received job %s (%s)" % (job["id"], job["jobType"]))
                self.execute_job(job)
            except Exception as exc:
                print("[worker] loop error: %s" % exc, file=sys.stderr)
                time.sleep(self.config.idle_sleep_seconds)
        return 0


class SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def normalize_progress(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return None


def parse_json_string(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def load_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def tail_text(path: Path, limit: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


def install_signal_handlers(worker: AutoDlWorker) -> None:
    def handle_signal(signum: int, frame: Any) -> None:
        print("[worker] received signal %s, shutting down" % signum)
        worker.stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)


def main() -> int:
    config = WorkerConfig()
    worker = AutoDlWorker(config)
    install_signal_handlers(worker)
    return worker.run()


if __name__ == "__main__":
    sys.exit(main())
