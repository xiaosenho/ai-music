package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.ExecutionMode;
import com.aimusic.controlplane.model.JobStatus;
import com.aimusic.controlplane.model.JobType;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record JobResponse(
        UUID id,
        UUID characterId,
        JobType jobType,
        ExecutionMode executionMode,
        JobStatus status,
        Integer priority,
        UUID targetNodeId,
        UUID assignedNodeId,
        List<String> inputAssetIds,
        String datasetVersion,
        String modelVersion,
        Integer sampleRate,
        String f0Method,
        Integer batchSize,
        Integer totalEpoch,
        String speakerId,
        Integer retryCount,
        Integer progressPercent,
        String payload,
        String resultManifest,
        String note,
        String errorMessage,
        OffsetDateTime leaseExpiresAt,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}

