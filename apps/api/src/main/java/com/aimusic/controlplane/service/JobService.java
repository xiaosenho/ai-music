package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.CreateJobRequest;
import com.aimusic.controlplane.dto.JobEventResponse;
import com.aimusic.controlplane.dto.JobResponse;
import com.aimusic.controlplane.dto.PullJobRequest;
import com.aimusic.controlplane.dto.PullJobResponse;
import com.aimusic.controlplane.dto.ReportJobStatusRequest;
import com.aimusic.controlplane.entity.Job;
import com.aimusic.controlplane.entity.JobEvent;
import com.aimusic.controlplane.entity.WorkerNode;
import com.aimusic.controlplane.exception.NotFoundException;
import com.aimusic.controlplane.model.ExecutionMode;
import com.aimusic.controlplane.model.JobStatus;
import com.aimusic.controlplane.model.JobType;
import com.aimusic.controlplane.model.NodeStatus;
import com.aimusic.controlplane.model.NodeType;
import com.aimusic.controlplane.repository.JobEventRepository;
import com.aimusic.controlplane.repository.JobRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class JobService {

    private final JobRepository jobRepository;
    private final JobEventRepository jobEventRepository;
    private final WorkerService workerService;
    private final WorkflowResultService workflowResultService;
    private final ObjectMapper objectMapper;
    private final int jobLeaseSeconds;

    public JobService(
            JobRepository jobRepository,
            JobEventRepository jobEventRepository,
            WorkerService workerService,
            WorkflowResultService workflowResultService,
            ObjectMapper objectMapper,
            @Value("${aimusic.worker.job-lease-seconds}") int jobLeaseSeconds
    ) {
        this.jobRepository = jobRepository;
        this.jobEventRepository = jobEventRepository;
        this.workerService = workerService;
        this.workflowResultService = workflowResultService;
        this.objectMapper = objectMapper;
        this.jobLeaseSeconds = jobLeaseSeconds;
    }

    @Transactional
    public JobResponse createJob(CreateJobRequest request) {
        Job job = new Job();
        job.setId(UUID.randomUUID());
        job.setCharacterId(request.characterId());
        job.setJobType(request.jobType());
        job.setExecutionMode(request.executionMode());
        job.setStatus(JobStatus.QUEUED);
        job.setPriority(request.priority() == null ? 0 : request.priority());
        job.setTargetNodeId(request.targetNodeId());
        job.setInputAssetIds(request.inputAssetIds());
        job.setDatasetVersion(request.datasetVersion());
        job.setModelVersion(request.modelVersion());
        job.setSampleRate(request.sampleRate());
        job.setF0Method(request.f0Method());
        job.setBatchSize(request.batchSize());
        job.setTotalEpoch(request.totalEpoch());
        job.setSpeakerId(request.speakerId());
        job.setMaxRetries(request.maxRetries() == null ? 3 : request.maxRetries());
        job.setNote(request.note());
        job.setPayload(serialize(request.payload()));
        jobRepository.save(job);
        saveEvent(job.getId(), null, "JOB_CREATED", "Job created", request.payload());
        return toResponse(job);
    }

    @Transactional
    public PullJobResponse pullJob(PullJobRequest request) {
        WorkerNode workerNode = workerService.getRequiredNode(request.nodeId());
        NodeStatus effectiveStatus = workerService.resolveEffectiveStatus(workerNode);
        if (effectiveStatus == NodeStatus.OFFLINE
                || effectiveStatus == NodeStatus.BUSY
                || effectiveStatus == NodeStatus.DRAINING) {
            return new PullJobResponse(false, null);
        }

        List<Job> candidates = jobRepository.findCandidatesForLease(
                EnumSet.of(JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RETRY_WAITING),
                PageRequest.of(0, 20)
        );

        for (Job candidate : candidates) {
            if (!isCompatible(candidate, workerNode)) {
                continue;
            }

            candidate.setAssignedNodeId(workerNode.getNodeId());
            candidate.setStatus(JobStatus.LEASED);
            candidate.setLeaseExpiresAt(OffsetDateTime.now().plusSeconds(jobLeaseSeconds));
            jobRepository.save(candidate);
            workerService.markNodeRunning(workerNode.getNodeId(), candidate.getId());
            saveEvent(candidate.getId(), workerNode.getNodeId(), "JOB_LEASED", "Job leased to worker", null);
            return new PullJobResponse(true, toResponse(candidate));
        }

        return new PullJobResponse(false, null);
    }

    @Transactional
    public JobResponse reportStatus(UUID jobId, ReportJobStatusRequest request) {
        Job job = jobRepository.findById(jobId)
                .orElseThrow(() -> new NotFoundException("Job not found: " + jobId));

        if (job.getAssignedNodeId() != null && !job.getAssignedNodeId().equals(request.nodeId())) {
            throw new IllegalArgumentException("Job is assigned to another node");
        }

        job.setStatus(request.status());
        if (request.progressPercent() != null) {
            job.setProgressPercent(request.progressPercent());
        }
        if (request.errorMessage() != null) {
            job.setErrorMessage(request.errorMessage());
        }
        if (request.resultManifest() != null) {
            job.setResultManifest(serialize(request.resultManifest()));
        }

        workflowResultService.handle(job, job.getStatus(), request.resultManifest());

        if (request.status() == JobStatus.RUNNING && job.getStartedAt() == null) {
            job.setStartedAt(OffsetDateTime.now());
        }

        boolean canRetry = request.status() == JobStatus.FAILED && job.getRetryCount() < job.getMaxRetries();

        if (canRetry) {
            job.setRetryCount(job.getRetryCount() + 1);
            job.setStatus(JobStatus.RETRY_WAITING);
            job.setAssignedNodeId(null);
            job.setLeaseExpiresAt(null);
            workerService.markNodeIdle(request.nodeId());
        } else if (isTerminal(request.status())) {
            job.setFinishedAt(OffsetDateTime.now());
            job.setLeaseExpiresAt(null);
            workerService.markNodeIdle(request.nodeId());
        }

        jobRepository.save(job);
        saveEvent(job.getId(), request.nodeId(), job.getStatus().name(), request.message(), request.resultManifest());
        return toResponse(job);
    }

    @Transactional(readOnly = true)
    public List<JobResponse> listJobs() {
        return jobRepository.findAllByOrderByCreatedAtDesc().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    @Transactional(readOnly = true)
    public JobResponse getJob(UUID jobId) {
        return toResponse(jobRepository.findById(jobId)
                .orElseThrow(() -> new NotFoundException("Job not found: " + jobId)));
    }

    @Transactional(readOnly = true)
    public List<JobEventResponse> listJobEvents(UUID jobId) {
        if (!jobRepository.existsById(jobId)) {
            throw new NotFoundException("Job not found: " + jobId);
        }
        return jobEventRepository.findByJobIdOrderByCreatedAtAsc(jobId).stream()
                .map(event -> new JobEventResponse(
                        event.getId(),
                        event.getJobId(),
                        event.getNodeId(),
                        event.getEventType(),
                        event.getMessage(),
                        event.getPayload(),
                        event.getCreatedAt()
                ))
                .toList();
    }

    private boolean isCompatible(Job job, WorkerNode workerNode) {
        JobType jobType = job.getJobType();
        if (!workerNode.supports(jobType)) {
            return false;
        }

        if (job.getTargetNodeId() != null && !job.getTargetNodeId().equals(workerNode.getNodeId())) {
            return false;
        }

        if (jobType == JobType.PROCESS || jobType == JobType.TRAIN) {
            return workerNode.getNodeType() == NodeType.AUTODL;
        }

        return switch (job.getExecutionMode()) {
            case CLOUD -> workerNode.getNodeType() == NodeType.AUTODL;
            case LOCAL -> workerNode.getNodeType() == NodeType.CLIENT_LOCAL;
            case AUTO -> true;
        };
    }

    private boolean isTerminal(JobStatus status) {
        return status == JobStatus.SUCCEEDED || status == JobStatus.FAILED || status == JobStatus.CANCELLED;
    }

    private void saveEvent(UUID jobId, UUID nodeId, String eventType, String message, Object payload) {
        JobEvent event = new JobEvent();
        event.setJobId(jobId);
        event.setNodeId(nodeId);
        event.setEventType(eventType);
        event.setMessage(message);
        event.setPayload(serialize(payload));
        jobEventRepository.save(event);
    }

    private String serialize(Object payload) {
        if (payload == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalArgumentException("Failed to serialize payload", exception);
        }
    }

    private JobResponse toResponse(Job job) {
        return new JobResponse(
                job.getId(),
                job.getCharacterId(),
                job.getJobType(),
                job.getExecutionMode(),
                job.getStatus(),
                job.getPriority(),
                job.getTargetNodeId(),
                job.getAssignedNodeId(),
                job.getInputAssetIds(),
                job.getDatasetVersion(),
                job.getModelVersion(),
                job.getSampleRate(),
                job.getF0Method(),
                job.getBatchSize(),
                job.getTotalEpoch(),
                job.getSpeakerId(),
                job.getRetryCount(),
                job.getProgressPercent(),
                job.getPayload(),
                job.getResultManifest(),
                job.getNote(),
                job.getErrorMessage(),
                job.getLeaseExpiresAt(),
                job.getStartedAt(),
                job.getFinishedAt(),
                job.getCreatedAt(),
                job.getUpdatedAt()
        );
    }
}
