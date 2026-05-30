package com.aimusic.controlplane.dto;

import java.time.OffsetDateTime;

public record DirectDownloadTicketResponse(
        String objectKey,
        String downloadUrl,
        OffsetDateTime expiresAt
) {
}
