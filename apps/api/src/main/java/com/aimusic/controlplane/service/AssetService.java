package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.CreateMediaAssetRequest;
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

    public AssetService(MediaAssetRepository mediaAssetRepository, ObjectMapper objectMapper) {
        this.mediaAssetRepository = mediaAssetRepository;
        this.objectMapper = objectMapper;
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
    public void updateStatuses(List<UUID> assetIds, AssetStatus status) {
        List<MediaAsset> assets = mediaAssetRepository.findAllById(assetIds);
        assets.forEach(asset -> asset.setStatus(status));
        mediaAssetRepository.saveAll(assets);
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
}
