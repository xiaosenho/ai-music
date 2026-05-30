package com.aimusic.controlplane.entity;

import com.aimusic.controlplane.converter.StringListJsonConverter;
import com.aimusic.controlplane.model.JobType;
import com.aimusic.controlplane.model.NodeStatus;
import com.aimusic.controlplane.model.NodeType;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "worker_nodes")
public class WorkerNode {

    @Id
    @Column(name = "node_id", nullable = false, updatable = false)
    private UUID nodeId;

    @Enumerated(EnumType.STRING)
    @Column(name = "node_type", nullable = false, length = 32)
    private NodeType nodeType;

    @Column(name = "hostname")
    private String hostname;

    @Column(name = "provider", length = 64)
    private String provider;

    @Column(name = "gpu_name")
    private String gpuName;

    @Column(name = "gpu_count", nullable = false)
    private Integer gpuCount = 0;

    @Column(name = "vram_mb", nullable = false)
    private Integer vramMb = 0;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private NodeStatus status = NodeStatus.IDLE;

    @Convert(converter = StringListJsonConverter.class)
    @Column(name = "supported_job_types", nullable = false, columnDefinition = "TEXT")
    private List<String> supportedJobTypes = new ArrayList<>();

    @Column(name = "worker_version", length = 64)
    private String workerVersion;

    @Column(name = "running_job_id")
    private UUID runningJobId;

    @Column(name = "last_seen_at")
    private OffsetDateTime lastSeenAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @PrePersist
    public void onCreate() {
        OffsetDateTime now = OffsetDateTime.now();
        this.createdAt = now;
        this.updatedAt = now;
    }

    @PreUpdate
    public void onUpdate() {
        this.updatedAt = OffsetDateTime.now();
    }

    public boolean supports(JobType jobType) {
        return supportedJobTypes.contains(jobType.name());
    }

    public UUID getNodeId() {
        return nodeId;
    }

    public void setNodeId(UUID nodeId) {
        this.nodeId = nodeId;
    }

    public NodeType getNodeType() {
        return nodeType;
    }

    public void setNodeType(NodeType nodeType) {
        this.nodeType = nodeType;
    }

    public String getHostname() {
        return hostname;
    }

    public void setHostname(String hostname) {
        this.hostname = hostname;
    }

    public String getProvider() {
        return provider;
    }

    public void setProvider(String provider) {
        this.provider = provider;
    }

    public String getGpuName() {
        return gpuName;
    }

    public void setGpuName(String gpuName) {
        this.gpuName = gpuName;
    }

    public Integer getGpuCount() {
        return gpuCount;
    }

    public void setGpuCount(Integer gpuCount) {
        this.gpuCount = gpuCount;
    }

    public Integer getVramMb() {
        return vramMb;
    }

    public void setVramMb(Integer vramMb) {
        this.vramMb = vramMb;
    }

    public NodeStatus getStatus() {
        return status;
    }

    public void setStatus(NodeStatus status) {
        this.status = status;
    }

    public List<String> getSupportedJobTypes() {
        return supportedJobTypes;
    }

    public void setSupportedJobTypes(List<String> supportedJobTypes) {
        this.supportedJobTypes = supportedJobTypes == null ? new ArrayList<>() : supportedJobTypes;
    }

    public String getWorkerVersion() {
        return workerVersion;
    }

    public void setWorkerVersion(String workerVersion) {
        this.workerVersion = workerVersion;
    }

    public UUID getRunningJobId() {
        return runningJobId;
    }

    public void setRunningJobId(UUID runningJobId) {
        this.runningJobId = runningJobId;
    }

    public OffsetDateTime getLastSeenAt() {
        return lastSeenAt;
    }

    public void setLastSeenAt(OffsetDateTime lastSeenAt) {
        this.lastSeenAt = lastSeenAt;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}

