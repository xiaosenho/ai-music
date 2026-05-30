package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.AssetType;
import java.time.OffsetDateTime;
import java.util.Map;

public record PrepareDirectUploadResponse(
        String fileName,
        AssetType assetType,
        String objectKey,
        String publicUrl,
        String uploadUrl,
        Map<String, String> headers,
        OffsetDateTime expiresAt
) {
}
