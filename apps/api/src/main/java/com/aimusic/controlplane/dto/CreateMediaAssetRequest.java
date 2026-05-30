package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.AssetType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.Map;
import java.util.UUID;

public record CreateMediaAssetRequest(
        UUID characterId,
        @NotBlank String name,
        @NotNull AssetType assetType,
        String sourceUri,
        String objectKey,
        Integer durationSeconds,
        String language,
        String note,
        Map<String, Object> metadata
) {
}

