#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


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


def read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


@dataclass
class PipelineConfig:
    sample_rate: int = read_int("AIMUSIC_PROCESS_OUTPUT_SAMPLE_RATE", 40000)
    channels: int = read_int("AIMUSIC_PROCESS_TARGET_CHANNELS", 1)
    min_segment_seconds: float = read_float("AIMUSIC_PROCESS_MIN_SEGMENT_SECONDS", 2.0)
    max_segment_seconds: float = read_float("AIMUSIC_PROCESS_MAX_SEGMENT_SECONDS", 12.0)
    silence_db: str = read_env("AIMUSIC_PROCESS_SILENCE_DB", "-35dB")
    silence_duration_seconds: float = read_float("AIMUSIC_PROCESS_SILENCE_DURATION_SECONDS", 0.35)
    audio_filters: str = read_env(
        "AIMUSIC_PROCESS_AUDIO_FILTERS",
        "highpass=f=80,lowpass=f=12000,loudnorm=I=-16:TP=-1.5:LRA=11",
    )
    vocal_tool: str = read_env("AIMUSIC_PROCESS_VOCAL_TOOL", "demucs").strip().lower()
    enable_demucs: bool = read_bool("AIMUSIC_PROCESS_ENABLE_DEMUCS", True)
    demucs_model: str = read_env("AIMUSIC_PROCESS_DEMUCS_MODEL", "htdemucs")
    uvr_command: str = read_env("AIMUSIC_PROCESS_UVR_COMMAND", "")
    keep_intermediate: bool = read_bool("AIMUSIC_PROCESS_KEEP_INTERMEDIATE", False)
    ffmpeg_bin: str = read_env("AIMUSIC_PROCESS_FFMPEG_BIN", "ffmpeg")
    ffprobe_bin: str = read_env("AIMUSIC_PROCESS_FFPROBE_BIN", "ffprobe")


def main() -> int:
    parser = argparse.ArgumentParser(description="Process audio assets for training datasets.")
    parser.add_argument("--context", required=True, help="Path to context.json from worker")
    parser.add_argument("--run-dir", required=True, help="Job run directory")
    args = parser.parse_args()

    context = load_json(Path(args.context))
    run_dir = Path(args.run_dir).resolve()
    config = PipelineConfig()

    inputs = context.get("resources", {}).get("assets") or []
    if not inputs:
        raise RuntimeError("No prefetched input assets found in resources.assets")

    work_dir = run_dir / "process-work"
    processed_dir = run_dir / "processed"
    work_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    all_segments: List[Dict[str, object]] = []
    total_assets = len(inputs)

    for index, asset in enumerate(inputs, start=1):
        asset_name = str(asset.get("name") or f"asset-{index}")
        input_path = asset.get("localPath")
        if not isinstance(input_path, str) or not input_path.strip():
            raise RuntimeError(f"Asset {asset_name} missing localPath")

        update_progress(run_dir, progress_for(index - 1, total_assets, 0.05), f"Preparing {asset_name}")
        prepared_audio = convert_to_wav(Path(input_path), work_dir / f"{index:03d}-prepared.wav", config)

        vocal_audio = prepared_audio
        if should_run_vocal_separation(config):
            update_progress(run_dir, progress_for(index - 1, total_assets, 0.20), f"Separating vocals for {asset_name}")
            separated = separate_vocals(prepared_audio, work_dir / f"{index:03d}-separated", config)
            if separated is not None:
                vocal_audio = separated

        update_progress(run_dir, progress_for(index - 1, total_assets, 0.45), f"Enhancing {asset_name}")
        enhanced_audio = enhance_audio(vocal_audio, work_dir / f"{index:03d}-enhanced.wav", config)

        update_progress(run_dir, progress_for(index - 1, total_assets, 0.65), f"Detecting segments for {asset_name}")
        segments = detect_segments(enhanced_audio, config)
        if not segments:
            duration = probe_duration(enhanced_audio, config)
            if duration >= config.min_segment_seconds:
                segments = [(0.0, min(duration, config.max_segment_seconds))]

        update_progress(run_dir, progress_for(index - 1, total_assets, 0.82), f"Exporting segments for {asset_name}")
        exported = export_segments(
            enhanced_audio,
            processed_dir,
            asset,
            segments,
            config,
            start_index=len(all_segments) + 1,
        )
        all_segments.extend(exported)
        update_progress(run_dir, progress_for(index, total_assets, 0.0), f"Finished {asset_name}")

    manifest = {
        "segmentCount": len(all_segments),
        "localProcessedFiles": all_segments,
        "pipeline": {
            "type": "ffmpeg-demucs-silence-v1",
            "sampleRate": config.sample_rate,
            "channels": config.channels,
            "vocalTool": config.vocal_tool if should_run_vocal_separation(config) else "none",
        },
    }
    write_json(run_dir / "result_manifest.json", manifest)
    update_progress(run_dir, 100, "Process pipeline completed")

    if not config.keep_intermediate:
        shutil.rmtree(work_dir, ignore_errors=True)

    return 0


def progress_for(asset_index: int, total_assets: int, intra: float) -> int:
    if total_assets <= 0:
        return 0
    base = asset_index / total_assets
    return max(1, min(99, int((base + intra / total_assets) * 100)))


def should_run_vocal_separation(config: PipelineConfig) -> bool:
    return (config.vocal_tool == "demucs" and config.enable_demucs) or (
        config.vocal_tool == "uvr" and bool(config.uvr_command.strip())
    )


def convert_to_wav(input_path: Path, output_path: Path, config: PipelineConfig) -> Path:
    run_command([
        config.ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        str(config.channels),
        "-ar",
        str(config.sample_rate),
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ], "ffmpeg convert")
    return output_path


def separate_vocals(input_path: Path, output_dir: Path, config: PipelineConfig) -> Optional[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    if config.vocal_tool == "demucs":
        demucs_bin = resolve_demucs_command()
        if demucs_bin is None:
            print("[process] demucs is not available, skipping vocal separation", file=sys.stderr)
            return None

        try:
            run_command([
                *demucs_bin,
                "--two-stems",
                "vocals",
                "-n",
                config.demucs_model,
                "--out",
                str(output_dir),
                str(input_path),
            ], "demucs separate")
        except RuntimeError as exc:
            print(f"[process] demucs failed, skipping vocal separation: {exc}", file=sys.stderr)
            return None

        candidates = sorted(output_dir.rglob("vocals.wav"))
        if candidates:
            return candidates[-1]
        return None

    if config.vocal_tool == "uvr" and config.uvr_command.strip():
        command = config.uvr_command.format(
            input_path=str(input_path),
            output_dir=str(output_dir),
        )
        run_shell(command, "uvr separate")
        candidates = [path for path in output_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".wav", ".flac", ".mp3"}]
        if candidates:
            candidates.sort(key=lambda path: path.stat().st_mtime)
            return candidates[-1]
        return None

    return None


def enhance_audio(input_path: Path, output_path: Path, config: PipelineConfig) -> Path:
    command = [
        config.ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-ac",
        str(config.channels),
        "-ar",
        str(config.sample_rate),
    ]
    if config.audio_filters.strip():
        command.extend(["-af", config.audio_filters])
    command.extend(["-c:a", "pcm_s16le", str(output_path)])
    run_command(command, "ffmpeg enhance")
    return output_path


def detect_segments(input_path: Path, config: PipelineConfig) -> List[Tuple[float, float]]:
    duration = probe_duration(input_path, config)
    silence_points = detect_silence_points(input_path, config)
    segments = non_silent_segments(duration, silence_points, config.min_segment_seconds)
    return split_long_segments(segments, config.min_segment_seconds, config.max_segment_seconds)


def probe_duration(input_path: Path, config: PipelineConfig) -> float:
    completed = run_command([
        config.ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ], "ffprobe duration", capture_output=True)
    raw = completed.stdout.strip()
    return float(raw) if raw else 0.0


def detect_silence_points(input_path: Path, config: PipelineConfig) -> List[Tuple[Optional[float], Optional[float]]]:
    completed = run_command([
        config.ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        f"silencedetect=n={config.silence_db}:d={config.silence_duration_seconds}",
        "-f",
        "null",
        "-",
    ], "ffmpeg silencedetect", capture_output=True, allow_failure=True)

    text = (completed.stderr or "") + "\n" + (completed.stdout or "")
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", text)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", text)]

    silence_ranges: List[Tuple[Optional[float], Optional[float]]] = []
    for start in starts:
        silence_ranges.append((start, None))
    for end in ends:
        matched = False
        for index, (start, existing_end) in enumerate(silence_ranges):
            if existing_end is None and (start is None or start <= end):
                silence_ranges[index] = (start, end)
                matched = True
                break
        if not matched:
            silence_ranges.append((None, end))
    silence_ranges.sort(key=lambda item: (item[0] if item[0] is not None else -1))
    return silence_ranges


def non_silent_segments(duration: float, silence_ranges: Sequence[Tuple[Optional[float], Optional[float]]], min_segment_seconds: float) -> List[Tuple[float, float]]:
    if duration <= 0:
        return []

    if not silence_ranges:
        return [(0.0, duration)] if duration >= min_segment_seconds else []

    cursor = 0.0
    segments: List[Tuple[float, float]] = []
    for silence_start, silence_end in silence_ranges:
        start = silence_start if silence_start is not None else cursor
        end = silence_end if silence_end is not None else duration
        if start - cursor >= min_segment_seconds:
            segments.append((cursor, start))
        cursor = max(cursor, end)

    if duration - cursor >= min_segment_seconds:
        segments.append((cursor, duration))

    return segments


def split_long_segments(
    segments: Sequence[Tuple[float, float]],
    min_segment_seconds: float,
    max_segment_seconds: float,
) -> List[Tuple[float, float]]:
    if max_segment_seconds <= min_segment_seconds:
        return list(segments)

    normalized: List[Tuple[float, float]] = []
    for start, end in segments:
        length = end - start
        if length <= max_segment_seconds:
            normalized.append((round(start, 3), round(end, 3)))
            continue

        count = max(1, math.ceil(length / max_segment_seconds))
        chunk = length / count
        cursor = start
        while cursor < end:
            chunk_end = min(end, cursor + max_segment_seconds)
            if chunk_end - cursor >= min_segment_seconds:
                normalized.append((round(cursor, 3), round(chunk_end, 3)))
            cursor = chunk_end
    return normalized


def export_segments(
    source_audio: Path,
    processed_dir: Path,
    asset: Dict[str, object],
    segments: Sequence[Tuple[float, float]],
    config: PipelineConfig,
    start_index: int,
) -> List[Dict[str, object]]:
    exports: List[Dict[str, object]] = []
    for offset, (start, end) in enumerate(segments):
        file_name = f"segment-{start_index + offset:04d}.wav"
        output_path = processed_dir / file_name
        run_command([
            config.ffmpeg_bin,
            "-y",
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            str(source_audio),
            "-ac",
            str(config.channels),
            "-ar",
            str(config.sample_rate),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ], "ffmpeg segment export")
        exports.append({
            "localPath": str(output_path),
            "fileName": file_name,
            "assetType": "AUDIO",
            "durationSeconds": int(round(end - start)),
            "language": asset.get("language") or "zh-CN",
            "note": "processed speech segment",
            "metadata": {
                "sourceAssetId": asset.get("id"),
                "sourceAssetName": asset.get("name"),
                "startSeconds": start,
                "endSeconds": end,
                "pipeline": "ffmpeg-demucs-silence-v1",
            },
        })
    return exports


def resolve_demucs_command() -> Optional[List[str]]:
    candidates = [
        ["python3", "-m", "demucs.separate"],
        ["demucs"],
    ]
    for candidate in candidates:
        try:
            completed = subprocess.run(candidate + ["--help"], capture_output=True, check=False, text=True)
            if completed.returncode == 0:
                return candidate
        except FileNotFoundError:
            continue
    return None


def run_command(
    command: Sequence[str],
    label: str,
    capture_output: bool = False,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        list(command),
        text=True,
        capture_output=capture_output,
        check=False,
    )
    if completed.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"{label} failed with code {completed.returncode}: {(completed.stderr or completed.stdout or '').strip()}"
        )
    return completed


def run_shell(command: str, label: str) -> None:
    completed = subprocess.run(command, shell=True, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with code {completed.returncode}: {(completed.stderr or completed.stdout or '').strip()}"
        )


def update_progress(run_dir: Path, progress_percent: int, message: str) -> None:
    write_json(run_dir / "progress.json", {
        "progressPercent": max(0, min(100, progress_percent)),
        "message": message,
    })


def load_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
