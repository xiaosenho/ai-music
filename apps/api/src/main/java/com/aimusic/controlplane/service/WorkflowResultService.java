package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.MediaAssetResponse;
import com.aimusic.controlplane.entity.Job;
import com.aimusic.controlplane.model.AssetStatus;
import com.aimusic.controlplane.model.AssetType;
import com.aimusic.controlplane.model.JobStatus;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;

@Service
public class WorkflowResultService {

    private final ObjectMapper objectMapper;
    private final AssetService assetService;
    private final DatasetService datasetService;
    private final ModelVersionService modelVersionService;

    public WorkflowResultService(
            ObjectMapper objectMapper,
            AssetService assetService,
            DatasetService datasetService,
            ModelVersionService modelVersionService
    ) {
        this.objectMapper = objectMapper;
        this.assetService = assetService;
        this.datasetService = datasetService;
        this.modelVersionService = modelVersionService;
    }

    public void handle(Job job, JobStatus status, Map<String, Object> resultManifest) {
        Map<String, Object> payload = parsePayload(job.getPayload());
        String workflow = payload.get("workflow") instanceof String value ? value : null;
        if (workflow == null) {
            return;
        }

        switch (workflow) {
            case "asset-process" -> handleProcessWorkflow(payload, status, resultManifest);
            case "dataset-train" -> handleTrainWorkflow(payload, status, resultManifest);
            case "model-infer" -> handleInferWorkflow(payload, status, resultManifest);
            default -> {
            }
        }
    }

    private void handleProcessWorkflow(Map<String, Object> payload, JobStatus status, Map<String, Object> resultManifest) {
        List<UUID> assetIds = readUuidList(payload.get("assetIds"));
        UUID datasetId = readUuid(payload.get("datasetId"));

        if (status == JobStatus.SUCCEEDED) {
            assetService.updateStatuses(assetIds, AssetStatus.APPROVED);
            if (datasetId != null) {
                List<MediaAssetResponse> processedAssets = createProcessedAssets(resultManifest);
                Integer segmentCount = resultManifest == null ? null : readInteger(resultManifest.get("segmentCount"));
                if ((segmentCount == null || segmentCount <= 0) && !processedAssets.isEmpty()) {
                    segmentCount = processedAssets.size();
                }

                if (!processedAssets.isEmpty()) {
                    datasetService.markReady(
                            datasetId,
                            processedAssets.stream()
                                    .map(MediaAssetResponse::id)
                                    .map(UUID::toString)
                                    .collect(Collectors.toList()),
                            segmentCount
                    );
                } else {
                    datasetService.markReady(datasetId, segmentCount);
                }
            }
        }

        if (status == JobStatus.FAILED) {
            assetService.updateStatuses(assetIds, AssetStatus.UPLOADED);
        }
    }

    private void handleTrainWorkflow(Map<String, Object> payload, JobStatus status, Map<String, Object> resultManifest) {
        UUID modelVersionId = readUuid(payload.get("modelVersionId"));
        if (modelVersionId == null) {
            return;
        }

        if (status == JobStatus.RUNNING) {
            modelVersionService.markTraining(modelVersionId);
            return;
        }

        if (status == JobStatus.SUCCEEDED) {
            String storagePath = readString(resultManifest == null ? null : resultManifest.get("storagePath"));
            String sampleAudioUrl = readString(resultManifest == null ? null : resultManifest.get("sampleAudioUrl"));
            String metrics = resultManifest == null ? null : writeJson(resultManifest.get("metrics"));
            modelVersionService.markReady(modelVersionId, storagePath, sampleAudioUrl, metrics);
            return;
        }

        if (status == JobStatus.FAILED) {
            modelVersionService.markDraft(modelVersionId);
        }
    }

    private void handleInferWorkflow(Map<String, Object> payload, JobStatus status, Map<String, Object> resultManifest) {
        if (status != JobStatus.SUCCEEDED || resultManifest == null) {
            return;
        }

        String outputObjectKey = readString(resultManifest.get("outputObjectKey"));
        String outputUrl = readString(resultManifest.get("outputUrl"));
        String outputName = readString(resultManifest.get("outputName"));

        if (outputObjectKey != null || outputUrl != null || outputName != null) {
            assetService.createOutputAsset(
                    outputName == null ? "inference-output" : outputName,
                    outputObjectKey,
                    outputUrl,
                    "generated by infer job"
            );
        }
    }

    private List<MediaAssetResponse> createProcessedAssets(Map<String, Object> resultManifest) {
        if (resultManifest == null) {
            return List.of();
        }

        Object value = resultManifest.get("processedAssets");
        if (!(value instanceof List<?> items) || items.isEmpty()) {
            return List.of();
        }

        List<ProcessedAssetCreateCommand> commands = items.stream()
                .filter(Map.class::isInstance)
                .map(Map.class::cast)
                .map(this::toProcessedAssetCommand)
                .filter(command -> command.objectKey() != null && !command.objectKey().isBlank())
                .toList();

        if (commands.isEmpty()) {
            return List.of();
        }

        return assetService.createProcessedAssets(commands);
    }

    @SuppressWarnings("unchecked")
    private ProcessedAssetCreateCommand toProcessedAssetCommand(Map<?, ?> raw) {
        String name = readString(raw.get("name"));
        String objectKey = readString(raw.get("objectKey"));
        String sourceUri = readString(raw.get("sourceUri"));
        String language = readString(raw.get("language"));
        String note = readString(raw.get("note"));
        Integer durationSeconds = readInteger(raw.get("durationSeconds"));
        String assetTypeText = readString(raw.get("assetType"));
        AssetType assetType = assetTypeText == null ? AssetType.AUDIO : AssetType.valueOf(assetTypeText.toUpperCase());
        Map<String, Object> metadata = raw.get("metadata") instanceof Map<?, ?> metadataMap
                ? (Map<String, Object>) metadataMap
                : Map.of();

        return new ProcessedAssetCreateCommand(
                name == null ? "processed-audio" : name,
                assetType,
                objectKey,
                sourceUri,
                durationSeconds,
                language,
                note,
                metadata
        );
    }

    private Map<String, Object> parsePayload(String payload) {
        if (payload == null || payload.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(payload, new TypeReference<>() {});
        } catch (Exception exception) {
            return Map.of();
        }
    }

    private List<UUID> readUuidList(Object value) {
        if (value instanceof List<?> items) {
            return items.stream()
                    .filter(String.class::isInstance)
                    .map(String.class::cast)
                    .map(UUID::fromString)
                    .toList();
        }
        return List.of();
    }

    private UUID readUuid(Object value) {
        if (value instanceof String text && !text.isBlank()) {
            return UUID.fromString(text);
        }
        return null;
    }

    private Integer readInteger(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value instanceof String text && !text.isBlank()) {
            return Integer.parseInt(text);
        }
        return null;
    }

    private String readString(Object value) {
        return value instanceof String text && !text.isBlank() ? text : null;
    }

    private String writeJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception exception) {
            return null;
        }
    }
}
