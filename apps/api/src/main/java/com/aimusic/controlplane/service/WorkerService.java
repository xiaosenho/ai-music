package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.RegisterWorkerRequest;
import com.aimusic.controlplane.dto.RegisterWorkerResponse;
import com.aimusic.controlplane.dto.WorkerHeartbeatRequest;
import com.aimusic.controlplane.dto.WorkerHeartbeatResponse;
import com.aimusic.controlplane.dto.WorkerNodeResponse;
import com.aimusic.controlplane.entity.WorkerHeartbeat;
import com.aimusic.controlplane.entity.WorkerNode;
import com.aimusic.controlplane.exception.NotFoundException;
import com.aimusic.controlplane.model.NodeStatus;
import com.aimusic.controlplane.repository.WorkerHeartbeatRepository;
import com.aimusic.controlplane.repository.WorkerNodeRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WorkerService {

    private final WorkerNodeRepository workerNodeRepository;
    private final WorkerHeartbeatRepository workerHeartbeatRepository;
    private final ObjectMapper objectMapper;
    private final int heartbeatIntervalSeconds;
    private final int pullIntervalSeconds;

    public WorkerService(
            WorkerNodeRepository workerNodeRepository,
            WorkerHeartbeatRepository workerHeartbeatRepository,
            ObjectMapper objectMapper,
            @Value("${aimusic.worker.heartbeat-interval-seconds}") int heartbeatIntervalSeconds,
            @Value("${aimusic.worker.pull-interval-seconds}") int pullIntervalSeconds
    ) {
        this.workerNodeRepository = workerNodeRepository;
        this.workerHeartbeatRepository = workerHeartbeatRepository;
        this.objectMapper = objectMapper;
        this.heartbeatIntervalSeconds = heartbeatIntervalSeconds;
        this.pullIntervalSeconds = pullIntervalSeconds;
    }

    @Transactional
    public RegisterWorkerResponse register(RegisterWorkerRequest request) {
        UUID nodeId = request.nodeId() == null ? UUID.randomUUID() : request.nodeId();
        WorkerNode workerNode = workerNodeRepository.findById(nodeId).orElseGet(WorkerNode::new);

        workerNode.setNodeId(nodeId);
        workerNode.setNodeType(request.nodeType());
        workerNode.setHostname(request.hostname());
        workerNode.setProvider(request.provider());
        workerNode.setGpuName(request.gpuName());
        workerNode.setGpuCount(request.gpuCount() == null ? 0 : request.gpuCount());
        workerNode.setVramMb(request.vramMb() == null ? 0 : request.vramMb());
        workerNode.setSupportedJobTypes(request.supportedJobTypes().stream().map(Enum::name).toList());
        workerNode.setWorkerVersion(request.workerVersion());
        workerNode.setStatus(request.status() == null ? NodeStatus.IDLE : request.status());
        workerNode.setLastSeenAt(OffsetDateTime.now());
        workerNodeRepository.save(workerNode);

        return new RegisterWorkerResponse(nodeId, heartbeatIntervalSeconds, pullIntervalSeconds, true);
    }

    @Transactional
    public WorkerHeartbeatResponse heartbeat(WorkerHeartbeatRequest request) {
        WorkerNode workerNode = workerNodeRepository.findById(request.nodeId())
                .orElseThrow(() -> new NotFoundException("Worker node not found: " + request.nodeId()));

        workerNode.setStatus(request.status());
        workerNode.setRunningJobId(request.runningJobId());
        workerNode.setLastSeenAt(OffsetDateTime.now());
        workerNodeRepository.save(workerNode);

        WorkerHeartbeat heartbeat = new WorkerHeartbeat();
        heartbeat.setNodeId(request.nodeId());
        heartbeat.setStatus(request.status());
        heartbeat.setRunningJobId(request.runningJobId());
        heartbeat.setPayload(serialize(request.payload()));
        workerHeartbeatRepository.save(heartbeat);

        return new WorkerHeartbeatResponse(OffsetDateTime.now(), true);
    }

    @Transactional(readOnly = true)
    public List<WorkerNodeResponse> listWorkers() {
        return workerNodeRepository.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
    }

    @Transactional
    public void markNodeRunning(UUID nodeId, UUID jobId) {
        WorkerNode workerNode = workerNodeRepository.findById(nodeId)
                .orElseThrow(() -> new NotFoundException("Worker node not found: " + nodeId));
        workerNode.setRunningJobId(jobId);
        workerNode.setStatus(NodeStatus.BUSY);
        workerNode.setLastSeenAt(OffsetDateTime.now());
        workerNodeRepository.save(workerNode);
    }

    @Transactional
    public void markNodeIdle(UUID nodeId) {
        WorkerNode workerNode = workerNodeRepository.findById(nodeId)
                .orElseThrow(() -> new NotFoundException("Worker node not found: " + nodeId));
        workerNode.setRunningJobId(null);
        workerNode.setStatus(NodeStatus.IDLE);
        workerNode.setLastSeenAt(OffsetDateTime.now());
        workerNodeRepository.save(workerNode);
    }

    @Transactional(readOnly = true)
    public WorkerNode getRequiredNode(UUID nodeId) {
        return workerNodeRepository.findById(nodeId)
                .orElseThrow(() -> new NotFoundException("Worker node not found: " + nodeId));
    }

    @Transactional
    public WorkerNodeResponse updateNodeStatus(UUID nodeId, NodeStatus status) {
        WorkerNode workerNode = getRequiredNode(nodeId);
        workerNode.setStatus(status);
        if (status != NodeStatus.BUSY) {
            workerNode.setRunningJobId(null);
        }
        workerNode.setLastSeenAt(OffsetDateTime.now());
        workerNodeRepository.save(workerNode);
        return toResponse(workerNode);
    }

    private WorkerNodeResponse toResponse(WorkerNode workerNode) {
        return new WorkerNodeResponse(
                workerNode.getNodeId(),
                workerNode.getNodeType(),
                workerNode.getHostname(),
                workerNode.getProvider(),
                workerNode.getGpuName(),
                workerNode.getGpuCount(),
                workerNode.getVramMb(),
                workerNode.getStatus(),
                workerNode.getSupportedJobTypes(),
                workerNode.getWorkerVersion(),
                workerNode.getRunningJobId(),
                workerNode.getLastSeenAt(),
                workerNode.getCreatedAt(),
                workerNode.getUpdatedAt()
        );
    }

    private String serialize(Object payload) {
        if (payload == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException exception) {
            throw new IllegalArgumentException("Failed to serialize worker payload", exception);
        }
    }
}
