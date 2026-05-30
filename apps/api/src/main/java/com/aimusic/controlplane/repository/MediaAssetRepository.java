package com.aimusic.controlplane.repository;

import com.aimusic.controlplane.entity.MediaAsset;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface MediaAssetRepository extends JpaRepository<MediaAsset, UUID> {
    List<MediaAsset> findAllByOrderByCreatedAtDesc();
}

