package com.aimusic.controlplane.controller;

import com.aimusic.controlplane.dto.CreateJobRequest;
import com.aimusic.controlplane.dto.JobEventResponse;
import com.aimusic.controlplane.dto.JobResponse;
import com.aimusic.controlplane.dto.PullJobRequest;
import com.aimusic.controlplane.dto.PullJobResponse;
import com.aimusic.controlplane.dto.ReportJobStatusRequest;
import com.aimusic.controlplane.service.JobService;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/jobs")
public class JobController {

    private final JobService jobService;

    public JobController(JobService jobService) {
        this.jobService = jobService;
    }

    @PostMapping
    public JobResponse create(@Valid @RequestBody CreateJobRequest request) {
        return jobService.createJob(request);
    }

    @PostMapping("/pull")
    public PullJobResponse pull(@Valid @RequestBody PullJobRequest request) {
        return jobService.pullJob(request);
    }

    @PostMapping("/{jobId}/report")
    public JobResponse report(
            @PathVariable UUID jobId,
            @Valid @RequestBody ReportJobStatusRequest request
    ) {
        return jobService.reportStatus(jobId, request);
    }

    @GetMapping
    public List<JobResponse> listJobs() {
        return jobService.listJobs();
    }

    @GetMapping("/{jobId}")
    public JobResponse get(@PathVariable UUID jobId) {
        return jobService.getJob(jobId);
    }

    @GetMapping("/{jobId}/events")
    public List<JobEventResponse> listEvents(@PathVariable UUID jobId) {
        return jobService.listJobEvents(jobId);
    }
}
