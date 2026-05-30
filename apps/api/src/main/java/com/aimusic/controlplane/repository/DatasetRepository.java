package com.aimusic.controlplane.repository;

import com.aimusic.controlplane.entity.Dataset;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface DatasetRepository extends JpaRepository<Dataset, UUID> {
    List<Dataset> findAllByOrderByCreatedAtDesc();
}

