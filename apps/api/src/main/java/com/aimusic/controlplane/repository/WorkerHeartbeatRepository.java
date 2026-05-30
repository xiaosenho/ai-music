package com.aimusic.controlplane.repository;

import com.aimusic.controlplane.entity.WorkerHeartbeat;
import org.springframework.data.jpa.repository.JpaRepository;

public interface WorkerHeartbeatRepository extends JpaRepository<WorkerHeartbeat, Long> {
}

