#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    context_path = Path(sys.argv[1])
    run_dir = Path(sys.argv[2])
    context = json.loads(context_path.read_text(encoding="utf-8"))
    job = context["job"]

    for progress, message in [(10, "preparing dataset"), (40, "training epochs"), (75, "exporting checkpoints")]:
        write_json(run_dir / "progress.json", {"progressPercent": progress, "message": message})
        time.sleep(1)

    model_path = run_dir / "trained-model.pth"
    sample_audio_path = run_dir / "preview.wav"
    model_path.write_bytes(b"MOCKMODEL")
    sample_audio_path.write_bytes(b"RIFFMOCKPREVIEW")

    write_json(run_dir / "result_manifest.json", {
        "localModelPath": str(model_path),
        "localSampleAudioPath": str(sample_audio_path),
        "metrics": {
            "epochs": job.get("totalEpoch") or 300,
            "sampleRate": job.get("sampleRate") or 40000,
            "loss": 0.031,
        },
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
