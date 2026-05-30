#!/usr/bin/env python3
import http.client
import json
import mimetypes
import os
import signal
import shutil
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
from urllib import parse
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
    worker_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
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
    use_mock_executor: bool = field(default_factory=lambda: read_bool("AIMUSIC_WORKER_USE_MOCK_EXECUTOR", False))
    prefetch_resources: bool = field(default_factory=lambda: read_bool("AIMUSIC_WORKER_PREFETCH_RESOURCES", True))
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

    def get_json(self, path: str) -> Dict[str, Any]:
        url = self.base_url + path
        req = request.Request(url, headers={"Accept": "application/json"}, method="GET")
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
        resources = self.prepare_job_resources(job, payload, run_dir)
        context = {
            "job": job,
            "payload": payload,
            "resultManifest": result_manifest,
            "resources": resources,
            "nodeId": self.node_id,
            "runDir": str(run_dir),
        }
        write_json(run_dir / "context.json", context)
        write_json(run_dir / "payload.json", payload)
        write_json(run_dir / "resources.json", resources)
        return context

    def prepare_job_resources(self, job: Dict[str, Any], payload: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
        resources = {
            "assets": [],
            "dataset": None,
            "model": None,
        }
        if not self.config.prefetch_resources:
            return resources

        job_type = str(job.get("jobType", "")).upper()
        asset_ids = list(job.get("inputAssetIds") or [])

        if job_type == "TRAIN":
            dataset_id = payload.get("datasetId")
            if dataset_id:
                dataset = self.fetch_dataset(str(dataset_id))
                resources["dataset"] = dataset
                asset_ids = list(dataset.get("assetIds") or [])

        if job_type == "INFER":
            model_version_id = payload.get("modelVersionId")
            if model_version_id:
                model = self.fetch_model(str(model_version_id))
                model_resources = dict(model)
                local_model_path = self.download_model_artifact(model, run_dir)
                if local_model_path:
                    model_resources["localPath"] = local_model_path
                resources["model"] = model_resources

        inputs_dir = run_dir / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        for asset_id in asset_ids:
            asset = self.fetch_asset(str(asset_id))
            asset_resource = dict(asset)
            local_path = self.download_asset(asset, inputs_dir)
            if local_path:
                asset_resource["localPath"] = local_path
            resources["assets"].append(asset_resource)

        return resources

    def fetch_asset(self, asset_id: str) -> Dict[str, Any]:
        return self.client.get_json("/api/v1/assets/%s" % asset_id)

    def fetch_dataset(self, dataset_id: str) -> Dict[str, Any]:
        return self.client.get_json("/api/v1/datasets/%s" % dataset_id)

    def fetch_model(self, model_version_id: str) -> Dict[str, Any]:
        return self.client.get_json("/api/v1/models/%s" % model_version_id)

    def download_asset(self, asset: Dict[str, Any], target_dir: Path) -> Optional[str]:
        source_url = None
        object_key = asset.get("objectKey")
        if object_key:
            ticket = self.client.post_json("/api/v1/assets/%s/download-ticket" % asset["id"], {})
            source_url = ticket.get("downloadUrl")
        elif asset.get("sourceUri"):
            source_url = asset.get("sourceUri")

        if not source_url:
            return None

        target_path = target_dir / build_file_name(asset.get("name"), asset.get("sourceUri"), object_key)
        download_file(source_url, target_path, self.config.request_timeout_seconds)
        return str(target_path)

    def download_model_artifact(self, model: Dict[str, Any], run_dir: Path) -> Optional[str]:
        storage_path = model.get("storagePath")
        if not storage_path:
            return None

        ticket = self.client.post_json("/api/v1/models/%s/download-ticket" % model["id"], {})
        download_url = ticket.get("downloadUrl")
        if not download_url:
            return None

        model_dir = run_dir / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        target_path = model_dir / build_file_name(model.get("name"), storage_path, ticket.get("objectKey"))
        download_file(download_url, target_path, self.config.request_timeout_seconds)
        return str(target_path)

    def prepare_storage_upload(self, file_name: str, category: str) -> Dict[str, Any]:
        return self.client.post_json("/api/v1/storage/upload-prepare", {
            "fileName": file_name,
            "category": category,
        })

    def upload_file_to_cos(self, local_path: Path, ticket: Dict[str, Any]) -> None:
        content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        parsed = parse.urlparse(ticket["uploadUrl"])
        connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_class(parsed.netloc, timeout=max(self.config.request_timeout_seconds, 300))
        request_path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(local_path.stat().st_size),
            **(ticket.get("headers") or {}),
        }

        try:
            connection.putrequest("PUT", request_path)
            for key, value in headers.items():
                connection.putheader(key, value)
            connection.endheaders()
            with local_path.open("rb") as file_handle:
                while True:
                    chunk = file_handle.read(1024 * 1024)
                    if not chunk:
                        break
                    connection.send(chunk)
            response = connection.getresponse()
            body = response.read().decode("utf-8", errors="replace")
            if response.status >= 400:
                raise RuntimeError("COS upload failed for %s: %s" % (local_path, body or response.reason))
        finally:
            connection.close()

    def finalize_result_manifest(self, job: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
        finalized = dict(manifest or {})
        job_type = str(job.get("jobType", "")).upper()

        if job_type == "PROCESS":
            local_processed_files = finalized.pop("localProcessedFiles", None)
            if isinstance(local_processed_files, list):
                processed_assets = []
                for entry in local_processed_files:
                    if not isinstance(entry, dict):
                        continue
                    local_path = entry.get("localPath")
                    if not isinstance(local_path, str) or not local_path.strip():
                        continue

                    file_path = Path(local_path)
                    ticket = self.prepare_storage_upload(str(entry.get("fileName") or file_path.name), "processed")
                    self.upload_file_to_cos(file_path, ticket)
                    processed_assets.append({
                        "name": str(entry.get("fileName") or file_path.name),
                        "assetType": str(entry.get("assetType") or "AUDIO"),
                        "objectKey": ticket["objectKey"],
                        "sourceUri": ticket["publicUrl"],
                        "durationSeconds": entry.get("durationSeconds"),
                        "language": entry.get("language"),
                        "note": entry.get("note"),
                        "metadata": entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {},
                    })

                if processed_assets:
                    finalized["processedAssets"] = processed_assets
                    finalized["segmentCount"] = finalized.get("segmentCount") or len(processed_assets)

        if job_type == "TRAIN":
            local_model_path = pop_string(finalized, "localModelPath")
            if local_model_path:
                model_file = Path(local_model_path)
                ticket = self.prepare_storage_upload(model_file.name, "models")
                self.upload_file_to_cos(model_file, ticket)
                finalized["storagePath"] = "cos://%s" % ticket["objectKey"]
                finalized["storageObjectKey"] = ticket["objectKey"]

            local_sample_audio_path = pop_string(finalized, "localSampleAudioPath")
            if local_sample_audio_path:
                preview_file = Path(local_sample_audio_path)
                ticket = self.prepare_storage_upload(preview_file.name, "previews")
                self.upload_file_to_cos(preview_file, ticket)
                finalized["sampleAudioUrl"] = ticket["publicUrl"]
                finalized["sampleAudioObjectKey"] = ticket["objectKey"]

        if job_type == "INFER":
            local_output_path = pop_string(finalized, "localOutputPath")
            if local_output_path:
                output_file = Path(local_output_path)
                ticket = self.prepare_storage_upload(output_file.name, "outputs")
                self.upload_file_to_cos(output_file, ticket)
                finalized["outputObjectKey"] = ticket["objectKey"]
                finalized["outputUrl"] = ticket["publicUrl"]
                finalized["outputName"] = finalized.get("outputName") or output_file.name

        return finalized

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

            result_manifest = self.finalize_result_manifest(job, result_manifest)
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
            "worker_dir": str(self.config.worker_dir),
            "run_dir": str(run_dir),
            "context_path": str(run_dir / "context.json"),
            "payload_path": str(run_dir / "payload.json"),
            "resources_path": str(run_dir / "resources.json"),
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
                cwd=str(self.config.worker_dir),
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
            model_path = run_dir / "mock-model.pth"
            sample_audio_path = run_dir / "mock-preview.wav"
            model_path.write_bytes(b"MOCKMODEL")
            sample_audio_path.write_bytes(b"RIFFMOCKPREVIEW")
            manifest = {
                "workflow": payload.get("workflow", "dataset-train"),
                "localModelPath": str(model_path),
                "localSampleAudioPath": str(sample_audio_path),
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
                "localOutputPath": str(output_path),
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
        mode = "MOCK" if self.config.use_mock_executor else "REAL"
        print("[worker] started in %s mode, waiting for jobs" % mode)
        if self.config.use_mock_executor:
            print(
                "[worker] warning: mock executor is enabled, TRAIN jobs will generate mock-model.pth instead of real RVC weights",
                file=sys.stderr,
            )
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


def download_file(url: str, target_path: Path, timeout_seconds: int) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with request.urlopen(url, timeout=max(timeout_seconds, 300)) as response, target_path.open("wb") as output:
        shutil.copyfileobj(response, output)


def build_file_name(name: Any, reference: Any, object_key: Any) -> str:
    base_name = sanitize_file_name(str(name) if name else "resource")
    suffix = detect_suffix(reference, object_key)
    if suffix and not base_name.lower().endswith(suffix.lower()):
        return base_name + suffix
    return base_name


def detect_suffix(reference: Any, object_key: Any) -> str:
    candidates = [reference, object_key]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            parsed = parse.urlparse(candidate)
            path = parsed.path if parsed.path else candidate
            suffix = Path(path).suffix
            if suffix:
                return suffix
    return ""


def sanitize_file_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in value.strip())
    return cleaned or "resource"


def pop_string(payload: Dict[str, Any], key: str) -> Optional[str]:
    value = payload.pop(key, None)
    if isinstance(value, str) and value.strip():
        return value
    return None


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
