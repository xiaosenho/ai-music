package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.NodeStatus;
import com.aimusic.controlplane.model.NodeType;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record WorkerNodeResponse(
        UUID nodeId,
        NodeType nodeType,
        String hostname,
        String provider,
        String gpuName,
        Integer gpuCount,
        Integer vramMb,
        NodeStatus status,
        List<String> supportedJobTypes,
        String workerVersion,
        UUID runningJobId,
        OffsetDateTime lastSeenAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}

