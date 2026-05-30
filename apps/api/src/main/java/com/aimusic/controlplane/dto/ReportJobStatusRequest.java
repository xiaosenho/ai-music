package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.JobStatus;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import java.util.Map;
import java.util.UUID;

public record ReportJobStatusRequest(
        @NotNull UUID nodeId,
        @NotNull JobStatus status,
        @Min(0) @Max(100) Integer progressPercent,
        String message,
        String errorMessage,
        Map<String, Object> resultManifest
) {
}

