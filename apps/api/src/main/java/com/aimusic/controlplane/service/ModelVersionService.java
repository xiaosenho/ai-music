package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.CreateModelVersionRequest;
import com.aimusic.controlplane.dto.ModelVersionResponse;
import com.aimusic.controlplane.entity.ModelVersion;
import com.aimusic.controlplane.model.ModelVersionStatus;
import com.aimusic.controlplane.repository.ModelVersionRepository;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ModelVersionService {

    private final ModelVersionRepository modelVersionRepository;

    public ModelVersionService(ModelVersionRepository modelVersionRepository) {
        this.modelVersionRepository = modelVersionRepository;
    }

    @Transactional
    public ModelVersionResponse create(CreateModelVersionRequest request) {
        ModelVersion modelVersion = new ModelVersion();
        modelVersion.setId(UUID.randomUUID());
        modelVersion.setCharacterId(request.characterId());
        modelVersion.setDatasetId(request.datasetId());
        modelVersion.setTrainingJobId(request.trainingJobId());
        modelVersion.setName(request.name());
        modelVersion.setStatus(ModelVersionStatus.DRAFT);
        modelVersion.setModelType(request.modelType());
        modelVersion.setStoragePath(request.storagePath());
        modelVersion.setSampleAudioUrl(request.sampleAudioUrl());
        modelVersion.setMetrics(request.metrics());
        modelVersion.setNote(request.note());
        modelVersionRepository.save(modelVersion);
        return toResponse(modelVersion);
    }

    @Transactional(readOnly = true)
    public List<ModelVersionResponse> list() {
        return modelVersionRepository.findAllByOrderByCreatedAtDesc().stream().map(this::toResponse).toList();
    }

    @Transactional(readOnly = true)
    public ModelVersionResponse get(UUID id) {
        return toResponse(require(id));
    }

    @Transactional
    public ModelVersion createTrainingDraft(UUID datasetId, String name, String modelType, String note) {
        ModelVersion modelVersion = new ModelVersion();
        modelVersion.setId(UUID.randomUUID());
        modelVersion.setDatasetId(datasetId);
        modelVersion.setName(name);
        modelVersion.setStatus(ModelVersionStatus.TRAINING);
        modelVersion.setModelType(modelType);
        modelVersion.setNote(note);
        modelVersionRepository.save(modelVersion);
        return modelVersion;
    }

    @Transactional(readOnly = true)
    public ModelVersion require(UUID id) {
        return modelVersionRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Model version not found: " + id));
    }

    @Transactional
    public void markTraining(UUID id) {
        require(id).setStatus(ModelVersionStatus.TRAINING);
    }

    @Transactional
    public void markReady(UUID id, String storagePath, String sampleAudioUrl, String metrics) {
        ModelVersion modelVersion = require(id);
        modelVersion.setStatus(ModelVersionStatus.READY);
        if (storagePath != null && !storagePath.isBlank()) {
            modelVersion.setStoragePath(storagePath);
        }
        if (sampleAudioUrl != null && !sampleAudioUrl.isBlank()) {
            modelVersion.setSampleAudioUrl(sampleAudioUrl);
        }
        if (metrics != null && !metrics.isBlank()) {
            modelVersion.setMetrics(metrics);
        }
    }

    @Transactional
    public void markDraft(UUID id) {
        require(id).setStatus(ModelVersionStatus.DRAFT);
    }

    @Transactional
    public void linkTrainingJob(UUID id, UUID trainingJobId) {
        require(id).setTrainingJobId(trainingJobId);
    }

    private ModelVersionResponse toResponse(ModelVersion modelVersion) {
        return new ModelVersionResponse(
                modelVersion.getId(),
                modelVersion.getCharacterId(),
                modelVersion.getDatasetId(),
                modelVersion.getTrainingJobId(),
                modelVersion.getName(),
                modelVersion.getStatus(),
                modelVersion.getModelType(),
                modelVersion.getStoragePath(),
                modelVersion.getSampleAudioUrl(),
                modelVersion.getMetrics(),
                modelVersion.getNote(),
                modelVersion.getCreatedAt(),
                modelVersion.getUpdatedAt()
        );
    }
}
