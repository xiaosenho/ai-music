# AutoDL Worker Deployment

This guide is for the current project layout:

- control plane on your own server
- file upload and outputs stored in Tencent COS
- heavy `PROCESS / TRAIN / INFER` jobs executed on AutoDL
- AutoDL image based on RVC WebUI V4 style root scripts, while model version stays `v2`

## Architecture

- Aliyun server:
  - `apps/api`
  - `apps/web`
  - PostgreSQL
  - Redis
- Tencent COS:
  - raw assets
  - processed segments
  - model bundles
  - inference outputs
- AutoDL:
  - `apps/autodl-worker`
  - RVC WebUI runtime
  - ffmpeg / faiss / pytorch / fairseq

## 1. Server prerequisites

Before starting the worker, make sure your server side is already available:

- backend API can be reached from AutoDL
- PostgreSQL and Redis are healthy
- COS credentials are configured in backend

Required backend checks:

```bash
curl http://YOUR_SERVER_IP:8092/actuator/health
curl http://YOUR_SERVER_IP:8092/api/v1/dashboard/summary
```

If the backend is behind a domain, replace `YOUR_SERVER_IP:8092` with that domain.

## 2. AutoDL prerequisites

This worker now auto-detects two RVC WebUI families:

- root-level script layout:
  - `trainset_preprocess_pipeline_print.py`
  - `extract_f0_print.py`
  - `extract_feature_print.py`
  - `train_nsf_sim_cache_sid_load_pretrain.py`
  - `infer-web.py`
- nested layout:
  - `infer/modules/train/...`
  - `tools/infer_cli.py`

Your current image is the first one, so the worker will use that automatically.

Recommended checks on AutoDL:

```bash
cd /Retrieval-based-Voice-Conversion-WebUI
which python
python --version
ls
ls weights
ls logs
```

Recommended runtime:

- Python: `/root/miniconda3/bin/python`
- RVC root: `/Retrieval-based-Voice-Conversion-WebUI`

## 3. Clone this project on AutoDL

```bash
cd /root
git clone git@github.com:xiaosenho/ai-music.git
cd ai-music/apps/autodl-worker
cp .env.example .env
```

If AutoDL does not have your SSH key, use HTTPS instead:

```bash
git clone https://github.com/xiaosenho/ai-music.git
```

## 4. Configure the worker

Edit `apps/autodl-worker/.env`:

```bash
AIMUSIC_CONTROL_PLANE_BASE_URL=http://YOUR_SERVER_IP:8092

AIMUSIC_WORKER_PROVIDER=autodl
AIMUSIC_WORKER_VERSION=autodl-worker-v1
AIMUSIC_WORKER_SUPPORTED_JOB_TYPES=PROCESS,TRAIN,INFER

AIMUSIC_WORKER_STATE_DIR=./.state
AIMUSIC_WORKER_RUNS_DIR=./runs
AIMUSIC_WORKER_PREFETCH_RESOURCES=true
AIMUSIC_WORKER_USE_MOCK_EXECUTOR=false

AIMUSIC_RVC_ROOT_DIR=/Retrieval-based-Voice-Conversion-WebUI
AIMUSIC_RVC_PYTHON_BIN=/root/miniconda3/bin/python
AIMUSIC_RVC_DEVICE=cuda:0
AIMUSIC_RVC_GPU_IDS=0
AIMUSIC_RVC_VERSION=v2
AIMUSIC_RVC_USE_F0=true
AIMUSIC_RVC_INDEX_ENABLED=true
AIMUSIC_RVC_INDEX_REQUIRED=false
AIMUSIC_RVC_PREPROCESS_WORKERS=2
AIMUSIC_RVC_F0_WORKERS=1
AIMUSIC_RVC_RMVPE_GPU_IDS=0-0
AIMUSIC_RVC_IS_HALF=true
AIMUSIC_RVC_SPEAKER_ID=0

AIMUSIC_PROCESS_COMMAND=python3 pipelines/process_job.py --context "{context_path}" --run-dir "{run_dir}"
AIMUSIC_TRAIN_COMMAND=python3 pipelines/train_job.py --context "{context_path}" --run-dir "{run_dir}"
AIMUSIC_INFER_COMMAND=python3 pipelines/infer_job.py --context "{context_path}" --run-dir "{run_dir}"

AIMUSIC_RVC_TRAIN_MODE=webui_auto
AIMUSIC_RVC_TRAIN_COMMAND=

AIMUSIC_RVC_INFER_MODE=webui_auto
AIMUSIC_RVC_INFER_COMMAND=
```

Notes:

- keep `AIMUSIC_RVC_VERSION=v2`
- do not change it to `v4`
- `V4` here refers to your WebUI distribution/workflow, not the model architecture flag used by training

## 5. Install missing Python packages if needed

Your AutoDL image may already contain everything. If not, install packages inside the image environment used by RVC:

```bash
cd /Retrieval-based-Voice-Conversion-WebUI
/root/miniconda3/bin/python -m pip install soundfile
```

If `faiss` or `fairseq` are missing, install them in the same environment your RVC image uses, not in a different system Python.

Quick check:

```bash
cd /Retrieval-based-Voice-Conversion-WebUI
/root/miniconda3/bin/python - <<'PY'
import faiss
import fairseq
import soundfile
print("deps ok")
PY
```

## 6. Start the worker

```bash
cd /root/ai-music/apps/autodl-worker
./scripts/start-worker.sh foreground
```

After startup, it should:

- register to backend
- start heartbeats
- poll jobs
- prefetch dataset/model/input files
- execute pipeline
- upload outputs to COS
- report result back to backend

## 7. Recommended tmux start

For long-running jobs on AutoDL:

```bash
cd /root/ai-music/apps/autodl-worker
./scripts/start-worker.sh tmux
```

View status:

```bash
./scripts/status-worker.sh
```

Stop worker:

```bash
./scripts/stop-worker.sh
```

If you want to inspect the live tmux session directly:

```bash
tmux attach -t aimusic-worker
```

## 8. Install AutoDL autostart

The repo now includes a helper that writes a crontab `@reboot` entry for the worker:

```bash
cd /root/ai-music/apps/autodl-worker
./scripts/install-autostart-cron.sh
```

That entry will run:

```bash
/usr/bin/env bash /root/ai-music/apps/autodl-worker/scripts/start-worker.sh tmux
```

Notes:

- make sure `.env` is already configured before installing autostart
- default mode is `tmux`, so the worker keeps running after boot
- logs will be written to `apps/autodl-worker/logs/worker.log`
- if you want the node to pull the latest repo on every boot, add this line to `.env`:

```bash
AIMUSIC_WORKER_AUTO_GIT_PULL=true
```

Check current crontab:

```bash
crontab -l
```

## 9. Smoke test flow

Recommended test order:

1. Upload one short raw audio asset from the web console
2. Create one dataset
3. Launch one `PROCESS` job
4. Confirm processed segments appear in COS and dataset asset list updates
5. Launch one `TRAIN` job
6. Confirm model bundle and index appear in COS
7. Launch one `INFER` job
8. Confirm output audio appears in COS and backend creates output asset

## 10. Useful logs

Worker logs:

```bash
cd /root/ai-music/apps/autodl-worker
tail -f logs/worker.log
```

Per-job logs:

```bash
find runs -maxdepth 2 -type f | sort
```

Typical files:

- `runs/<jobId>/context.json`
- `runs/<jobId>/payload.json`
- `runs/<jobId>/resources.json`
- `runs/<jobId>/progress.json`
- `runs/<jobId>/result_manifest.json`
- `runs/<jobId>/*-stdout.log`
- `runs/<jobId>/*-stderr.log`

## 10. Common issues

`worker registered but never gets jobs`

- check backend node status
- check job type is one of `PROCESS,TRAIN,INFER`
- check worker heartbeat is arriving

`PROCESS works but TRAIN fails`

- check RVC root path
- check `train_nsf_sim_cache_sid_load_pretrain.py` exists
- check pretrained files exist under `pretrained_v2/`

`TRAIN works but no final model in weights/`

- the worker now tries to extract a small final model automatically from `G_*.pth`
- inspect `runs/<jobId>/extract-small-model-stderr.log`

`INFER fails to load model`

- inspect `runs/<jobId>/infer-flat-webui-stderr.log`
- verify the bundled zip contains `.pth`
- verify the index path exists if one was reported

`rmvpe_gpu fails`

- reduce to one GPU id:
  - `AIMUSIC_RVC_RMVPE_GPU_IDS=0`
- or switch to:
  - `f0Method=rmvpe`

## 11. Suggested next improvement

Once the first node is stable, add a tiny launcher script on AutoDL:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /root/ai-music/apps/autodl-worker
set -a
source .env
set +a
exec python3 worker.py
```

Then you can restart the worker with one command after every AutoDL boot.
