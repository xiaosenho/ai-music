package com.aimusic.controlplane.dto;

import java.util.UUID;

public record RegisterWorkerResponse(
        UUID nodeId,
        int heartbeatIntervalSeconds,
        int pullIntervalSeconds,
        boolean accepted
) {
}

