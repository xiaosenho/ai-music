package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.JobType;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import java.util.UUID;

public record PullJobRequest(
        @NotNull UUID nodeId,
        @NotEmpty List<JobType> supportedJobTypes
) {
}

