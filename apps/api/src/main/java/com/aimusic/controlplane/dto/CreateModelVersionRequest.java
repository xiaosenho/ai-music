package com.aimusic.controlplane.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.UUID;

public record CreateModelVersionRequest(
        UUID characterId,
        UUID datasetId,
        UUID trainingJobId,
        @NotBlank String name,
        @NotBlank String modelType,
        String storagePath,
        String sampleAudioUrl,
        String metrics,
        String note
) {
}

