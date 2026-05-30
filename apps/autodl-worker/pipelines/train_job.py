#!/usr/bin/env python3
import argparse
import json
import os
import re
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


def read_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


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


@dataclass
class TrainConfig:
    workspace_dir_name: str = read_env("AIMUSIC_TRAIN_WORKSPACE_DIR_NAME", "train-workspace")
    dataset_dir_name: str = read_env("AIMUSIC_TRAIN_DATASET_DIR_NAME", "dataset")
    output_dir_name: str = read_env("AIMUSIC_TRAIN_OUTPUT_DIR_NAME", "train-output")
    dataset_stage_mode: str = read_env("AIMUSIC_TRAIN_DATASET_STAGE_MODE", "symlink").strip().lower()
    command_template: str = read_env("AIMUSIC_RVC_TRAIN_COMMAND", "")
    train_mode: str = read_env("AIMUSIC_RVC_TRAIN_MODE", "webui_auto").strip().lower()
    model_glob: str = read_env("AIMUSIC_TRAIN_MODEL_GLOB", "*.pth")
    index_glob: str = read_env("AIMUSIC_TRAIN_INDEX_GLOB", "*.index")
    preview_glob: str = read_env("AIMUSIC_TRAIN_PREVIEW_GLOB", "*.wav")
    bundle_name: str = read_env("AIMUSIC_TRAIN_BUNDLE_NAME", "model-artifacts.zip")
    keep_workspace: bool = read_bool("AIMUSIC_TRAIN_KEEP_WORKSPACE", False)
    rvc_root_dir: str = read_env("AIMUSIC_RVC_ROOT_DIR", "/Retrieval-based-Voice-Conversion-WebUI")
    rvc_python_bin: str = read_env("AIMUSIC_RVC_PYTHON_BIN", "python3")
    rvc_device: str = read_env("AIMUSIC_RVC_DEVICE", "cuda:0")
    rvc_gpu_ids: str = read_env("AIMUSIC_RVC_GPU_IDS", "0")
    rvc_version: str = read_env("AIMUSIC_RVC_VERSION", "v2")
    rvc_use_f0: bool = read_bool("AIMUSIC_RVC_USE_F0", True)
    rvc_preprocess_workers: int = read_int("AIMUSIC_RVC_PREPROCESS_WORKERS", 2)
    rvc_f0_workers: int = read_int("AIMUSIC_RVC_F0_WORKERS", 1)
    rvc_rmvpe_gpu_ids: str = read_env("AIMUSIC_RVC_RMVPE_GPU_IDS", "")
    rvc_save_every_epoch: int = read_int("AIMUSIC_RVC_SAVE_EVERY_EPOCH", 10)
    rvc_save_latest: bool = read_bool("AIMUSIC_RVC_SAVE_LATEST", True)
    rvc_cache_gpu: bool = read_bool("AIMUSIC_RVC_CACHE_GPU", False)
    rvc_save_every_weights: bool = read_bool("AIMUSIC_RVC_SAVE_EVERY_WEIGHTS", False)
    rvc_is_half: bool = read_bool("AIMUSIC_RVC_IS_HALF", True)
    rvc_preprocess_per: str = read_env("AIMUSIC_RVC_PREPROCESS_PER", "3.7")
    rvc_noparallel: str = read_env("AIMUSIC_RVC_NOPARALLEL", "0")
    rvc_pretrained_generator: str = read_env("AIMUSIC_RVC_PRETRAINED_GENERATOR", "")
    rvc_pretrained_discriminator: str = read_env("AIMUSIC_RVC_PRETRAINED_DISCRIMINATOR", "")
    rvc_speaker_id: int = read_int("AIMUSIC_RVC_SPEAKER_ID", 0)
    rvc_index_enabled: bool = read_bool("AIMUSIC_RVC_INDEX_ENABLED", True)
    rvc_index_required: bool = read_bool("AIMUSIC_RVC_INDEX_REQUIRED", False)


@dataclass
class AutoTrainArtifacts:
    model_file: Path
    index_file: Optional[Path]
    preview_file: Optional[Path]
    output_dir: Path
    metrics: Dict[str, object]


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and run a real training pipeline")
    parser.add_argument("--context", required=True, help="Path to worker context.json")
    parser.add_argument("--run-dir", required=True, help="Worker job run directory")
    args = parser.parse_args()

    context = load_json(Path(args.context))
    run_dir = Path(args.run_dir).resolve()
    config = TrainConfig()

    job = context.get("job", {})
    payload = context.get("payload") or {}
    resources = context.get("resources", {})
    dataset = resources.get("dataset") or {}
    assets = resources.get("assets") or []

    if not assets:
        raise RuntimeError("No dataset assets were prefetched for training")

    workspace_dir = run_dir / config.workspace_dir_name
    dataset_dir = workspace_dir / config.dataset_dir_name
    output_dir = workspace_dir / config.output_dir_name
    manifests_dir = workspace_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    update_progress(run_dir, 5, "Preparing training dataset")
    staged_files = stage_dataset_assets(assets, dataset_dir, config.dataset_stage_mode)

    train_parameters = {
        "sampleRate": job.get("sampleRate") or 40000,
        "sampleRateTag": to_rvc_sample_rate_tag(job.get("sampleRate") or 40000),
        "f0Method": normalize_f0_method(job.get("f0Method") or "rmvpe"),
        "batchSize": job.get("batchSize") or 8,
        "totalEpoch": job.get("totalEpoch") or 300,
        "speakerId": parse_int(job.get("speakerId"), config.rvc_speaker_id),
        "version": parse_string(payload.get("version"), config.rvc_version),
        "useF0": parse_bool_value(payload.get("useF0"), config.rvc_use_f0),
        "saveEveryEpoch": parse_int(payload.get("saveEveryEpoch"), config.rvc_save_every_epoch),
        "saveLatest": parse_bool_value(payload.get("saveLatest"), config.rvc_save_latest),
        "cacheGpu": parse_bool_value(payload.get("cacheGpu"), config.rvc_cache_gpu),
        "saveEveryWeights": parse_bool_value(payload.get("saveEveryWeights"), config.rvc_save_every_weights),
        "modelName": job.get("modelVersion") or dataset.get("name") or "rvc-model",
        "datasetId": dataset.get("id"),
        "datasetName": dataset.get("name"),
        "assetCount": len(staged_files),
    }
    write_json(manifests_dir / "train_config.json", train_parameters)
    write_json(manifests_dir / "dataset_manifest.json", {
        "dataset": dataset,
        "stagedFiles": staged_files,
    })

    if config.command_template.strip():
        command = build_train_command(
            config.command_template,
            run_dir=run_dir,
            workspace_dir=workspace_dir,
            dataset_dir=dataset_dir,
            output_dir=output_dir,
            context_path=Path(args.context).resolve(),
            manifests_dir=manifests_dir,
            train_parameters=train_parameters,
        )
        update_progress(run_dir, 18, "Launching RVC training")
        execute_shell_command(command, run_dir, "train", run_dir)
        model_file = pick_latest(output_dir, config.model_glob)
        if model_file is None:
            raise RuntimeError(f"No trained model file found under {output_dir} matching {config.model_glob}")
        index_file = pick_latest(output_dir, config.index_glob)
        preview_file = pick_latest(output_dir, config.preview_glob)
        metrics = {
            "mode": "custom-command",
            "sampleRate": train_parameters["sampleRate"],
            "f0Method": train_parameters["f0Method"],
            "batchSize": train_parameters["batchSize"],
            "totalEpoch": train_parameters["totalEpoch"],
            "speakerId": train_parameters["speakerId"],
            "version": train_parameters["version"],
            "useF0": train_parameters["useF0"],
            "saveEveryEpoch": train_parameters["saveEveryEpoch"],
            "saveLatest": train_parameters["saveLatest"],
            "cacheGpu": train_parameters["cacheGpu"],
            "saveEveryWeights": train_parameters["saveEveryWeights"],
            "assetCount": len(staged_files),
        }
    else:
        if config.train_mode != "webui_auto":
            raise RuntimeError("AIMUSIC_RVC_TRAIN_COMMAND is not configured and AIMUSIC_RVC_TRAIN_MODE is not webui_auto")
        artifacts = run_webui_auto_training(
            run_dir=run_dir,
            workspace_dir=workspace_dir,
            dataset_dir=dataset_dir,
            output_dir=output_dir,
            train_parameters=train_parameters,
            config=config,
        )
        model_file = artifacts.model_file
        index_file = artifacts.index_file
        preview_file = artifacts.preview_file
        metrics = artifacts.metrics

    update_progress(run_dir, 92, "Collecting model artifacts")
    bundle_path = run_dir / config.bundle_name
    bundle_model_artifacts(bundle_path, model_file, index_file, manifests_dir / "train_config.json", manifests_dir / "dataset_manifest.json")

    metrics.update({
        "bundleFileName": bundle_path.name,
        "modelFileName": model_file.name,
        "indexFileName": index_file.name if index_file else None,
    })

    result_manifest = {
        "localModelPath": str(bundle_path),
        "localSampleAudioPath": str(preview_file) if preview_file else None,
        "metrics": metrics,
    }
    write_json(run_dir / "result_manifest.json", result_manifest)
    update_progress(run_dir, 100, "Training finished")

    if not config.keep_workspace:
        shutil.rmtree(workspace_dir, ignore_errors=True)

    return 0


def run_webui_auto_training(
    run_dir: Path,
    workspace_dir: Path,
    dataset_dir: Path,
    output_dir: Path,
    train_parameters: Dict[str, object],
    config: TrainConfig,
) -> AutoTrainArtifacts:
    rvc_root = resolve_rvc_root(Path(config.rvc_root_dir))

    effective_version = resolve_rvc_version(str(train_parameters["version"]), rvc_root)
    layout = detect_webui_layout(rvc_root)
    scripts = resolve_webui_scripts(rvc_root, layout)
    exp_name = build_experiment_name(str(train_parameters["modelName"]), train_parameters.get("datasetId"))
    log_dir = rvc_root / "logs" / exp_name
    log_dir.mkdir(parents=True, exist_ok=True)
    weights_dir = resolve_weight_dir(rvc_root, layout)
    weights_dir.mkdir(parents=True, exist_ok=True)
    indices_dir = resolve_indices_dir(rvc_root, layout)
    indices_dir.mkdir(parents=True, exist_ok=True)

    env = build_rvc_env(rvc_root, layout)
    gpu_primary = first_gpu_id(config.rvc_gpu_ids)
    sample_rate_tag = str(train_parameters["sampleRateTag"])
    total_epoch = int(train_parameters["totalEpoch"])
    batch_size = int(train_parameters["batchSize"])
    use_f0 = bool(train_parameters["useF0"])

    if layout == "flat":
        run_flat_webui_auto_training(
            run_dir=run_dir,
            rvc_root=rvc_root,
            log_dir=log_dir,
            dataset_dir=dataset_dir,
            scripts=scripts,
            env=env,
            config=config,
            train_parameters=train_parameters,
            effective_version=effective_version,
        )
    else:
        run_nested_webui_auto_training(
            run_dir=run_dir,
            rvc_root=rvc_root,
            log_dir=log_dir,
            dataset_dir=dataset_dir,
            scripts=scripts,
            env=env,
            config=config,
            train_parameters=train_parameters,
            effective_version=effective_version,
        )

    update_progress(run_dir, 52, "Preparing RVC filelist")
    write_rvc_config_if_missing(rvc_root, log_dir, sample_rate_tag, effective_version, layout)
    file_count = build_rvc_filelist(
        rvc_root=rvc_root,
        log_dir=log_dir,
        sample_rate_tag=sample_rate_tag,
        version=effective_version,
        speaker_id=int(train_parameters["speakerId"]),
        use_f0=use_f0,
    )
    if file_count == 0:
        raise RuntimeError(f"No aligned training entries were produced under {log_dir}")

    pretrained_generator, pretrained_discriminator = resolve_pretrained_models(
        rvc_root,
        sample_rate_tag,
        use_f0,
        effective_version,
        layout,
        config,
    )

    update_progress(run_dir, 68, "RVC model training")
    train_command = [
        config.rvc_python_bin,
        str(scripts["train"]),
        "-e",
        exp_name,
        "-sr",
        sample_rate_tag,
        "-f0",
        "1" if use_f0 else "0",
        "-bs",
        str(batch_size),
        "-te",
        str(total_epoch),
        "-se",
        str(train_parameters["saveEveryEpoch"]),
        "-l",
        "1" if train_parameters["saveLatest"] else "0",
        "-c",
        "1" if train_parameters["cacheGpu"] else "0",
        "-sw",
        "1" if train_parameters["saveEveryWeights"] else "0",
        "-v",
        effective_version,
    ]
    if config.rvc_gpu_ids.strip():
        train_command.extend(["-g", config.rvc_gpu_ids])
    if pretrained_generator:
        train_command.extend(["-pg", pretrained_generator])
    if pretrained_discriminator:
        train_command.extend(["-pd", pretrained_discriminator])

    run_logged_command(
        name="train",
        command=train_command,
        run_dir=run_dir,
        cwd=rvc_root,
        env=env,
    )

    index_file = None
    if config.rvc_index_enabled:
        update_progress(run_dir, 84, "Building RVC index")
        try:
            index_file = build_rvc_index(
                run_dir=run_dir,
                rvc_root=rvc_root,
                log_dir=log_dir,
                version=effective_version,
                python_bin=config.rvc_python_bin,
                layout=layout,
                env=env,
            )
        except Exception as exc:
            if config.rvc_index_required:
                raise
            write_json(run_dir / "index-warning.json", {"warning": str(exc)})

    model_file = weights_dir / f"{exp_name}.pth"
    if not model_file.exists():
        if layout == "flat":
            model_file = extract_flat_small_model(
                run_dir=run_dir,
                rvc_root=rvc_root,
                log_dir=log_dir,
                weights_dir=weights_dir,
                exp_name=exp_name,
                sample_rate_tag=sample_rate_tag,
                effective_version=effective_version,
                use_f0=use_f0,
                python_bin=config.rvc_python_bin,
                env=env,
            )
        else:
            fallback = pick_latest(weights_dir, "*.pth")
            if fallback is None:
                raise RuntimeError(f"No trained model file found under {weights_dir}")
            model_file = fallback

    output_dir.mkdir(parents=True, exist_ok=True)
    copied_model = output_dir / model_file.name
    shutil.copy2(model_file, copied_model)
    copied_index = None
    if index_file is not None and index_file.exists():
        copied_index = output_dir / index_file.name
        shutil.copy2(index_file, copied_index)

    return AutoTrainArtifacts(
        model_file=copied_model,
        index_file=copied_index,
        preview_file=None,
        output_dir=output_dir,
        metrics={
            "mode": "webui_auto",
            "sampleRate": train_parameters["sampleRate"],
            "sampleRateTag": sample_rate_tag,
            "f0Method": train_parameters["f0Method"],
            "batchSize": batch_size,
            "totalEpoch": total_epoch,
            "speakerId": train_parameters["speakerId"],
            "requestedVersion": train_parameters["version"],
            "assetCount": int(train_parameters["assetCount"]),
            "layout": layout,
            "effectiveVersion": effective_version,
            "useF0": use_f0,
            "saveEveryEpoch": train_parameters["saveEveryEpoch"],
            "saveLatest": train_parameters["saveLatest"],
            "cacheGpu": train_parameters["cacheGpu"],
            "saveEveryWeights": train_parameters["saveEveryWeights"],
            "experimentName": exp_name,
            "fileCount": file_count,
            "indexBuilt": copied_index is not None,
        },
    )


def stage_dataset_assets(assets: Sequence[Dict[str, object]], dataset_dir: Path, mode: str) -> List[Dict[str, object]]:
    staged: List[Dict[str, object]] = []
    for index, asset in enumerate(assets, start=1):
        local_path = asset.get("localPath")
        if not isinstance(local_path, str) or not local_path.strip():
            continue
        source = Path(local_path)
        suffix = source.suffix or ".wav"
        target = dataset_dir / f"{index:05d}{suffix}"
        if target.exists():
            target.unlink()

        if mode == "copy":
            shutil.copy2(source, target)
        else:
            os.symlink(source, target)

        staged.append({
            "assetId": asset.get("id"),
            "name": asset.get("name"),
            "sourcePath": str(source),
            "stagedPath": str(target),
            "language": asset.get("language"),
        })
    return staged


def build_train_command(
    template: str,
    run_dir: Path,
    workspace_dir: Path,
    dataset_dir: Path,
    output_dir: Path,
    context_path: Path,
    manifests_dir: Path,
    train_parameters: Dict[str, object],
) -> str:
    values = SafeDict({
        "run_dir": str(run_dir),
        "workspace_dir": str(workspace_dir),
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "context_path": str(context_path),
        "train_config_path": str(manifests_dir / "train_config.json"),
        "dataset_manifest_path": str(manifests_dir / "dataset_manifest.json"),
        "sample_rate": train_parameters["sampleRate"],
        "f0_method": train_parameters["f0Method"],
        "batch_size": train_parameters["batchSize"],
        "total_epoch": train_parameters["totalEpoch"],
        "speaker_id": train_parameters.get("speakerId") or "",
        "version": train_parameters.get("version") or "",
        "use_f0": "1" if train_parameters.get("useF0") else "0",
        "save_every_epoch": train_parameters.get("saveEveryEpoch") or "",
        "save_latest": "1" if train_parameters.get("saveLatest") else "0",
        "cache_gpu": "1" if train_parameters.get("cacheGpu") else "0",
        "save_every_weights": "1" if train_parameters.get("saveEveryWeights") else "0",
        "model_name": train_parameters["modelName"],
        "dataset_id": train_parameters.get("datasetId") or "",
        "dataset_name": train_parameters.get("datasetName") or "",
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
        while process.poll() is None:
            time.sleep(10)
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
    raise RuntimeError(
        f"Unsupported RVC WebUI layout under {rvc_root}. "
        "Expected either root scripts like trainset_preprocess_pipeline_print.py or nested infer/modules/train scripts."
    )


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


def resolve_webui_scripts(rvc_root: Path, layout: str) -> Dict[str, Path]:
    if layout == "flat":
        candidates = {
            "preprocess": rvc_root / "trainset_preprocess_pipeline_print.py",
            "extract_f0_print": rvc_root / "extract_f0_print.py",
            "extract_f0_rmvpe": rvc_root / "extract_f0_rmvpe.py",
            "extract_f0_rmvpe_dml": rvc_root / "extract_f0_rmvpe_dml.py",
            "extract_feature_print": rvc_root / "extract_feature_print.py",
            "train": rvc_root / "train_nsf_sim_cache_sid_load_pretrain.py",
        }
    else:
        candidates = {
            "preprocess": rvc_root / "infer/modules/train/preprocess.py",
            "extract_f0_print": rvc_root / "infer/modules/train/extract/extract_f0_print.py",
            "extract_f0_rmvpe": rvc_root / "infer/modules/train/extract/extract_f0_rmvpe.py",
            "extract_feature_print": rvc_root / "infer/modules/train/extract_feature_print.py",
            "train": rvc_root / "infer/modules/train/train.py",
        }
    missing = [key for key, path in candidates.items() if not path.exists()]
    if missing:
        raise RuntimeError(f"RVC WebUI auto train missing scripts under {rvc_root}: {', '.join(missing)}")
    return candidates


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


def resolve_weight_dir(rvc_root: Path, layout: str) -> Path:
    return rvc_root / ("weights" if layout == "flat" else "assets/weights")


def resolve_indices_dir(rvc_root: Path, layout: str) -> Path:
    return rvc_root / ("logs" if layout == "flat" else "assets/indices")


def run_flat_webui_auto_training(
    run_dir: Path,
    rvc_root: Path,
    log_dir: Path,
    dataset_dir: Path,
    scripts: Dict[str, Path],
    env: Dict[str, str],
    config: TrainConfig,
    train_parameters: Dict[str, object],
    effective_version: str,
) -> None:
    update_progress(run_dir, 18, "RVC preprocessing")
    run_logged_command(
        name="preprocess",
        command=[
            config.rvc_python_bin,
            str(scripts["preprocess"]),
            str(dataset_dir),
            str(train_parameters["sampleRate"]),
            str(config.rvc_preprocess_workers),
            str(log_dir),
            config.rvc_noparallel,
        ],
        run_dir=run_dir,
        cwd=rvc_root,
        env=env,
    )

    update_progress(run_dir, 34, "RVC feature extraction")
    if config.rvc_use_f0:
        f0_method = str(train_parameters["f0Method"])
        if f0_method in {"rmvpe", "rmvpe_gpu"} and scripts.get("extract_f0_rmvpe") and scripts["extract_f0_rmvpe"].exists():
            run_flat_rmvpe_extract(run_dir, rvc_root, log_dir, scripts, env, config)
        else:
            run_logged_command(
                name="extract-f0",
                command=[
                    config.rvc_python_bin,
                    str(scripts["extract_f0_print"]),
                    str(log_dir),
                    str(max(1, config.rvc_f0_workers)),
                    f0_method,
                ],
                run_dir=run_dir,
                cwd=rvc_root,
                env=env,
            )

    run_parallel_feature_extract(
        run_dir=run_dir,
        rvc_root=rvc_root,
        log_dir=log_dir,
        script=scripts["extract_feature_print"],
        env=env,
        config=config,
        effective_version=effective_version,
        is_nested=False,
    )


def run_nested_webui_auto_training(
    run_dir: Path,
    rvc_root: Path,
    log_dir: Path,
    dataset_dir: Path,
    scripts: Dict[str, Path],
    env: Dict[str, str],
    config: TrainConfig,
    train_parameters: Dict[str, object],
    effective_version: str,
) -> None:
    gpu_primary = first_gpu_id(config.rvc_gpu_ids)
    update_progress(run_dir, 18, "RVC preprocessing")
    run_logged_command(
        name="preprocess",
        command=[
            config.rvc_python_bin,
            str(scripts["preprocess"]),
            str(dataset_dir),
            str(train_parameters["sampleRate"]),
            str(config.rvc_preprocess_workers),
            str(log_dir),
            config.rvc_noparallel,
            config.rvc_preprocess_per,
        ],
        run_dir=run_dir,
        cwd=rvc_root,
        env=env,
    )

    update_progress(run_dir, 34, "RVC feature extraction")
    if config.rvc_use_f0:
        if str(train_parameters["f0Method"]) in {"rmvpe", "rmvpe_gpu"}:
            run_logged_command(
                name="extract-f0",
                command=[
                    config.rvc_python_bin,
                    str(scripts["extract_f0_rmvpe"]),
                    str(max(1, config.rvc_f0_workers)),
                    "0",
                    gpu_primary,
                    str(log_dir),
                    bool_text(config.rvc_is_half),
                ],
                run_dir=run_dir,
                cwd=rvc_root,
                env=env,
            )
        else:
            run_logged_command(
                name="extract-f0",
                command=[
                    config.rvc_python_bin,
                    str(scripts["extract_f0_print"]),
                    str(log_dir),
                    str(max(1, config.rvc_f0_workers)),
                    str(train_parameters["f0Method"]),
                ],
                run_dir=run_dir,
                cwd=rvc_root,
                env=env,
            )

    run_parallel_feature_extract(
        run_dir=run_dir,
        rvc_root=rvc_root,
        log_dir=log_dir,
        script=scripts["extract_feature_print"],
        env=env,
        config=config,
        effective_version=effective_version,
        is_nested=True,
    )


def run_flat_rmvpe_extract(
    run_dir: Path,
    rvc_root: Path,
    log_dir: Path,
    scripts: Dict[str, Path],
    env: Dict[str, str],
    config: TrainConfig,
) -> None:
    gpu_ids = split_gpu_ids(config.rvc_rmvpe_gpu_ids or config.rvc_gpu_ids)
    if not gpu_ids and scripts.get("extract_f0_rmvpe_dml") and scripts["extract_f0_rmvpe_dml"].exists():
        run_logged_command(
            name="extract-f0-rmvpe-dml",
            command=[
                config.rvc_python_bin,
                str(scripts["extract_f0_rmvpe_dml"]),
                str(log_dir),
            ],
            run_dir=run_dir,
            cwd=rvc_root,
            env=env,
        )
        return
    if not gpu_ids:
        gpu_ids = ["0"]
    run_parallel_commands(
        name_prefix="extract-f0-rmvpe",
        commands=[
            [
                config.rvc_python_bin,
                str(scripts["extract_f0_rmvpe"]),
                str(len(gpu_ids)),
                str(idx),
                gpu_id,
                str(log_dir),
                bool_text(config.rvc_is_half),
            ]
            for idx, gpu_id in enumerate(gpu_ids)
        ],
        run_dir=run_dir,
        cwd=rvc_root,
        env=env,
    )


def run_parallel_feature_extract(
    run_dir: Path,
    rvc_root: Path,
    log_dir: Path,
    script: Path,
    env: Dict[str, str],
    config: TrainConfig,
    effective_version: str,
    is_nested: bool,
) -> None:
    gpu_ids = split_gpu_ids(config.rvc_gpu_ids)
    if not gpu_ids:
        gpu_ids = ["0"]
    commands: List[List[str]] = []
    for idx, gpu_id in enumerate(gpu_ids):
        command = [
            config.rvc_python_bin,
            str(script),
            config.rvc_device,
            str(len(gpu_ids)),
            str(idx),
            gpu_id,
            str(log_dir),
            effective_version,
        ]
        if is_nested:
            command.append(bool_text(config.rvc_is_half))
        commands.append(command)
    run_parallel_commands(
        name_prefix="extract-feature",
        commands=commands,
        run_dir=run_dir,
        cwd=rvc_root,
        env=env,
    )


def run_parallel_commands(
    name_prefix: str,
    commands: Sequence[Sequence[str]],
    run_dir: Path,
    cwd: Path,
    env: Dict[str, str],
) -> None:
    processes = []
    stdout_files = []
    stderr_files = []
    try:
        for idx, command in enumerate(commands):
            stdout_path = run_dir / f"{name_prefix}-{idx}-stdout.log"
            stderr_path = run_dir / f"{name_prefix}-{idx}-stderr.log"
            stdout_file = stdout_path.open("w", encoding="utf-8")
            stderr_file = stderr_path.open("w", encoding="utf-8")
            stdout_files.append(stdout_file)
            stderr_files.append(stderr_file)
            processes.append(
                subprocess.Popen(
                    [str(item) for item in command],
                    cwd=str(cwd),
                    text=True,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    env=env,
                )
            )
        for idx, process in enumerate(processes):
            process.wait()
            if process.returncode != 0:
                raise RuntimeError(
                    f"{name_prefix}-{idx} failed with code {process.returncode}: {tail_text(run_dir / f'{name_prefix}-{idx}-stderr.log')}"
                )
    finally:
        for file in stdout_files + stderr_files:
            file.close()


def first_gpu_id(gpu_ids: str) -> str:
    for item in gpu_ids.split("-"):
        value = item.strip()
        if value:
            return value
    return "0"


def build_experiment_name(model_name: str, dataset_id: object) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", model_name).strip("-._")
    if not safe:
        safe = "rvc-model"
    if dataset_id:
        short_id = str(dataset_id).replace("-", "")[:8]
        return f"{safe}-{short_id}"
    return safe


def write_rvc_config_if_missing(rvc_root: Path, log_dir: Path, sample_rate_tag: str, version: str, layout: str) -> None:
    if layout == "flat":
        return
    config_path = rvc_root / "configs" / version / f"{sample_rate_tag}.json"
    if not config_path.exists():
        raise RuntimeError(f"Missing RVC config template: {config_path}")
    target = log_dir / "config.json"
    if not target.exists():
        shutil.copy2(config_path, target)


def build_rvc_filelist(
    rvc_root: Path,
    log_dir: Path,
    sample_rate_tag: str,
    version: str,
    speaker_id: int,
    use_f0: bool,
) -> int:
    gt_wavs_dir = log_dir / "0_gt_wavs"
    feature_dir = log_dir / ("3_feature256" if version == "v1" else "3_feature768")
    if use_f0:
        f0_dir = log_dir / "2a_f0"
        f0nsf_dir = log_dir / "2b-f0nsf"
        names = stem_set(gt_wavs_dir) & stem_set(feature_dir) & stem_set(f0_dir) & stem_set(f0nsf_dir)
    else:
        names = stem_set(gt_wavs_dir) & stem_set(feature_dir)

    lines: List[str] = []
    for name in sorted(names):
        if use_f0:
            lines.append(
                f"{(gt_wavs_dir / f'{name}.wav').as_posix()}|"
                f"{(feature_dir / f'{name}.npy').as_posix()}|"
                f"{(f0_dir / f'{name}.wav.npy').as_posix()}|"
                f"{(f0nsf_dir / f'{name}.wav.npy').as_posix()}|"
                f"{speaker_id}"
            )
        else:
            lines.append(
                f"{(gt_wavs_dir / f'{name}.wav').as_posix()}|"
                f"{(feature_dir / f'{name}.npy').as_posix()}|"
                f"{speaker_id}"
            )

    mute_root = rvc_root / "logs" / "mute"
    feature_dim = "256" if version == "v1" else "768"
    for _ in range(2):
        if use_f0:
            lines.append(
                f"{(mute_root / '0_gt_wavs' / f'mute{sample_rate_tag}.wav').as_posix()}|"
                f"{(mute_root / f'3_feature{feature_dim}' / 'mute.npy').as_posix()}|"
                f"{(mute_root / '2a_f0' / 'mute.wav.npy').as_posix()}|"
                f"{(mute_root / '2b-f0nsf' / 'mute.wav.npy').as_posix()}|"
                f"{speaker_id}"
            )
        else:
            lines.append(
                f"{(mute_root / '0_gt_wavs' / f'mute{sample_rate_tag}.wav').as_posix()}|"
                f"{(mute_root / f'3_feature{feature_dim}' / 'mute.npy').as_posix()}|"
                f"{speaker_id}"
            )

    (log_dir / "filelist.txt").write_text("\n".join(lines), encoding="utf-8")
    return len(names)


def stem_set(directory: Path) -> set:
    if not directory.exists():
        return set()
    return {path.stem.replace(".wav", "") for path in directory.iterdir() if path.is_file()}


def resolve_pretrained_models(
    rvc_root: Path,
    sample_rate_tag: str,
    use_f0: bool,
    effective_version: str,
    layout: str,
    config: TrainConfig,
) -> List[str]:
    generator = config.rvc_pretrained_generator.strip()
    discriminator = config.rvc_pretrained_discriminator.strip()
    if generator and discriminator:
        return [generator, discriminator]

    suffix = "" if effective_version == "v1" else "_v2"
    prefix = "f0" if use_f0 else ""
    pretrained_dir = rvc_root / (f"pretrained{suffix}" if layout == "flat" else f"assets/pretrained{suffix}")
    generator_candidate = pretrained_dir / f"{prefix}G{sample_rate_tag}.pth"
    discriminator_candidate = pretrained_dir / f"{prefix}D{sample_rate_tag}.pth"
    return [
        str(generator_candidate) if generator_candidate.exists() else generator,
        str(discriminator_candidate) if discriminator_candidate.exists() else discriminator,
    ]


def resolve_rvc_version(requested_version: str, rvc_root: Path) -> str:
    normalized = (requested_version or "v2").strip().lower()
    flat_mode = (rvc_root / "trainset_preprocess_pipeline_print.py").exists()
    if flat_mode and normalized in {"v1", "v2"}:
        return normalized
    if (rvc_root / "configs" / normalized).exists():
        return normalized
    if normalized in {"v3", "v4"} and (rvc_root / "configs" / "v2").exists():
        raise RuntimeError(
            f"AIMUSIC_RVC_VERSION={requested_version} is not available under {rvc_root / 'configs'}. "
            "The current upstream RVC WebUI training code still uses model architecture versions v1/v2. "
            "If you mean the image or workflow release is RVC v4, keep AIMUSIC_RVC_VERSION=v2 unless your repo really provides configs/v4 and matching train scripts."
        )
    raise RuntimeError(f"Unsupported AIMUSIC_RVC_VERSION={requested_version}, missing {rvc_root / 'configs' / normalized}")


def build_rvc_index(
    run_dir: Path,
    rvc_root: Path,
    log_dir: Path,
    version: str,
    python_bin: str,
    layout: str,
    env: Dict[str, str],
) -> Optional[Path]:
    script_path = run_dir / "build_rvc_index.py"
    script_path.write_text(
        INDEX_SCRIPT_SOURCE,
        encoding="utf-8",
    )
    run_logged_command(
        name="build-index",
        command=[python_bin, str(script_path), str(log_dir), version, str(resolve_indices_dir(rvc_root, layout))],
        run_dir=run_dir,
        cwd=rvc_root,
        env=env,
    )
    added_indexes = sorted(log_dir.glob("added_*.index"))
    return added_indexes[-1] if added_indexes else None


def to_rvc_sample_rate_tag(sample_rate: object) -> str:
    try:
        value = int(sample_rate)
    except (TypeError, ValueError):
        value = 40000
    if value <= 32000:
        return "32k"
    if value >= 48000:
        return "48k"
    return "40k"


def normalize_f0_method(method: str) -> str:
    normalized = str(method or "rmvpe").strip().lower()
    if normalized == "rmvpe_gpu":
        return "rmvpe"
    return normalized


def parse_bool_value(raw: object, default: bool) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def parse_int(raw: object, default: int) -> int:
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except Exception:
        return default


def parse_string(raw: object, default: str) -> str:
    if raw is None:
        return default
    value = str(raw).strip()
    return value or default


def bool_text(value: bool) -> str:
    return "True" if value else "False"


def split_gpu_ids(raw: str) -> List[str]:
    return [item.strip() for item in str(raw or "").split("-") if item.strip()]


def extract_flat_small_model(
    run_dir: Path,
    rvc_root: Path,
    log_dir: Path,
    weights_dir: Path,
    exp_name: str,
    sample_rate_tag: str,
    effective_version: str,
    use_f0: bool,
    python_bin: str,
    env: Dict[str, str],
) -> Path:
    checkpoint = pick_latest(log_dir, "G_*.pth")
    if checkpoint is None:
        raise RuntimeError(f"No G_*.pth checkpoint found under {log_dir}")
    script_path = run_dir / "extract_flat_small_model.py"
    script_path.write_text(EXTRACT_FLAT_SMALL_MODEL_SOURCE, encoding="utf-8")
    run_logged_command(
        name="extract-small-model",
        command=[
            python_bin,
            str(script_path),
            str(rvc_root),
            str(checkpoint),
            exp_name,
            sample_rate_tag,
            "1" if use_f0 else "0",
            effective_version,
        ],
        run_dir=run_dir,
        cwd=rvc_root,
        env=env,
    )
    model_file = weights_dir / f"{exp_name}.pth"
    if not model_file.exists():
        raise RuntimeError(f"Expected extracted model missing: {model_file}")
    return model_file


def pick_latest(directory: Path, pattern: str) -> Optional[Path]:
    matches = [path for path in directory.rglob(pattern) if path.is_file()]
    if not matches:
        return None
    matches.sort(key=lambda path: path.stat().st_mtime)
    return matches[-1]


def bundle_model_artifacts(bundle_path: Path, model_file: Path, index_file: Optional[Path], *extra_files: Path) -> None:
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(model_file, arcname=f"artifacts/{model_file.name}")
        if index_file:
            archive.write(index_file, arcname=f"artifacts/{index_file.name}")
        for extra_file in extra_files:
            if extra_file.exists():
                archive.write(extra_file, arcname=f"manifests/{extra_file.name}")


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


INDEX_SCRIPT_SOURCE = """\
import os
import sys
from pathlib import Path

import faiss
import numpy as np


def main() -> int:
    log_dir = Path(sys.argv[1]).resolve()
    version = sys.argv[2]
    outside_index_root = Path(sys.argv[3]).resolve()
    outside_index_root.mkdir(parents=True, exist_ok=True)
    feature_dir = log_dir / ("3_feature256" if version == "v1" else "3_feature768")
    if not feature_dir.exists():
        raise RuntimeError(f"feature dir missing: {feature_dir}")
    npys = []
    for path in sorted(feature_dir.glob("*.npy")):
        npys.append(np.load(path))
    if not npys:
        raise RuntimeError(f"no feature npy files found in {feature_dir}")
    big_npy = np.concatenate(npys, axis=0)
    big_npy_idx = np.arange(big_npy.shape[0])
    np.random.shuffle(big_npy_idx)
    big_npy = big_npy[big_npy_idx]
    np.save(log_dir / "total_fea.npy", big_npy)
    n_ivf = min(int(16 * np.sqrt(big_npy.shape[0])), max(1, big_npy.shape[0] // 39))
    dim = 256 if version == "v1" else 768
    index = faiss.index_factory(dim, f"IVF{n_ivf},Flat")
    index_ivf = faiss.extract_index_ivf(index)
    index_ivf.nprobe = 1
    index.train(big_npy)
    trained_path = log_dir / f"trained_IVF{n_ivf}_Flat_nprobe_{index_ivf.nprobe}_{log_dir.name}_{version}.index"
    faiss.write_index(index, str(trained_path))
    batch_size_add = 8192
    for i in range(0, big_npy.shape[0], batch_size_add):
        index.add(big_npy[i : i + batch_size_add])
    added_path = log_dir / f"added_IVF{n_ivf}_Flat_nprobe_{index_ivf.nprobe}_{log_dir.name}_{version}.index"
    faiss.write_index(index, str(added_path))
    outside_link = outside_index_root / f"{log_dir.name}_IVF{n_ivf}_Flat_nprobe_{index_ivf.nprobe}_{log_dir.name}_{version}.index"
    if outside_link.exists() or outside_link.is_symlink():
        outside_link.unlink()
    try:
        os.symlink(added_path, outside_link)
    except Exception:
        import shutil
        shutil.copy2(added_path, outside_link)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


EXTRACT_FLAT_SMALL_MODEL_SOURCE = """\
import os
import sys
from pathlib import Path


def main() -> int:
    rvc_root = Path(sys.argv[1]).resolve()
    checkpoint = Path(sys.argv[2]).resolve()
    name = sys.argv[3]
    sr = sys.argv[4]
    if_f0 = sys.argv[5]
    version = sys.argv[6]
    os.chdir(rvc_root)
    sys.path.append(str(rvc_root))
    try:
        from lib.train.process_ckpt import extract_small_model
    except Exception:
        from train.process_ckpt import extract_small_model
    result = extract_small_model(str(checkpoint), name, sr, if_f0, "Auto extracted by ai-music worker", version)
    if str(result).lower().startswith("traceback"):
        raise RuntimeError(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


if __name__ == "__main__":
    raise SystemExit(main())
