CREATE TABLE worker_nodes (
    node_id UUID PRIMARY KEY,
    node_type VARCHAR(32) NOT NULL,
    hostname VARCHAR(255),
    provider VARCHAR(64),
    gpu_name VARCHAR(255),
    gpu_count INTEGER NOT NULL DEFAULT 0,
    vram_mb INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    supported_job_types TEXT NOT NULL,
    worker_version VARCHAR(64),
    running_job_id UUID,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE worker_heartbeats (
    id BIGSERIAL PRIMARY KEY,
    node_id UUID NOT NULL REFERENCES worker_nodes (node_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL,
    running_job_id UUID,
    payload TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    character_id UUID,
    job_type VARCHAR(32) NOT NULL,
    execution_mode VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    target_node_id UUID,
    assigned_node_id UUID,
    input_asset_ids TEXT NOT NULL,
    dataset_version VARCHAR(128),
    model_version VARCHAR(128),
    sample_rate INTEGER,
    f0_method VARCHAR(64),
    batch_size INTEGER,
    total_epoch INTEGER,
    speaker_id VARCHAR(64),
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    payload TEXT,
    result_manifest TEXT,
    note TEXT,
    error_message TEXT,
    lease_expires_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jobs_status_priority ON jobs (status, priority DESC, created_at ASC);
CREATE INDEX idx_jobs_assigned_node_id ON jobs (assigned_node_id);
CREATE INDEX idx_jobs_target_node_id ON jobs (target_node_id);

CREATE TABLE job_events (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    node_id UUID,
    event_type VARCHAR(32) NOT NULL,
    message TEXT,
    payload TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

