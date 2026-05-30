package com.aimusic.controlplane.controller;

import com.aimusic.controlplane.dto.CreateDatasetRequest;
import com.aimusic.controlplane.dto.CreateTrainJobRequest;
import com.aimusic.controlplane.dto.DatasetResponse;
import com.aimusic.controlplane.dto.JobResponse;
import com.aimusic.controlplane.service.DatasetService;
import com.aimusic.controlplane.service.WorkflowService;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/datasets")
public class DatasetController {

    private final DatasetService datasetService;
    private final WorkflowService workflowService;

    public DatasetController(DatasetService datasetService, WorkflowService workflowService) {
        this.datasetService = datasetService;
        this.workflowService = workflowService;
    }

    @GetMapping
    public List<DatasetResponse> list() {
        return datasetService.list();
    }

    @GetMapping("/{datasetId}")
    public DatasetResponse get(@PathVariable UUID datasetId) {
        return datasetService.get(datasetId);
    }

    @DeleteMapping("/{datasetId}")
    public void delete(@PathVariable UUID datasetId) {
        datasetService.delete(datasetId);
    }

    @PostMapping
    public DatasetResponse create(@Valid @RequestBody CreateDatasetRequest request) {
        return datasetService.create(request);
    }

    @PostMapping("/{datasetId}/train-jobs")
    public JobResponse createTrainJob(
            @PathVariable UUID datasetId,
            @Valid @RequestBody CreateTrainJobRequest request
    ) {
        return workflowService.createTrainJob(datasetId, request);
    }
}
