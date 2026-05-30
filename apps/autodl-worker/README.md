# AutoDL Worker

`apps/autodl-worker/worker.py` is the execution-plane worker for AutoDL nodes. It handles:

- worker registration
- periodic heartbeat
- job polling
- asset / dataset / model metadata fetch
- resource prefetch into local run directories
- PROCESS / TRAIN / INFER execution
- direct COS upload for weights and inference outputs
- job status reporting and backend metadata callback

## Runtime

- Python `3.8+`
- no third-party Python dependency

## Quick start

```bash
cd apps/autodl-worker
cp .env.example .env
./scripts/start-worker.sh foreground
```

Detached run:

```bash
./scripts/start-worker.sh tmux
```

Check status:

```bash
./scripts/status-worker.sh
```

Stop worker:

```bash
./scripts/stop-worker.sh
```

Install crontab autostart:

```bash
./scripts/install-autostart-cron.sh
```

One-click dependency install on AutoDL:

```bash
bash ./scripts/install-deps.sh
```

## Execution modes

### 1. Mock mode

Mock mode is optional and should only be used for control-plane smoke testing:

```bash
AIMUSIC_WORKER_USE_MOCK_EXECUTOR=true
```

This is useful for control-plane integration testing. The worker will simulate:

- process job completion with `segmentCount`
- train job completion with local files that are auto-uploaded to COS
- infer job completion with local files that are auto-uploaded to COS

### 2. Real command mode

You can plug in real scripts for each job type:

```bash
AIMUSIC_WORKER_USE_MOCK_EXECUTOR=false
AIMUSIC_PROCESS_COMMAND='python3 pipelines/process_job.py --context "{context_path}" --run-dir "{run_dir}"'
AIMUSIC_TRAIN_COMMAND='python3 pipelines/train_job.py --context "{context_path}" --run-dir "{run_dir}"'
AIMUSIC_INFER_COMMAND='python3 pipelines/infer_job.py --context "{context_path}" --run-dir "{run_dir}"'
```

Available placeholders:

- `{job_id}`
- `{job_type}`
- `{worker_dir}`
- `{run_dir}`
- `{context_path}`
- `{payload_path}`
- `{resources_path}`
- `{input_asset_ids}`
- `{dataset_version}`
- `{model_version}`
- `{workflow}`

## Job contract

Before executing a job, the worker writes:

- `runs/<jobId>/context.json`
- `runs/<jobId>/payload.json`
- `runs/<jobId>/resources.json`

During execution, your script can optionally write:

- `runs/<jobId>/progress.json`

Example:

```json
{
  "progressPercent": 45,
  "message": "separating vocals"
}
```

After a successful run, your script can write:

- `runs/<jobId>/result_manifest.json`

Examples:

### PROCESS

```json
{
  "localProcessedFiles": [
    {
      "localPath": "/root/autodl-tmp/job-123/segment-001.wav",
      "fileName": "segment-001.wav",
      "assetType": "AUDIO",
      "language": "zh-CN",
      "note": "processed segment",
      "metadata": {
        "sourceAssetId": "..."
      }
    }
  ],
  "segmentCount": 328
}
```

Worker behavior:

- uploads every `localProcessedFiles[*].localPath` to COS
- rewrites the manifest into `processedAssets`
- backend creates processed asset records from `processedAssets`
- backend updates dataset `assetIds` to processed asset ids

### Built-in real PROCESS pipeline

The repo now includes a real first-pass pipeline at `pipelines/process_job.py`.

Pipeline steps:

- `ffmpeg`: extract / normalize audio to mono wav
- `demucs` or custom `uvr`: optional vocal separation
- `ffmpeg`: high-pass / low-pass / loudness normalize
- `ffmpeg silencedetect`: speech-oriented silence segmentation
- `ffmpeg`: export cleaned segments
- worker: upload segments to COS and report them back as processed assets

Recommended setup on AutoDL:

```bash
cd apps/autodl-worker
cp .env.example .env
./scripts/start-worker.sh tmux
```

Useful env vars:

- `AIMUSIC_PROCESS_OUTPUT_SAMPLE_RATE=40000`
- `AIMUSIC_PROCESS_MIN_SEGMENT_SECONDS=2`
- `AIMUSIC_PROCESS_MAX_SEGMENT_SECONDS=12`
- `AIMUSIC_PROCESS_VOCAL_TOOL=demucs`
- `AIMUSIC_PROCESS_ENABLE_DEMUCS=true`
- `AIMUSIC_PROCESS_DEMUCS_MODEL=htdemucs`
- `AIMUSIC_PROCESS_UVR_COMMAND=...`
- `AIMUSIC_PROCESS_AUDIO_FILTERS=highpass=f=80,lowpass=f=12000,loudnorm=I=-16:TP=-1.5:LRA=11`

When `demucs` is unavailable, the script will skip separation and continue with plain `ffmpeg` processing.

### TRAIN

```json
{
  "localModelPath": "/root/autodl-tmp/job-123/model.pth",
  "localSampleAudioPath": "/root/autodl-tmp/job-123/preview.wav",
  "metrics": {
    "loss": 0.038,
    "epochs": 300
  }
}
```

Worker behavior:

- uploads `localModelPath` to COS
- uploads `localSampleAudioPath` to COS
- rewrites the manifest before reporting:
  - `storagePath=cos://...`
  - `sampleAudioUrl=https://...`

### Built-in real TRAIN pipeline

The repo now includes a real RVC WebUI training wrapper at `pipelines/train_job.py`.

What it does:

- reads prefetched dataset assets and training parameters from worker context
- stages dataset audio into a training workspace
- writes `train_config.json` and `dataset_manifest.json`
- when `AIMUSIC_RVC_TRAIN_COMMAND` is empty, it auto-detects your RVC WebUI layout and uses the matching flow:
  - root-level script layout:
    - `trainset_preprocess_pipeline_print.py`
    - `extract_f0_print.py` or `extract_f0_rmvpe.py`
    - `extract_feature_print.py`
    - `train_nsf_sim_cache_sid_load_pretrain.py`
  - official nested layout:
    - `infer/modules/train/preprocess.py`
    - `infer/modules/train/extract/extract_f0_*.py`
    - `infer/modules/train/extract_feature_print.py`
    - `infer/modules/train/train.py`
  - index build after training
- collects generated `.pth` and optional `.index`
- bundles artifacts into a zip package
- returns:
  - `localModelPath`
  - `localSampleAudioPath`
  - `metrics`

Worker behavior after that:

- uploads the model bundle to COS
- uploads preview audio to COS if present
- reports `storagePath`, `sampleAudioUrl`, `metrics` back to backend

Recommended AutoDL env:

```bash
AIMUSIC_RVC_ROOT_DIR=/Retrieval-based-Voice-Conversion-WebUI
AIMUSIC_RVC_PYTHON_BIN=/root/miniconda3/bin/python
AIMUSIC_RVC_TRAIN_MODE=webui_auto
AIMUSIC_RVC_TRAIN_COMMAND=
```

If your image is not the official repo layout, keep `AIMUSIC_RVC_TRAIN_MODE=webui_auto` disabled and fill `AIMUSIC_RVC_TRAIN_COMMAND` yourself.

Useful placeholders inside `AIMUSIC_RVC_TRAIN_COMMAND` when you override it:

- `{run_dir}`
- `{workspace_dir}`
- `{dataset_dir}`
- `{output_dir}`
- `{context_path}`
- `{train_config_path}`
- `{dataset_manifest_path}`
- `{sample_rate}`
- `{f0_method}`
- `{batch_size}`
- `{total_epoch}`
- `{model_name}`
- `{dataset_id}`
- `{dataset_name}`

Useful tuning env vars:

- `AIMUSIC_TRAIN_DATASET_STAGE_MODE=symlink`
- `AIMUSIC_TRAIN_MODEL_GLOB=*.pth`
- `AIMUSIC_TRAIN_INDEX_GLOB=*.index`
- `AIMUSIC_TRAIN_PREVIEW_GLOB=*.wav`
- `AIMUSIC_TRAIN_BUNDLE_NAME=model-artifacts.zip`
- `AIMUSIC_RVC_ROOT_DIR=/Retrieval-based-Voice-Conversion-WebUI`
- `AIMUSIC_RVC_PYTHON_BIN=/root/miniconda3/bin/python`
- `AIMUSIC_RVC_GPU_IDS=0`
- `AIMUSIC_RVC_RMVPE_GPU_IDS=0-0`
- `AIMUSIC_RVC_DEVICE=cuda:0`
- `AIMUSIC_RVC_VERSION=v2`
- `AIMUSIC_RVC_INDEX_ENABLED=true`

Important:

- `AIMUSIC_RVC_VERSION` means the model architecture version consumed by the repo code.
- In the current upstream RVC WebUI this is still `v1` or `v2`.
- If your AutoDL image is labeled as `RVC v4`, do not automatically change this to `v4` unless your repo actually has `configs/v4` and matching train code.

### INFER

```json
{
  "localOutputPath": "/root/autodl-tmp/job-123/result.wav",
  "outputName": "hanser-demo.wav"
}
```

Worker behavior:

- uploads `localOutputPath` to COS
- rewrites the manifest before reporting:
  - `outputObjectKey=...`
  - `outputUrl=https://...`
  - `outputName=...`

### Built-in real INFER pipeline

The repo now includes a real RVC WebUI inference wrapper at `pipelines/infer_job.py`.

What it does:

- reads prefetched model artifact and input audio from worker context
- if the model artifact is a zip bundle, extracts it automatically
- resolves `.pth` and optional `.index`
- stages input audio into a local workspace
- writes `infer_config.json`
- when `AIMUSIC_RVC_INFER_COMMAND` is empty, it auto-detects your RVC WebUI layout:
  - nested layout: uses `tools/infer_cli.py`
  - root-level infer-web layout: runs an internal Python wrapper that mirrors `get_vc()` + `vc_single()`
- collects the generated output audio
- returns:
  - `localOutputPath`
  - `outputName`
  - `metrics`

Worker behavior after that:

- uploads output audio to COS
- reports `outputObjectKey`, `outputUrl`, `outputName` back to backend

Recommended AutoDL env:

```bash
AIMUSIC_RVC_ROOT_DIR=/Retrieval-based-Voice-Conversion-WebUI
AIMUSIC_RVC_PYTHON_BIN=/root/miniconda3/bin/python
AIMUSIC_RVC_INFER_MODE=webui_auto
AIMUSIC_RVC_INFER_COMMAND=
```

If your image is not the official repo layout, fill `AIMUSIC_RVC_INFER_COMMAND` yourself.

Useful placeholders inside `AIMUSIC_RVC_INFER_COMMAND` when you override it:

- `{run_dir}`
- `{workspace_dir}`
- `{model_bundle_path}`
- `{model_dir}`
- `{model_path}`
- `{index_path}`
- `{input_dir}`
- `{input_path}`
- `{output_dir}`
- `{output_path}`
- `{context_path}`
- `{infer_config_path}`
- `{speaker_id}`
- `{f0_method}`
- `{sample_rate}`
- `{model_name}`

Useful tuning env vars:

- `AIMUSIC_INFER_INPUT_STAGE_MODE=symlink`
- `AIMUSIC_INFER_OUTPUT_GLOB=*.wav`
- `AIMUSIC_INFER_BUNDLE_EXTRACT_DIR_NAME=bundle`
- `AIMUSIC_RVC_INDEX_RATE=0.66`
- `AIMUSIC_RVC_FILTER_RADIUS=3`
- `AIMUSIC_RVC_PROTECT=0.33`

## AutoDL image note

The worker now supports two RVC WebUI families:

- official nested layout:
  - `infer/modules/train/...`
  - `tools/infer_cli.py`
- root-level script layout:
  - `trainset_preprocess_pipeline_print.py`
  - `extract_f0_print.py`
  - `extract_feature_print.py`
  - `train_nsf_sim_cache_sid_load_pretrain.py`
  - `infer-web.py`

So if your AutoDL image is based on the newer root-level `infer-web.py` workflow, you can still keep `AIMUSIC_RVC_TRAIN_COMMAND=` and `AIMUSIC_RVC_INFER_COMMAND=` empty and let the worker auto-detect it.

## Example scripts

You can use the demo scripts in `examples/` for local smoke testing:

```bash
AIMUSIC_WORKER_USE_MOCK_EXECUTOR=false
AIMUSIC_PROCESS_COMMAND='python3 examples/mock_process_job.py "{context_path}" "{run_dir}"'
AIMUSIC_TRAIN_COMMAND='python3 examples/mock_train_job.py "{context_path}" "{run_dir}"'
AIMUSIC_INFER_COMMAND='python3 examples/mock_infer_job.py "{context_path}" "{run_dir}"'
```
