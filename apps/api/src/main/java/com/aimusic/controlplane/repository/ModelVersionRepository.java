package com.aimusic.controlplane.repository;

import com.aimusic.controlplane.entity.ModelVersion;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface ModelVersionRepository extends JpaRepository<ModelVersion, UUID> {
    List<ModelVersion> findAllByOrderByCreatedAtDesc();
}

