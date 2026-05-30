package com.aimusic.controlplane.dto;

import java.time.OffsetDateTime;
import java.util.Map;

public record StorageUploadTicketResponse(
        String objectKey,
        String publicUrl,
        String uploadUrl,
        Map<String, String> headers,
        OffsetDateTime expiresAt
) {
}
