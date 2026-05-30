package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.AssetStatus;
import com.aimusic.controlplane.model.AssetType;
import java.time.OffsetDateTime;
import java.util.UUID;

public record MediaAssetResponse(
        UUID id,
        UUID characterId,
        String name,
        AssetType assetType,
        AssetStatus status,
        String sourceUri,
        String objectKey,
        Integer durationSeconds,
        String language,
        String metadata,
        String note,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}

