package com.aimusic.controlplane.entity;

import com.aimusic.controlplane.model.ModelVersionStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "model_versions")
public class ModelVersion {

    @Id
    private UUID id;

    @Column(name = "character_id")
    private UUID characterId;

    @Column(name = "dataset_id")
    private UUID datasetId;

    @Column(name = "training_job_id")
    private UUID trainingJobId;

    @Column(nullable = false)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private ModelVersionStatus status;

    @Column(name = "model_type", nullable = false, length = 64)
    private String modelType;

    @Column(name = "storage_path", columnDefinition = "TEXT")
    private String storagePath;

    @Column(name = "sample_audio_url", columnDefinition = "TEXT")
    private String sampleAudioUrl;

    @Column(columnDefinition = "TEXT")
    private String metrics;

    @Column(columnDefinition = "TEXT")
    private String note;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @PrePersist
    public void onCreate() {
        OffsetDateTime now = OffsetDateTime.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    public void onUpdate() {
        updatedAt = OffsetDateTime.now();
    }

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public UUID getCharacterId() { return characterId; }
    public void setCharacterId(UUID characterId) { this.characterId = characterId; }
    public UUID getDatasetId() { return datasetId; }
    public void setDatasetId(UUID datasetId) { this.datasetId = datasetId; }
    public UUID getTrainingJobId() { return trainingJobId; }
    public void setTrainingJobId(UUID trainingJobId) { this.trainingJobId = trainingJobId; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public ModelVersionStatus getStatus() { return status; }
    public void setStatus(ModelVersionStatus status) { this.status = status; }
    public String getModelType() { return modelType; }
    public void setModelType(String modelType) { this.modelType = modelType; }
    public String getStoragePath() { return storagePath; }
    public void setStoragePath(String storagePath) { this.storagePath = storagePath; }
    public String getSampleAudioUrl() { return sampleAudioUrl; }
    public void setSampleAudioUrl(String sampleAudioUrl) { this.sampleAudioUrl = sampleAudioUrl; }
    public String getMetrics() { return metrics; }
    public void setMetrics(String metrics) { this.metrics = metrics; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public OffsetDateTime getUpdatedAt() { return updatedAt; }
}

