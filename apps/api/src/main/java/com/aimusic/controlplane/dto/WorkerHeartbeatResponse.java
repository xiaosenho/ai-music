package com.aimusic.controlplane.dto;

import java.time.OffsetDateTime;

public record WorkerHeartbeatResponse(
        OffsetDateTime serverTime,
        boolean accepted
) {
}

