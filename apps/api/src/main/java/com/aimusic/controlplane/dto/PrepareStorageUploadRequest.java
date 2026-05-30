package com.aimusic.controlplane.dto;

import jakarta.validation.constraints.NotBlank;

public record PrepareStorageUploadRequest(
        @NotBlank String fileName,
        @NotBlank String category
) {
}
