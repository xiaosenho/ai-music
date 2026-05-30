package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.CreateMediaAssetRequest;
import com.aimusic.controlplane.dto.CompleteDirectUploadRequest;
import com.aimusic.controlplane.dto.MediaAssetResponse;
import com.aimusic.controlplane.entity.MediaAsset;
import com.aimusic.controlplane.model.AssetStatus;
import com.aimusic.controlplane.model.AssetType;
import com.aimusic.controlplane.repository.MediaAssetRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AssetService {

    private final MediaAssetRepository mediaAssetRepository;
    private final ObjectMapper objectMapper;
    private final CosStorageService cosStorageService;

    public AssetService(
            MediaAssetRepository mediaAssetRepository,
            ObjectMapper objectMapper,
            CosStorageService cosStorageService
    ) {
        this.mediaAssetRepository = mediaAssetRepository;
        this.objectMapper = objectMapper;
        this.cosStorageService = cosStorageService;
    }

    @Transactional
    public MediaAssetResponse create(CreateMediaAssetRequest request) {
        MediaAsset asset = new MediaAsset();
        asset.setId(UUID.randomUUID());
        asset.setCharacterId(request.characterId());
        asset.setName(request.name());
        asset.setAssetType(request.assetType());
        asset.setStatus(AssetStatus.UPLOADED);
        asset.setSourceUri(request.sourceUri());
        asset.setObjectKey(request.objectKey());
        asset.setDurationSeconds(request.durationSeconds());
        asset.setLanguage(request.language());
        asset.setNote(request.note());
        asset.setMetadata(serialize(request.metadata()));
        mediaAssetRepository.save(asset);
        return toResponse(asset);
    }

    @Transactional(readOnly = true)
    public List<MediaAssetResponse> list() {
        return mediaAssetRepository.findAllByOrderByCreatedAtDesc().stream().map(this::toResponse).toList();
    }

    @Transactional(readOnly = true)
    public MediaAssetResponse get(UUID id) {
        return toResponse(mediaAssetRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Asset not found: " + id)));
    }

    @Transactional
    public MediaAssetResponse createUploadedAsset(
            String name,
            AssetType assetType,
            String objectKey,
            String publicUrl,
            String language,
            String note
    ) {
        MediaAsset asset = new MediaAsset();
        asset.setId(UUID.randomUUID());
        asset.setName(name);
        asset.setAssetType(assetType);
        asset.setStatus(AssetStatus.UPLOADED);
        asset.setObjectKey(objectKey);
        asset.setSourceUri(publicUrl);
        asset.setLanguage(language);
        asset.setNote(note);
        mediaAssetRepository.save(asset);
        return toResponse(asset);
    }

    @Transactional
    public MediaAssetResponse completeDirectUpload(CompleteDirectUploadRequest request) {
        MediaAsset asset = new MediaAsset();
        asset.setId(UUID.randomUUID());
        asset.setName(request.fileName());
        asset.setAssetType(request.assetType());
        asset.setStatus(AssetStatus.UPLOADED);
        asset.setObjectKey(request.objectKey());
        asset.setSourceUri(cosStorageService.publicUrlFor(request.objectKey()));
        asset.setDurationSeconds(request.durationSeconds());
        asset.setLanguage(request.language());
        asset.setNote(request.note());
        asset.setMetadata(serialize(mergeUploadMetadata(request)));
        mediaAssetRepository.save(asset);
        return toResponse(asset);
    }

    @Transactional
    public void updateStatuses(List<UUID> assetIds, AssetStatus status) {
        List<MediaAsset> assets = mediaAssetRepository.findAllById(assetIds);
        assets.forEach(asset -> asset.setStatus(status));
        mediaAssetRepository.saveAll(assets);
    }

    @Transactional
    public List<MediaAssetResponse> createProcessedAssets(List<ProcessedAssetCreateCommand> commands) {
        List<MediaAsset> assets = commands.stream().map(command -> {
            MediaAsset asset = new MediaAsset();
            asset.setId(UUID.randomUUID());
            asset.setName(command.name());
            asset.setAssetType(command.assetType());
            asset.setStatus(AssetStatus.APPROVED);
            asset.setObjectKey(command.objectKey());
            asset.setSourceUri(command.sourceUri() == null || command.sourceUri().isBlank()
                    ? cosStorageService.publicUrlFor(command.objectKey())
                    : command.sourceUri());
            asset.setDurationSeconds(command.durationSeconds());
            asset.setLanguage(command.language());
            asset.setNote(command.note());
            asset.setMetadata(serialize(command.metadata()));
            return asset;
        }).toList();

        return mediaAssetRepository.saveAll(assets).stream().map(this::toResponse).toList();
    }

    @Transactional
    public MediaAssetResponse createOutputAsset(String name, String objectKey, String publicUrl, String note) {
        return createUploadedAsset(name, AssetType.AUDIO, objectKey, publicUrl, "zh-CN", note);
    }

    private MediaAssetResponse toResponse(MediaAsset asset) {
        return new MediaAssetResponse(
                asset.getId(),
                asset.getCharacterId(),
                asset.getName(),
                asset.getAssetType(),
                asset.getStatus(),
                asset.getSourceUri(),
                asset.getObjectKey(),
                asset.getDurationSeconds(),
                asset.getLanguage(),
                asset.getMetadata(),
                asset.getNote(),
                asset.getCreatedAt(),
                asset.getUpdatedAt()
        );
    }

    private String serialize(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalArgumentException("Failed to serialize asset metadata", exception);
        }
    }

    private Object mergeUploadMetadata(CompleteDirectUploadRequest request) {
        if (request.metadata() == null && request.contentType() == null && request.sizeBytes() == null) {
            return null;
        }

        java.util.Map<String, Object> metadata = new java.util.LinkedHashMap<>();
        if (request.metadata() != null) {
            metadata.putAll(request.metadata());
        }
        if (request.contentType() != null && !request.contentType().isBlank()) {
            metadata.put("contentType", request.contentType());
        }
        if (request.sizeBytes() != null) {
            metadata.put("sizeBytes", request.sizeBytes());
        }
        return metadata;
    }
}
