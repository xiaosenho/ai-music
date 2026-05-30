package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.CreateInferJobRequest;
import com.aimusic.controlplane.dto.CreateJobRequest;
import com.aimusic.controlplane.dto.CreateProcessJobRequest;
import com.aimusic.controlplane.dto.CreateTrainJobRequest;
import com.aimusic.controlplane.dto.JobResponse;
import com.aimusic.controlplane.entity.Dataset;
import com.aimusic.controlplane.entity.ModelVersion;
import com.aimusic.controlplane.model.AssetStatus;
import com.aimusic.controlplane.model.ExecutionMode;
import com.aimusic.controlplane.model.JobType;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WorkflowService {

    private final JobService jobService;
    private final AssetService assetService;
    private final DatasetService datasetService;
    private final ModelVersionService modelVersionService;
    private final CosStorageService cosStorageService;

    public WorkflowService(
            JobService jobService,
            AssetService assetService,
            DatasetService datasetService,
            ModelVersionService modelVersionService,
            CosStorageService cosStorageService
    ) {
        this.jobService = jobService;
        this.assetService = assetService;
        this.datasetService = datasetService;
        this.modelVersionService = modelVersionService;
        this.cosStorageService = cosStorageService;
    }

    @Transactional
    public JobResponse createProcessJob(CreateProcessJobRequest request) {
        assetService.updateStatuses(request.assetIds().stream().map(UUID::fromString).toList(), AssetStatus.PROCESSING);
        Dataset dataset = datasetService.createProcessingDataset(
                request.datasetName(),
                request.assetIds(),
                request.language(),
                request.note()
        );

        return jobService.createJob(new CreateJobRequest(
                null,
                JobType.PROCESS,
                ExecutionMode.CLOUD,
                0,
                null,
                request.assetIds(),
                dataset.getName(),
                null,
                null,
                null,
                null,
                null,
                null,
                3,
                request.note(),
                Map.of(
                        "workflow", "asset-process",
                        "datasetId", dataset.getId().toString(),
                        "assetIds", request.assetIds()
                )
        ));
    }

    @Transactional
    public JobResponse createTrainJob(UUID datasetId, CreateTrainJobRequest request) {
        Dataset dataset = datasetService.require(datasetId);
        datasetService.markProcessing(datasetId);
        ModelVersion modelVersion = modelVersionService.createTrainingDraft(datasetId, request.modelName(), request.modelType(), request.note());
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("workflow", "dataset-train");
        payload.put("datasetId", datasetId.toString());
        payload.put("modelVersionId", modelVersion.getId().toString());
        putIfNotNull(payload, "version", request.version());
        putIfNotNull(payload, "useF0", request.useF0());
        putIfNotNull(payload, "saveEveryEpoch", request.saveEveryEpoch());
        putIfNotNull(payload, "saveLatest", request.saveLatest());
        putIfNotNull(payload, "cacheGpu", request.cacheGpu());
        putIfNotNull(payload, "saveEveryWeights", request.saveEveryWeights());

        JobResponse jobResponse = jobService.createJob(new CreateJobRequest(
                null,
                JobType.TRAIN,
                ExecutionMode.CLOUD,
                0,
                null,
                dataset.getAssetIds(),
                dataset.getName(),
                modelVersion.getName(),
                request.sampleRate(),
                request.f0Method(),
                request.batchSize(),
                request.totalEpoch(),
                request.speakerId(),
                3,
                request.note(),
                payload
        ));

        modelVersionService.linkTrainingJob(modelVersion.getId(), jobResponse.id());
        return jobResponse;
    }

    @Transactional
    public JobResponse createInferJob(UUID modelVersionId, CreateInferJobRequest request) {
        ModelVersion modelVersion = modelVersionService.require(modelVersionId);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("workflow", "model-infer");
        payload.put("modelVersionId", modelVersionId.toString());
        payload.put("inputAssetIds", request.inputAssetIds());
        putIfNotNull(payload, "f0UpKey", request.f0UpKey());
        putIfNotNull(payload, "indexRate", request.indexRate());
        putIfNotNull(payload, "filterRadius", request.filterRadius());
        putIfNotNull(payload, "resampleSr", request.resampleSr());
        putIfNotNull(payload, "rmsMixRate", request.rmsMixRate());
        putIfNotNull(payload, "protect", request.protect());

        return jobService.createJob(new CreateJobRequest(
                null,
                JobType.INFER,
                request.executionMode(),
                0,
                null,
                request.inputAssetIds(),
                null,
                modelVersion.getName(),
                null,
                request.f0Method(),
                null,
                null,
                request.speakerId(),
                3,
                request.note(),
                payload
        ));
    }

    public CosStorageService.DirectDownloadTicket prepareModelArtifactDownload(String storagePath) {
        return cosStorageService.prepareDirectDownload(storagePath);
    }

    private void putIfNotNull(Map<String, Object> payload, String key, Object value) {
        if (value != null) {
            payload.put(key, value);
        }
    }
}
