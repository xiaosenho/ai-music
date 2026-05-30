package com.aimusic.controlplane.controller;

import com.aimusic.controlplane.dto.CreateInferJobRequest;
import com.aimusic.controlplane.dto.CreateModelVersionRequest;
import com.aimusic.controlplane.dto.JobResponse;
import com.aimusic.controlplane.dto.ModelVersionResponse;
import com.aimusic.controlplane.service.ModelVersionService;
import com.aimusic.controlplane.service.WorkflowService;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/models")
public class ModelVersionController {

    private final ModelVersionService modelVersionService;
    private final WorkflowService workflowService;

    public ModelVersionController(ModelVersionService modelVersionService, WorkflowService workflowService) {
        this.modelVersionService = modelVersionService;
        this.workflowService = workflowService;
    }

    @GetMapping
    public List<ModelVersionResponse> list() {
        return modelVersionService.list();
    }

    @PostMapping
    public ModelVersionResponse create(@Valid @RequestBody CreateModelVersionRequest request) {
        return modelVersionService.create(request);
    }

    @PostMapping("/{modelVersionId}/infer-jobs")
    public JobResponse createInferJob(
            @PathVariable UUID modelVersionId,
            @Valid @RequestBody CreateInferJobRequest request
    ) {
        return workflowService.createInferJob(modelVersionId, request);
    }
}
