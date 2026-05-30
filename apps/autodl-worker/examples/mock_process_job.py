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
    input_asset_ids = context["job"].get("inputAssetIds") or []

    for progress, message in [(20, "separating vocals"), (50, "denoising"), (85, "segmenting")]:
        write_json(run_dir / "progress.json", {"progressPercent": progress, "message": message})
        time.sleep(1)

    write_json(run_dir / "result_manifest.json", {
        "segmentCount": max(len(input_asset_ids) * 16, 16),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
