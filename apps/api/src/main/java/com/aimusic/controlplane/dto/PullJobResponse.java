package com.aimusic.controlplane.dto;

public record PullJobResponse(
        boolean assigned,
        JobResponse job
) {
}

