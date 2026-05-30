package com.aimusic.controlplane.service;

import com.aimusic.controlplane.dto.DashboardSummaryResponse;
import com.aimusic.controlplane.dto.StatusCountResponse;
import com.aimusic.controlplane.entity.Dataset;
import com.aimusic.controlplane.entity.Job;
import com.aimusic.controlplane.entity.MediaAsset;
import com.aimusic.controlplane.entity.ModelVersion;
import com.aimusic.controlplane.entity.WorkerNode;
import com.aimusic.controlplane.model.DatasetStatus;
import com.aimusic.controlplane.model.JobStatus;
import com.aimusic.controlplane.model.ModelVersionStatus;
import com.aimusic.controlplane.model.NodeStatus;
import com.aimusic.controlplane.repository.DatasetRepository;
import com.aimusic.controlplane.repository.JobRepository;
import com.aimusic.controlplane.repository.MediaAssetRepository;
import com.aimusic.controlplane.repository.ModelVersionRepository;
import com.aimusic.controlplane.repository.WorkerNodeRepository;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DashboardService {

    private final WorkerNodeRepository workerNodeRepository;
    private final JobRepository jobRepository;
    private final MediaAssetRepository mediaAssetRepository;
    private final DatasetRepository datasetRepository;
    private final ModelVersionRepository modelVersionRepository;

    public DashboardService(
            WorkerNodeRepository workerNodeRepository,
            JobRepository jobRepository,
            MediaAssetRepository mediaAssetRepository,
            DatasetRepository datasetRepository,
            ModelVersionRepository modelVersionRepository
    ) {
        this.workerNodeRepository = workerNodeRepository;
        this.jobRepository = jobRepository;
        this.mediaAssetRepository = mediaAssetRepository;
        this.datasetRepository = datasetRepository;
        this.modelVersionRepository = modelVersionRepository;
    }

    @Transactional(readOnly = true)
    public DashboardSummaryResponse getSummary() {
        List<WorkerNode> workers = workerNodeRepository.findAll();
        List<Job> jobs = jobRepository.findAll();
        List<MediaAsset> assets = mediaAssetRepository.findAll();
        List<Dataset> datasets = datasetRepository.findAll();
        List<ModelVersion> modelVersions = modelVersionRepository.findAll();

        OffsetDateTime onlineThreshold = OffsetDateTime.now().minusSeconds(90);
        long onlineWorkers = workers.stream()
                .filter(worker -> worker.getLastSeenAt() != null && worker.getLastSeenAt().isAfter(onlineThreshold))
                .count();

        return new DashboardSummaryResponse(
                workers.size(),
                onlineWorkers,
                workers.stream().filter(worker -> worker.getStatus() == NodeStatus.BUSY).count(),
                jobs.size(),
                jobs.stream().filter(job -> job.getStatus() == JobStatus.QUEUED || job.getStatus() == JobStatus.PENDING || job.getStatus() == JobStatus.RETRY_WAITING).count(),
                jobs.stream().filter(job -> job.getStatus() == JobStatus.RUNNING || job.getStatus() == JobStatus.LEASED || job.getStatus() == JobStatus.UPLOADING).count(),
                jobs.stream().filter(job -> job.getStatus() == JobStatus.FAILED).count(),
                assets.size(),
                datasets.size(),
                datasets.stream().filter(dataset -> dataset.getStatus() == DatasetStatus.READY).count(),
                modelVersions.size(),
                modelVersions.stream().filter(model -> model.getStatus() == ModelVersionStatus.READY).count(),
                toCounts(workers.stream().collect(Collectors.groupingBy(worker -> worker.getStatus().name(), Collectors.counting()))),
                toCounts(jobs.stream().collect(Collectors.groupingBy(job -> job.getStatus().name(), Collectors.counting()))),
                toCounts(jobs.stream().collect(Collectors.groupingBy(job -> job.getJobType().name(), Collectors.counting())))
        );
    }

    private List<StatusCountResponse> toCounts(Map<String, Long> counts) {
        return counts.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> new StatusCountResponse(entry.getKey(), entry.getValue()))
                .toList();
    }
}
