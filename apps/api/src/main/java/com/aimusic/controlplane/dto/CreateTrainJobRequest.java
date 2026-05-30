package com.aimusic.controlplane.dto;

import jakarta.validation.constraints.NotBlank;

public record CreateTrainJobRequest(
        @NotBlank String modelName,
        @NotBlank String modelType,
        Integer sampleRate,
        String f0Method,
        Integer batchSize,
        Integer totalEpoch,
        String note
) {
}

