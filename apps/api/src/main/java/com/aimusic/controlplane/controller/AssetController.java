package com.aimusic.controlplane.controller;

import com.aimusic.controlplane.dto.CreateProcessJobRequest;
import com.aimusic.controlplane.dto.CreateMediaAssetRequest;
import com.aimusic.controlplane.dto.JobResponse;
import com.aimusic.controlplane.dto.MediaAssetResponse;
import com.aimusic.controlplane.model.AssetType;
import com.aimusic.controlplane.service.AssetService;
import com.aimusic.controlplane.service.CosStorageService;
import com.aimusic.controlplane.service.WorkflowService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/assets")
public class AssetController {

    private final AssetService assetService;
    private final CosStorageService cosStorageService;
    private final WorkflowService workflowService;

    public AssetController(
            AssetService assetService,
            CosStorageService cosStorageService,
            WorkflowService workflowService
    ) {
        this.assetService = assetService;
        this.cosStorageService = cosStorageService;
        this.workflowService = workflowService;
    }

    @GetMapping
    public List<MediaAssetResponse> list() {
        return assetService.list();
    }

    @PostMapping
    public MediaAssetResponse create(@Valid @RequestBody CreateMediaAssetRequest request) {
        return assetService.create(request);
    }

    @PostMapping("/upload")
    public MediaAssetResponse upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "assetType", defaultValue = "AUDIO") AssetType assetType,
            @RequestParam(value = "language", required = false) String language,
            @RequestParam(value = "note", required = false) String note
    ) {
        CosStorageService.UploadedObject uploadedObject = cosStorageService.upload(file, "assets");
        return assetService.createUploadedAsset(
                file.getOriginalFilename() == null ? "uploaded-asset" : file.getOriginalFilename(),
                assetType,
                uploadedObject.objectKey(),
                uploadedObject.publicUrl(),
                language,
                note
        );
    }

    @PostMapping("/process-jobs")
    public JobResponse createProcessJob(@Valid @RequestBody CreateProcessJobRequest request) {
        return workflowService.createProcessJob(request);
    }
}
