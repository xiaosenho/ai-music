#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence


def read_env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None and value != "" else default


def read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass
class InferConfig:
    workspace_dir_name: str = read_env("AIMUSIC_INFER_WORKSPACE_DIR_NAME", "infer-workspace")
    model_dir_name: str = read_env("AIMUSIC_INFER_MODEL_DIR_NAME", "model")
    inputs_dir_name: str = read_env("AIMUSIC_INFER_INPUTS_DIR_NAME", "inputs")
    output_dir_name: str = read_env("AIMUSIC_INFER_OUTPUT_DIR_NAME", "infer-output")
    input_stage_mode: str = read_env("AIMUSIC_INFER_INPUT_STAGE_MODE", "symlink").strip().lower()
    command_template: str = read_env("AIMUSIC_RVC_INFER_COMMAND", "")
    infer_mode: str = read_env("AIMUSIC_RVC_INFER_MODE", "webui_auto").strip().lower()
    output_glob: str = read_env("AIMUSIC_INFER_OUTPUT_GLOB", "*.wav")
    bundle_extract_dir_name: str = read_env("AIMUSIC_INFER_BUNDLE_EXTRACT_DIR_NAME", "bundle")
    keep_workspace: bool = read_bool("AIMUSIC_INFER_KEEP_WORKSPACE", False)
    rvc_root_dir: str = read_env("AIMUSIC_RVC_ROOT_DIR", "/Retrieval-based-Voice-Conversion-WebUI")
    rvc_python_bin: str = read_env("AIMUSIC_RVC_PYTHON_BIN", "python3")
    rvc_device: str = read_env("AIMUSIC_RVC_DEVICE", "cuda:0")
    rvc_index_rate: float = read_float("AIMUSIC_RVC_INDEX_RATE", 0.66)
    rvc_filter_radius: int = int(read_float("AIMUSIC_RVC_FILTER_RADIUS", 3))
    rvc_resample_sr: int = int(read_float("AIMUSIC_RVC_RESAMPLE_SR", 0))
    rvc_rms_mix_rate: float = read_float("AIMUSIC_RVC_RMS_MIX_RATE", 1.0)
    rvc_protect: float = read_float("AIMUSIC_RVC_PROTECT", 0.33)
    rvc_f0_up_key: int = int(read_float("AIMUSIC_RVC_F0_UP_KEY", 0))
    rvc_is_half: bool = read_bool("AIMUSIC_RVC_IS_HALF", True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and run a real inference pipeline")
    parser.add_argument("--context", required=True, help="Path to worker context.json")
    parser.add_argument("--run-dir", required=True, help="Worker job run directory")
    args = parser.parse_args()

    context = load_json(Path(args.context))
    run_dir = Path(args.run_dir).resolve()
    config = InferConfig()

    payload = context.get("payload") or {}
    resources = context.get("resources", {})
    model = resources.get("model") or {}
    assets = resources.get("assets") or []
    job = context.get("job", {})

    if not model:
        raise RuntimeError("No model resource found for infer job")
    if not assets:
        raise RuntimeError("No input assets found for infer job")

    workspace_dir = run_dir / config.workspace_dir_name
    model_dir = workspace_dir / config.model_dir_name
    inputs_dir = workspace_dir / config.inputs_dir_name
    output_dir = workspace_dir / config.output_dir_name
    manifests_dir = workspace_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    update_progress(run_dir, 5, "Preparing model artifacts")
    resolved_model = resolve_model_artifacts(model, model_dir, config)

    update_progress(run_dir, 18, "Preparing input audio")
    staged_inputs = stage_input_assets(assets, inputs_dir, config.input_stage_mode)
    if not staged_inputs:
        raise RuntimeError("No staged input audio available for inference")

    primary_input = staged_inputs[0]
    expected_output_path = output_dir / build_output_name(primary_input["name"], model.get("name"))

    infer_parameters = {
        "modelId": model.get("id"),
        "modelName": model.get("name"),
        "inputCount": len(staged_inputs),
        "executionMode": job.get("executionMode"),
        "sampleRate": job.get("sampleRate"),
        "speakerId": parse_string(job.get("speakerId"), "0"),
        "f0Method": normalize_f0_method(job.get("f0Method") or "rmvpe"),
        "f0UpKey": parse_int(payload.get("f0UpKey"), config.rvc_f0_up_key),
        "indexRate": parse_float_value(payload.get("indexRate"), config.rvc_index_rate),
        "filterRadius": parse_int(payload.get("filterRadius"), config.rvc_filter_radius),
        "resampleSr": parse_int(payload.get("resampleSr"), config.rvc_resample_sr),
        "rmsMixRate": parse_float_value(payload.get("rmsMixRate"), config.rvc_rms_mix_rate),
        "protect": parse_float_value(payload.get("protect"), config.rvc_protect),
    }
    write_json(manifests_dir / "infer_config.json", {
        "model": model,
        "resolvedModel": resolved_model,
        "inputs": staged_inputs,
        "parameters": infer_parameters,
    })

    if config.command_template.strip():
        command = build_infer_command(
            config.command_template,
            run_dir=run_dir,
            workspace_dir=workspace_dir,
            model_bundle_path=Path(str(model.get("localPath"))).resolve(),
            model_dir=model_dir,
            output_dir=output_dir,
            context_path=Path(args.context).resolve(),
            infer_config_path=manifests_dir / "infer_config.json",
            resolved_model=resolved_model,
            primary_input=primary_input,
            expected_output_path=expected_output_path,
            parameters=infer_parameters,
        )
        update_progress(run_dir, 30, "Launching RVC inference")
        execute_shell_command(command, run_dir, "infer", run_dir)
    else:
        if config.infer_mode not in {"infer_cli_auto", "webui_auto"}:
            raise RuntimeError("AIMUSIC_RVC_INFER_COMMAND is not configured and AIMUSIC_RVC_INFER_MODE is not supported")
        update_progress(run_dir, 30, "Launching RVC inference")
        execute_webui_auto_infer(
            run_dir=run_dir,
            config=config,
            resolved_model=resolved_model,
            primary_input=primary_input,
            expected_output_path=expected_output_path,
            parameters=infer_parameters,
        )

    update_progress(run_dir, 88, "Collecting inference output")
    output_file = expected_output_path if expected_output_path.exists() else pick_latest(output_dir, config.output_glob)
    if output_file is None:
        raise RuntimeError(f"No inference output found under {output_dir} matching {config.output_glob}")

    result_manifest = {
        "localOutputPath": str(output_file),
        "outputName": output_file.name,
        "metrics": {
            "mode": "webui_auto" if not config.command_template.strip() else "custom-command",
            "inputCount": len(staged_inputs),
            "primaryInputName": primary_input["name"],
            "modelName": model.get("name"),
            "speakerId": infer_parameters["speakerId"],
            "f0Method": infer_parameters["f0Method"],
            "f0UpKey": infer_parameters["f0UpKey"],
            "indexRate": infer_parameters["indexRate"],
            "filterRadius": infer_parameters["filterRadius"],
            "resampleSr": infer_parameters["resampleSr"],
            "rmsMixRate": infer_parameters["rmsMixRate"],
            "protect": infer_parameters["protect"],
        },
    }
    write_json(run_dir / "result_manifest.json", result_manifest)
    update_progress(run_dir, 100, "Inference finished")

    if not config.keep_workspace:
        shutil.rmtree(workspace_dir, ignore_errors=True)

    return 0


def execute_webui_auto_infer(
    run_dir: Path,
    config: InferConfig,
    resolved_model: Dict[str, str],
    primary_input: Dict[str, str],
    expected_output_path: Path,
    parameters: Dict[str, object],
) -> None:
    rvc_root = resolve_rvc_root(Path(config.rvc_root_dir))
    layout = detect_webui_layout(rvc_root)
    env = build_rvc_env(rvc_root, layout)
    if layout == "nested":
        infer_cli = rvc_root / "tools" / "infer_cli.py"
        if not infer_cli.exists():
            raise RuntimeError(f"RVC infer_cli.py not found under {infer_cli}")
        weight_root = Path(env["weight_root"])
        weight_root.mkdir(parents=True, exist_ok=True)

        source_model_path = Path(resolved_model["modelPath"]).resolve()
        staged_model_name = f"aimusic-{run_dir.name}-{source_model_path.name}"
        staged_model_path = weight_root / staged_model_name
        shutil.copy2(source_model_path, staged_model_path)
        try:
            command: List[str] = [
                config.rvc_python_bin,
                str(infer_cli),
                "--f0up_key",
                str(parameters["f0UpKey"]),
                "--input_path",
                str(primary_input["stagedPath"]),
                "--index_path",
                resolved_model.get("indexPath", ""),
                "--f0method",
                str(parameters["f0Method"]),
                "--opt_path",
                str(expected_output_path),
                "--model_name",
                staged_model_name,
                "--index_rate",
                str(parameters["indexRate"]),
                "--device",
                config.rvc_device,
                "--filter_radius",
                str(parameters["filterRadius"]),
                "--resample_sr",
                str(parameters["resampleSr"]),
                "--rms_mix_rate",
                str(parameters["rmsMixRate"]),
                "--protect",
                str(parameters["protect"]),
            ]
            run_logged_command(
                name="infer-cli",
                command=command,
                run_dir=run_dir,
                cwd=rvc_root,
                env=env,
            )
        finally:
            if staged_model_path.exists():
                staged_model_path.unlink()
    else:
        script_path = run_dir / "flat_webui_infer.py"
        script_path.write_text(FLAT_INFER_SCRIPT_SOURCE, encoding="utf-8")
        command = [
            config.rvc_python_bin,
            str(script_path),
            str(rvc_root),
            resolved_model["modelPath"],
            primary_input["stagedPath"],
            str(expected_output_path),
            resolved_model.get("indexPath", ""),
            str(parameters.get("speakerId") or 0),
            str(parameters["f0UpKey"]),
            str(parameters["f0Method"]),
            str(parameters["indexRate"]),
            str(parameters["filterRadius"]),
            str(parameters["resampleSr"]),
            str(parameters["rmsMixRate"]),
            str(parameters["protect"]),
            config.rvc_device,
            "1" if config.rvc_is_half else "0",
        ]
        run_logged_command(
            name="infer-flat-webui",
            command=command,
            run_dir=run_dir,
            cwd=rvc_root,
            env=env,
        )


def resolve_model_artifacts(model: Dict[str, object], model_dir: Path, config: InferConfig) -> Dict[str, str]:
    local_path = model.get("localPath")
    if not isinstance(local_path, str) or not local_path.strip():
        raise RuntimeError("Model resource missing localPath")

    bundle_path = Path(local_path)
    if not bundle_path.exists():
        raise RuntimeError(f"Local model artifact does not exist: {bundle_path}")

    search_dir = model_dir
    if bundle_path.suffix.lower() == ".zip":
        extract_dir = model_dir / config.bundle_extract_dir_name
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle_path, "r") as archive:
            archive.extractall(extract_dir)
        search_dir = extract_dir
    else:
        copied = model_dir / bundle_path.name
        if copied.resolve() != bundle_path.resolve():
            shutil.copy2(bundle_path, copied)
        search_dir = model_dir

    model_file = pick_latest(search_dir, "*.pth")
    if model_file is None:
        raise RuntimeError(f"No .pth model file found under {search_dir}")
    index_file = pick_latest(search_dir, "*.index")

    return {
        "bundlePath": str(bundle_path),
        "searchDir": str(search_dir),
        "modelPath": str(model_file),
        "indexPath": str(index_file) if index_file else "",
    }


def stage_input_assets(assets: Sequence[Dict[str, object]], inputs_dir: Path, mode: str) -> List[Dict[str, str]]:
    staged: List[Dict[str, str]] = []
    for index, asset in enumerate(assets, start=1):
        local_path = asset.get("localPath")
        if not isinstance(local_path, str) or not local_path.strip():
            continue
        source = Path(local_path)
        suffix = source.suffix or ".wav"
        target = inputs_dir / f"{index:03d}{suffix}"
        if target.exists():
            target.unlink()

        if mode == "copy":
            shutil.copy2(source, target)
        else:
            os.symlink(source, target)

        staged.append({
            "assetId": str(asset.get("id") or ""),
            "name": str(asset.get("name") or source.name),
            "sourcePath": str(source),
            "stagedPath": str(target),
        })
    return staged


def build_output_name(input_name: str, model_name: object) -> str:
    input_stem = Path(input_name).stem or "input"
    model_stem = str(model_name or "model").replace(" ", "_")
    return f"{input_stem}-{model_stem}.wav"


def build_infer_command(
    template: str,
    run_dir: Path,
    workspace_dir: Path,
    model_bundle_path: Path,
    model_dir: Path,
    output_dir: Path,
    context_path: Path,
    infer_config_path: Path,
    resolved_model: Dict[str, str],
    primary_input: Dict[str, str],
    expected_output_path: Path,
    parameters: Dict[str, object],
) -> str:
    values = SafeDict({
        "run_dir": str(run_dir),
        "workspace_dir": str(workspace_dir),
        "model_bundle_path": str(model_bundle_path),
        "model_dir": str(model_dir),
        "model_path": resolved_model["modelPath"],
        "index_path": resolved_model.get("indexPath", ""),
        "input_dir": str(Path(primary_input["stagedPath"]).parent),
        "input_path": primary_input["stagedPath"],
        "output_dir": str(output_dir),
        "output_path": str(expected_output_path),
        "context_path": str(context_path),
        "infer_config_path": str(infer_config_path),
        "speaker_id": parameters.get("speakerId") or "",
        "f0_method": parameters.get("f0Method") or "",
        "sample_rate": parameters.get("sampleRate") or "",
        "model_name": parameters.get("modelName") or "",
        "f0_up_key": parameters.get("f0UpKey") or "",
        "index_rate": parameters.get("indexRate") or "",
        "filter_radius": parameters.get("filterRadius") or "",
        "resample_sr": parameters.get("resampleSr") or "",
        "rms_mix_rate": parameters.get("rmsMixRate") or "",
        "protect": parameters.get("protect") or "",
    })
    return template.format_map(values)


def execute_shell_command(command: str, run_dir: Path, name: str, cwd: Path) -> None:
    stdout_path = run_dir / f"{name}-stdout.log"
    stderr_path = run_dir / f"{name}-stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            shell=True,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
        )
        while process.poll() is None:
            time.sleep(15)
        if process.returncode != 0:
            raise RuntimeError(
                f"{name} command failed with code {process.returncode}: {tail_text(stderr_path)}"
            )


def run_logged_command(
    name: str,
    command: Sequence[str],
    run_dir: Path,
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
) -> None:
    stdout_path = run_dir / f"{name}-stdout.log"
    stderr_path = run_dir / f"{name}-stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            [str(item) for item in command],
            cwd=str(cwd),
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
        )
        phase_progress = [45, 62, 78]
        next_phase = 0
        while process.poll() is None:
            if next_phase < len(phase_progress):
                update_progress(run_dir, phase_progress[next_phase], f"Running {name}")
                next_phase += 1
            time.sleep(15)
        if process.returncode != 0:
            raise RuntimeError(
                f"{name} command failed with code {process.returncode}: {tail_text(stderr_path)}"
            )


def detect_webui_layout(rvc_root: Path) -> str:
    flat_markers = [
        rvc_root / "trainset_preprocess_pipeline_print.py",
        rvc_root / "train_nsf_sim_cache_sid_load_pretrain.py",
        rvc_root / "extract_feature_print.py",
    ]
    if all(path.exists() for path in flat_markers):
        return "flat"
    nested_markers = [
        rvc_root / "infer/modules/train/preprocess.py",
        rvc_root / "infer/modules/train/train.py",
        rvc_root / "tools/infer_cli.py",
    ]
    if all(path.exists() for path in nested_markers):
        return "nested"
    raise RuntimeError(f"Unsupported RVC WebUI layout under {rvc_root}")


def resolve_rvc_root(configured_root: Path) -> Path:
    candidates = [configured_root]
    home_dir = Path.home()
    common_names = [
        "Retrieval-based-Voice-Conversion-WebUI",
        "RVC-WebUI",
    ]
    for name in common_names:
        candidates.extend([
            Path("/") / name,
            Path("/root") / name,
            home_dir / name,
        ])

    seen = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if looks_like_rvc_root(resolved):
            return resolved

    searched = ", ".join(sorted(seen))
    raise RuntimeError(
        "RVC root directory does not exist or is not a valid RVC repo. "
        f"Configured value: {configured_root}. Checked: {searched}. "
        "Set AIMUSIC_RVC_ROOT_DIR to the directory that contains infer-web.py "
        "or tools/infer_cli.py."
    )


def looks_like_rvc_root(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    markers = [
        path / "infer-web.py",
        path / "trainset_preprocess_pipeline_print.py",
        path / "tools" / "infer_cli.py",
        path / "infer" / "modules" / "train",
    ]
    return any(marker.exists() for marker in markers)


def build_rvc_env(rvc_root: Path, layout: str) -> Dict[str, str]:
    env = os.environ.copy()
    if layout == "flat":
        env.setdefault("weight_root", str(rvc_root / "weights"))
        env.setdefault("weight_uvr5_root", str(rvc_root / "uvr5_weights"))
        env.setdefault("outside_index_root", str(rvc_root / "logs"))
    else:
        env.setdefault("weight_root", str(rvc_root / "assets" / "weights"))
        env.setdefault("weight_uvr5_root", str(rvc_root / "assets" / "uvr5_weights"))
        env.setdefault("outside_index_root", str(rvc_root / "assets" / "indices"))
    env.setdefault("index_root", str(rvc_root / "logs"))
    return env


def normalize_f0_method(method: str) -> str:
    normalized = str(method or "rmvpe").strip().lower()
    if normalized == "rmvpe_gpu":
        return "rmvpe"
    return normalized


def parse_int(raw: object, default: int) -> int:
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except Exception:
        return default


def parse_float_value(raw: object, default: float) -> float:
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except Exception:
        return default


def parse_string(raw: object, default: str) -> str:
    if raw is None:
        return default
    value = str(raw).strip()
    return value or default


def pick_latest(directory: Path, pattern: str) -> Optional[Path]:
    matches = [path for path in directory.rglob(pattern) if path.is_file()]
    if not matches:
        return None
    matches.sort(key=lambda path: path.stat().st_mtime)
    return matches[-1]


def update_progress(run_dir: Path, progress_percent: int, message: str) -> None:
    write_json(run_dir / "progress.json", {
        "progressPercent": max(0, min(100, progress_percent)),
        "message": message,
    })


def load_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, object]) -> None:
    filtered = {key: value for key, value in payload.items() if value is not None}
    path.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")


def tail_text(path: Path, limit: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


class SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


FLAT_INFER_SCRIPT_SOURCE = """\
import os
import sys
from pathlib import Path

ORIGINAL_ARGS = list(sys.argv[1:])
sys.argv = [sys.argv[0]]

import numpy as np
import soundfile as sf
import torch
import fairseq


def main() -> int:
    if len(ORIGINAL_ARGS) < 15:
        raise RuntimeError(f"flat_webui_infer.py expects 15 runtime arguments, got {len(ORIGINAL_ARGS)}")

    rvc_root = Path(ORIGINAL_ARGS[0]).resolve()
    model_path = Path(ORIGINAL_ARGS[1]).resolve()
    input_path = Path(ORIGINAL_ARGS[2]).resolve()
    output_path = Path(ORIGINAL_ARGS[3]).resolve()
    index_path = ORIGINAL_ARGS[4]
    speaker_id = int(ORIGINAL_ARGS[5])
    f0_up_key = int(ORIGINAL_ARGS[6])
    f0_method = ORIGINAL_ARGS[7]
    index_rate = float(ORIGINAL_ARGS[8])
    filter_radius = int(ORIGINAL_ARGS[9])
    resample_sr = int(ORIGINAL_ARGS[10])
    rms_mix_rate = float(ORIGINAL_ARGS[11])
    protect = float(ORIGINAL_ARGS[12])
    device = ORIGINAL_ARGS[13]
    is_half = ORIGINAL_ARGS[14] == "1"

    os.chdir(rvc_root)
    sys.path.append(str(rvc_root))

    from config import Config
    from lib.audio import load_audio
    from vc_infer_pipeline import VC
    from lib.infer_pack.models import (
        SynthesizerTrnMs256NSFsid,
        SynthesizerTrnMs256NSFsid_nono,
        SynthesizerTrnMs768NSFsid,
        SynthesizerTrnMs768NSFsid_nono,
    )

    config = Config()
    config.device = device
    config.is_half = is_half
    models, _, _ = fairseq.checkpoint_utils.load_model_ensemble_and_task(["hubert_base.pt"], suffix="")
    hubert_model = models[0].to(config.device)
    hubert_model = hubert_model.half() if config.is_half else hubert_model.float()
    hubert_model.eval()

    cpt = torch.load(model_path, map_location="cpu")
    tgt_sr = cpt["config"][-1]
    cpt["config"][-3] = cpt["weight"]["emb_g.weight"].shape[0]
    if_f0 = cpt.get("f0", 1)
    version = cpt.get("version", "v1")
    if version == "v1":
        net_g = SynthesizerTrnMs256NSFsid(*cpt["config"], is_half=config.is_half) if if_f0 == 1 else SynthesizerTrnMs256NSFsid_nono(*cpt["config"])
    else:
        net_g = SynthesizerTrnMs768NSFsid(*cpt["config"], is_half=config.is_half) if if_f0 == 1 else SynthesizerTrnMs768NSFsid_nono(*cpt["config"])
    del net_g.enc_q
    net_g.load_state_dict(cpt["weight"], strict=False)
    net_g.eval().to(config.device)
    net_g = net_g.half() if config.is_half else net_g.float()
    vc = VC(tgt_sr, config)

    audio = load_audio(str(input_path), 16000)
    audio_max = np.abs(audio).max() / 0.95
    if audio_max > 1:
        audio /= audio_max
    times = [0, 0, 0]
    normalized_index = index_path.replace("trained", "added") if index_path else ""
    audio_opt = vc.pipeline(
        hubert_model,
        net_g,
        speaker_id,
        audio,
        str(input_path),
        times,
        f0_up_key,
        f0_method,
        normalized_index,
        index_rate,
        if_f0,
        filter_radius,
        tgt_sr,
        resample_sr,
        rms_mix_rate,
        version,
        protect,
        f0_file=None,
    )
    final_sr = resample_sr if tgt_sr != resample_sr and resample_sr >= 16000 else tgt_sr
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), audio_opt, final_sr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


if __name__ == "__main__":
    raise SystemExit(main())
