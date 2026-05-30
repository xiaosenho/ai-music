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
    input_assets = context.get("resources", {}).get("assets") or []

    for progress, message in [(20, "separating vocals"), (50, "denoising"), (85, "segmenting")]:
        write_json(run_dir / "progress.json", {"progressPercent": progress, "message": message})
        time.sleep(1)

    processed_dir = run_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    processed_files = []

    if not input_assets:
        input_assets = [{"name": "sample-input.wav"}]

    for index, asset in enumerate(input_assets, start=1):
        output_path = processed_dir / f"segment-{index:03d}.wav"
        output_path.write_bytes(b"RIFFMOCKSEGMENT")
        processed_files.append({
            "localPath": str(output_path),
            "fileName": output_path.name,
            "assetType": "AUDIO",
            "language": asset.get("language") or "zh-CN",
            "note": "processed segment",
            "metadata": {
                "sourceAssetId": asset.get("id"),
                "sourceAssetName": asset.get("name"),
            },
        })

    write_json(run_dir / "result_manifest.json", {
        "segmentCount": len(processed_files),
        "processedAssets": [],
        "localProcessedFiles": processed_files,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
