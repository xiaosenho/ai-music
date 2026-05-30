package com.aimusic.controlplane.repository;

import com.aimusic.controlplane.entity.WorkerNode;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface WorkerNodeRepository extends JpaRepository<WorkerNode, UUID> {
}

