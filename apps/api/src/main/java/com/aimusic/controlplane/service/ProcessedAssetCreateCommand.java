package com.aimusic.controlplane.service;

import com.aimusic.controlplane.model.AssetType;
import java.util.Map;

public record ProcessedAssetCreateCommand(
        String name,
        AssetType assetType,
        String objectKey,
        String sourceUri,
        Integer durationSeconds,
        String language,
        String note,
        Map<String, Object> metadata
) {
}
