package com.aimusic.controlplane.repository;

import com.aimusic.controlplane.entity.Job;
import com.aimusic.controlplane.model.JobStatus;
import jakarta.persistence.LockModeType;
import java.util.Collection;
import java.util.List;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;

public interface JobRepository extends JpaRepository<Job, UUID> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select j from Job j where j.status in :statuses order by j.priority desc, j.createdAt asc")
    List<Job> findCandidatesForLease(Collection<JobStatus> statuses, Pageable pageable);

    List<Job> findAllByOrderByCreatedAtDesc();
}
