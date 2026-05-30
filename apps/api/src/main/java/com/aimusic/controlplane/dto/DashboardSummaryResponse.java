package com.aimusic.controlplane.dto;

import java.util.List;

public record DashboardSummaryResponse(
        long totalWorkers,
        long onlineWorkers,
        long busyWorkers,
        long totalJobs,
        long queuedJobs,
        long runningJobs,
        long failedJobs,
        List<StatusCountResponse> workerStatusCounts,
        List<StatusCountResponse> jobStatusCounts,
        List<StatusCountResponse> jobTypeCounts
) {
}
