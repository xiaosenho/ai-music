package com.aimusic.controlplane.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import java.util.List;
import java.util.UUID;

public record CreateDatasetRequest(
        UUID characterId,
        @NotBlank String name,
        @NotEmpty List<String> assetIds,
        Integer segmentCount,
        String language,
        String note
) {
}

