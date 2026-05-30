package com.aimusic.controlplane.repository;

import com.aimusic.controlplane.entity.JobEvent;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface JobEventRepository extends JpaRepository<JobEvent, Long> {

    List<JobEvent> findByJobIdOrderByCreatedAtAsc(UUID jobId);
}
