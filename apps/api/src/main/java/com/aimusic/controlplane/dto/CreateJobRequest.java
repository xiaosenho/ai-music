package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.ExecutionMode;
import com.aimusic.controlplane.model.JobType;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record CreateJobRequest(
        UUID characterId,
        @NotNull JobType jobType,
        @NotNull ExecutionMode executionMode,
        Integer priority,
        UUID targetNodeId,
        List<String> inputAssetIds,
        String datasetVersion,
        String modelVersion,
        Integer sampleRate,
        String f0Method,
        Integer batchSize,
        Integer totalEpoch,
        String speakerId,
        Integer maxRetries,
        String note,
        Map<String, Object> payload
) {
}

