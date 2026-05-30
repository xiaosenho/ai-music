package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.AssetType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.Map;

public record CompleteDirectUploadRequest(
        @NotBlank String fileName,
        @NotNull AssetType assetType,
        @NotBlank String objectKey,
        String contentType,
        Long sizeBytes,
        Integer durationSeconds,
        String language,
        String note,
        Map<String, Object> metadata
) {
}
