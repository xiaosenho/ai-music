package com.aimusic.controlplane.entity;

import com.aimusic.controlplane.converter.StringListJsonConverter;
import com.aimusic.controlplane.model.ExecutionMode;
import com.aimusic.controlplane.model.JobStatus;
import com.aimusic.controlplane.model.JobType;
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
@Table(name = "jobs")
public class Job {

    @Id
    @Column(nullable = false, updatable = false)
    private UUID id;

    @Column(name = "character_id")
    private UUID characterId;

    @Enumerated(EnumType.STRING)
    @Column(name = "job_type", nullable = false, length = 32)
    private JobType jobType;

    @Enumerated(EnumType.STRING)
    @Column(name = "execution_mode", nullable = false, length = 32)
    private ExecutionMode executionMode;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 32)
    private JobStatus status;

    @Column(name = "priority", nullable = false)
    private Integer priority = 0;

    @Column(name = "target_node_id")
    private UUID targetNodeId;

    @Column(name = "assigned_node_id")
    private UUID assignedNodeId;

    @Convert(converter = StringListJsonConverter.class)
    @Column(name = "input_asset_ids", nullable = false, columnDefinition = "TEXT")
    private List<String> inputAssetIds = new ArrayList<>();

    @Column(name = "dataset_version", length = 128)
    private String datasetVersion;

    @Column(name = "model_version", length = 128)
    private String modelVersion;

    @Column(name = "sample_rate")
    private Integer sampleRate;

    @Column(name = "f0_method", length = 64)
    private String f0Method;

    @Column(name = "batch_size")
    private Integer batchSize;

    @Column(name = "total_epoch")
    private Integer totalEpoch;

    @Column(name = "speaker_id", length = 64)
    private String speakerId;

    @Column(name = "retry_count", nullable = false)
    private Integer retryCount = 0;

    @Column(name = "max_retries", nullable = false)
    private Integer maxRetries = 3;

    @Column(name = "progress_percent", nullable = false)
    private Integer progressPercent = 0;

    @Column(name = "payload", columnDefinition = "TEXT")
    private String payload;

    @Column(name = "result_manifest", columnDefinition = "TEXT")
    private String resultManifest;

    @Column(name = "note", columnDefinition = "TEXT")
    private String note;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "lease_expires_at")
    private OffsetDateTime leaseExpiresAt;

    @Column(name = "started_at")
    private OffsetDateTime startedAt;

    @Column(name = "finished_at")
    private OffsetDateTime finishedAt;

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

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public UUID getCharacterId() {
        return characterId;
    }

    public void setCharacterId(UUID characterId) {
        this.characterId = characterId;
    }

    public JobType getJobType() {
        return jobType;
    }

    public void setJobType(JobType jobType) {
        this.jobType = jobType;
    }

    public ExecutionMode getExecutionMode() {
        return executionMode;
    }

    public void setExecutionMode(ExecutionMode executionMode) {
        this.executionMode = executionMode;
    }

    public JobStatus getStatus() {
        return status;
    }

    public void setStatus(JobStatus status) {
        this.status = status;
    }

    public Integer getPriority() {
        return priority;
    }

    public void setPriority(Integer priority) {
        this.priority = priority;
    }

    public UUID getTargetNodeId() {
        return targetNodeId;
    }

    public void setTargetNodeId(UUID targetNodeId) {
        this.targetNodeId = targetNodeId;
    }

    public UUID getAssignedNodeId() {
        return assignedNodeId;
    }

    public void setAssignedNodeId(UUID assignedNodeId) {
        this.assignedNodeId = assignedNodeId;
    }

    public List<String> getInputAssetIds() {
        return inputAssetIds;
    }

    public void setInputAssetIds(List<String> inputAssetIds) {
        this.inputAssetIds = inputAssetIds == null ? new ArrayList<>() : inputAssetIds;
    }

    public String getDatasetVersion() {
        return datasetVersion;
    }

    public void setDatasetVersion(String datasetVersion) {
        this.datasetVersion = datasetVersion;
    }

    public String getModelVersion() {
        return modelVersion;
    }

    public void setModelVersion(String modelVersion) {
        this.modelVersion = modelVersion;
    }

    public Integer getSampleRate() {
        return sampleRate;
    }

    public void setSampleRate(Integer sampleRate) {
        this.sampleRate = sampleRate;
    }

    public String getF0Method() {
        return f0Method;
    }

    public void setF0Method(String f0Method) {
        this.f0Method = f0Method;
    }

    public Integer getBatchSize() {
        return batchSize;
    }

    public void setBatchSize(Integer batchSize) {
        this.batchSize = batchSize;
    }

    public Integer getTotalEpoch() {
        return totalEpoch;
    }

    public void setTotalEpoch(Integer totalEpoch) {
        this.totalEpoch = totalEpoch;
    }

    public String getSpeakerId() {
        return speakerId;
    }

    public void setSpeakerId(String speakerId) {
        this.speakerId = speakerId;
    }

    public Integer getRetryCount() {
        return retryCount;
    }

    public void setRetryCount(Integer retryCount) {
        this.retryCount = retryCount;
    }

    public Integer getMaxRetries() {
        return maxRetries;
    }

    public void setMaxRetries(Integer maxRetries) {
        this.maxRetries = maxRetries;
    }

    public Integer getProgressPercent() {
        return progressPercent;
    }

    public void setProgressPercent(Integer progressPercent) {
        this.progressPercent = progressPercent;
    }

    public String getPayload() {
        return payload;
    }

    public void setPayload(String payload) {
        this.payload = payload;
    }

    public String getResultManifest() {
        return resultManifest;
    }

    public void setResultManifest(String resultManifest) {
        this.resultManifest = resultManifest;
    }

    public String getNote() {
        return note;
    }

    public void setNote(String note) {
        this.note = note;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public OffsetDateTime getLeaseExpiresAt() {
        return leaseExpiresAt;
    }

    public void setLeaseExpiresAt(OffsetDateTime leaseExpiresAt) {
        this.leaseExpiresAt = leaseExpiresAt;
    }

    public OffsetDateTime getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(OffsetDateTime startedAt) {
        this.startedAt = startedAt;
    }

    public OffsetDateTime getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(OffsetDateTime finishedAt) {
        this.finishedAt = finishedAt;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}

