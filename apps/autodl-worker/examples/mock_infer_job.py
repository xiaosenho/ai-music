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

    for progress, message in [(15, "loading model"), (55, "running voice conversion"), (90, "writing output")]:
        write_json(run_dir / "progress.json", {"progressPercent": progress, "message": message})
        time.sleep(1)

    output_path = run_dir / "result.wav"
    output_path.write_bytes(b"RIFFMOCKAUDIO")
    write_json(run_dir / "result_manifest.json", {
        "outputObjectKey": "outputs/%s/result.wav" % job["id"],
        "outputUrl": str(output_path),
        "outputName": "infer-%s.wav" % job["id"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
