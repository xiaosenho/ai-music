package com.aimusic.controlplane.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

public record JobEventResponse(
        Long id,
        UUID jobId,
        UUID nodeId,
        String eventType,
        String message,
        String payload,
        OffsetDateTime createdAt
) {
}

