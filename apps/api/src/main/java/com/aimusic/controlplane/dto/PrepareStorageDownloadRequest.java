package com.aimusic.controlplane.dto;

import jakarta.validation.constraints.NotBlank;

public record PrepareStorageDownloadRequest(
        @NotBlank String objectKey
) {
}
