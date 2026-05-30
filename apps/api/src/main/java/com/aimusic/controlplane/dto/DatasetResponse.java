package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.DatasetStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record DatasetResponse(
        UUID id,
        UUID characterId,
        String name,
        DatasetStatus status,
        List<String> assetIds,
        Integer segmentCount,
        String language,
        String note,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}

