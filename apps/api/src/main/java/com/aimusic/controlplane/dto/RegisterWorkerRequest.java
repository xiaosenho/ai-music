package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.JobType;
import com.aimusic.controlplane.model.NodeStatus;
import com.aimusic.controlplane.model.NodeType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import java.util.UUID;

public record RegisterWorkerRequest(
        UUID nodeId,
        @NotNull NodeType nodeType,
        @NotBlank String hostname,
        @NotBlank String provider,
        String gpuName,
        Integer gpuCount,
        Integer vramMb,
        @NotEmpty List<JobType> supportedJobTypes,
        String workerVersion,
        NodeStatus status
) {
}

