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
set -a
source .env
set +a
python3 worker.py
```

## Execution modes

### 1. Mock mode

Default mode is mock execution:

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
AIMUSIC_PROCESS_COMMAND='python3 /root/pipelines/process_job.py --context "{context_path}" --run-dir "{run_dir}"'
AIMUSIC_TRAIN_COMMAND='bash /root/pipelines/train_rvc.sh "{context_path}" "{run_dir}"'
AIMUSIC_INFER_COMMAND='python3 /root/pipelines/infer_job.py --context "{context_path}" --run-dir "{run_dir}"'
```

Available placeholders:

- `{job_id}`
- `{job_type}`
- `{run_dir}`
- `{context_path}`
- `{payload_path}`
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
  "segmentCount": 328
}
```

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

## Example scripts

You can use the demo scripts in `examples/` for local smoke testing:

```bash
AIMUSIC_WORKER_USE_MOCK_EXECUTOR=false
AIMUSIC_PROCESS_COMMAND='python3 examples/mock_process_job.py "{context_path}" "{run_dir}"'
AIMUSIC_TRAIN_COMMAND='python3 examples/mock_train_job.py "{context_path}" "{run_dir}"'
AIMUSIC_INFER_COMMAND='python3 examples/mock_infer_job.py "{context_path}" "{run_dir}"'
```
