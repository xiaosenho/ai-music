package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.AssetType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record PrepareDirectUploadRequest(
        @NotBlank String fileName,
        @NotNull AssetType assetType,
        String contentType,
        Long sizeBytes,
        String language,
        String note
) {
}
