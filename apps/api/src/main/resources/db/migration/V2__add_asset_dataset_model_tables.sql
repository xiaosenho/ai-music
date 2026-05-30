CREATE TABLE media_assets (
    id UUID PRIMARY KEY,
    character_id UUID,
    name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    source_uri TEXT,
    object_key TEXT,
    duration_seconds INTEGER,
    language VARCHAR(32),
    metadata TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_media_assets_status_created_at ON media_assets (status, created_at DESC);

CREATE TABLE datasets (
    id UUID PRIMARY KEY,
    character_id UUID,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL,
    asset_ids TEXT NOT NULL,
    segment_count INTEGER NOT NULL DEFAULT 0,
    language VARCHAR(32),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_datasets_status_created_at ON datasets (status, created_at DESC);

CREATE TABLE model_versions (
    id UUID PRIMARY KEY,
    character_id UUID,
    dataset_id UUID REFERENCES datasets (id) ON DELETE SET NULL,
    training_job_id UUID REFERENCES jobs (id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL,
    model_type VARCHAR(64) NOT NULL,
    storage_path TEXT,
    sample_audio_url TEXT,
    metrics TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_model_versions_status_created_at ON model_versions (status, created_at DESC);
