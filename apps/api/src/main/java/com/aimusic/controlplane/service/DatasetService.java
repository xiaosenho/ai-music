package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.CreateDatasetRequest;
import com.aimusic.controlplane.dto.DatasetResponse;
import com.aimusic.controlplane.entity.Dataset;
import com.aimusic.controlplane.repository.JobRepository;
import com.aimusic.controlplane.repository.ModelVersionRepository;
import com.aimusic.controlplane.model.DatasetStatus;
import com.aimusic.controlplane.repository.DatasetRepository;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DatasetService {

    private final DatasetRepository datasetRepository;
    private final ModelVersionRepository modelVersionRepository;
    private final JobRepository jobRepository;

    public DatasetService(
            DatasetRepository datasetRepository,
            ModelVersionRepository modelVersionRepository,
            JobRepository jobRepository
    ) {
        this.datasetRepository = datasetRepository;
        this.modelVersionRepository = modelVersionRepository;
        this.jobRepository = jobRepository;
    }

    @Transactional
    public DatasetResponse create(CreateDatasetRequest request) {
        Dataset dataset = new Dataset();
        dataset.setId(UUID.randomUUID());
        dataset.setCharacterId(request.characterId());
        dataset.setName(request.name());
        dataset.setStatus(DatasetStatus.DRAFT);
        dataset.setAssetIds(request.assetIds());
        dataset.setSegmentCount(request.segmentCount() == null ? 0 : request.segmentCount());
        dataset.setLanguage(request.language());
        dataset.setNote(request.note());
        datasetRepository.save(dataset);
        return toResponse(dataset);
    }

    @Transactional(readOnly = true)
    public List<DatasetResponse> list() {
        return datasetRepository.findAllByOrderByCreatedAtDesc().stream().map(this::toResponse).toList();
    }

    @Transactional(readOnly = true)
    public DatasetResponse get(UUID id) {
        return toResponse(require(id));
    }

    @Transactional
    public void delete(UUID id) {
        Dataset dataset = require(id);
        String datasetId = id.toString();

        boolean usedByModel = modelVersionRepository.findAll().stream()
                .anyMatch(modelVersion -> id.equals(modelVersion.getDatasetId()));
        if (usedByModel) {
            throw new IllegalArgumentException("Dataset is referenced by a model version and cannot be deleted");
        }

        boolean usedByJob = jobRepository.findAll().stream()
                .anyMatch(job -> datasetId.equals(job.getDatasetVersion()));
        if (usedByJob) {
            throw new IllegalArgumentException("Dataset is referenced by a job and cannot be deleted");
        }

        datasetRepository.delete(dataset);
    }

    @Transactional
    public Dataset createProcessingDataset(String name, List<String> assetIds, String language, String note) {
        Dataset dataset = new Dataset();
        dataset.setId(UUID.randomUUID());
        dataset.setName(name);
        dataset.setStatus(DatasetStatus.PROCESSING);
        dataset.setAssetIds(assetIds);
        dataset.setSegmentCount(0);
        dataset.setLanguage(language);
        dataset.setNote(note);
        datasetRepository.save(dataset);
        return dataset;
    }

    @Transactional(readOnly = true)
    public Dataset require(UUID id) {
        return datasetRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Dataset not found: " + id));
    }

    @Transactional
    public void markReady(UUID id, Integer segmentCount) {
        Dataset dataset = require(id);
        dataset.setStatus(DatasetStatus.READY);
        if (segmentCount != null) {
            dataset.setSegmentCount(segmentCount);
        }
    }

    @Transactional
    public void markReady(UUID id, List<String> assetIds, Integer segmentCount) {
        Dataset dataset = require(id);
        dataset.setStatus(DatasetStatus.READY);
        if (assetIds != null && !assetIds.isEmpty()) {
            dataset.setAssetIds(assetIds);
        }
        if (segmentCount != null) {
            dataset.setSegmentCount(segmentCount);
        }
    }

    @Transactional
    public void markProcessing(UUID id) {
        Dataset dataset = require(id);
        dataset.setStatus(DatasetStatus.PROCESSING);
    }

    private DatasetResponse toResponse(Dataset dataset) {
        return new DatasetResponse(
                dataset.getId(),
                dataset.getCharacterId(),
                dataset.getName(),
                dataset.getStatus(),
                dataset.getAssetIds(),
                dataset.getSegmentCount(),
                dataset.getLanguage(),
                dataset.getNote(),
                dataset.getCreatedAt(),
                dataset.getUpdatedAt()
        );
    }
}
