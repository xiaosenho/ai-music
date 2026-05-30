package com.aimusic.controlplane.model;

public enum JobStatus {
    PENDING,
    QUEUED,
    LEASED,
    RUNNING,
    UPLOADING,
    SUCCEEDED,
    FAILED,
    RETRY_WAITING,
    CANCELLED
}

