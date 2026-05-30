package com.aimusic.controlplane.entity;

import com.aimusic.controlplane.converter.StringListJsonConverter;
import com.aimusic.controlplane.model.DatasetStatus;
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
@Table(name = "datasets")
public class Dataset {

    @Id
    private UUID id;

    @Column(name = "character_id")
    private UUID characterId;

    @Column(nullable = false)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private DatasetStatus status;

    @Convert(converter = StringListJsonConverter.class)
    @Column(name = "asset_ids", nullable = false, columnDefinition = "TEXT")
    private List<String> assetIds = new ArrayList<>();

    @Column(name = "segment_count", nullable = false)
    private Integer segmentCount = 0;

    @Column(length = 32)
    private String language;

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
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public DatasetStatus getStatus() { return status; }
    public void setStatus(DatasetStatus status) { this.status = status; }
    public List<String> getAssetIds() { return assetIds; }
    public void setAssetIds(List<String> assetIds) { this.assetIds = assetIds == null ? new ArrayList<>() : assetIds; }
    public Integer getSegmentCount() { return segmentCount; }
    public void setSegmentCount(Integer segmentCount) { this.segmentCount = segmentCount; }
    public String getLanguage() { return language; }
    public void setLanguage(String language) { this.language = language; }
    public String getNote() { return note; }
    public void setNote(String note) { this.note = note; }
    public OffsetDateTime getCreatedAt() { return createdAt; }
    public OffsetDateTime getUpdatedAt() { return updatedAt; }
}

