package com.aimusic.controlplane.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import java.util.List;

public record CreateProcessJobRequest(
        @NotEmpty List<String> assetIds,
        @NotBlank String datasetName,
        String language,
        String note
) {
}

