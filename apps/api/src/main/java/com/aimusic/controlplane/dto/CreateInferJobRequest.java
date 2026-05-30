package com.aimusic.controlplane.dto;

import com.aimusic.controlplane.model.ExecutionMode;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.List;

public record CreateInferJobRequest(
        @NotEmpty List<String> inputAssetIds,
        @NotNull ExecutionMode executionMode,
        String note
) {
}
