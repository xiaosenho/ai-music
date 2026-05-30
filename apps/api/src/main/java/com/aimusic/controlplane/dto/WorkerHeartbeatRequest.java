package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.NodeStatus;
import jakarta.validation.constraints.NotNull;
import java.util.Map;
import java.util.UUID;

public record WorkerHeartbeatRequest(
        @NotNull UUID nodeId,
        @NotNull NodeStatus status,
        UUID runningJobId,
        Map<String, Object> payload
) {
}

