package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.ModelVersionStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record ModelVersionResponse(
        UUID id,
        UUID characterId,
        UUID datasetId,
        UUID trainingJobId,
        String name,
        ModelVersionStatus status,
        String modelType,
        String storagePath,
        String sampleAudioUrl,
        String metrics,
        String note,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
