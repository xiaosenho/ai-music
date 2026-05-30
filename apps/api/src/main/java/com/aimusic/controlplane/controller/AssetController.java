package com.aimusic.controlplane.controller;

import com.aimusic.controlplane.dto.CompleteDirectUploadRequest;
import com.aimusic.controlplane.dto.CreateProcessJobRequest;
import com.aimusic.controlplane.dto.CreateMediaAssetRequest;
import com.aimusic.controlplane.dto.DirectDownloadTicketResponse;
import com.aimusic.controlplane.dto.JobResponse;
import com.aimusic.controlplane.dto.MediaAssetResponse;
import com.aimusic.controlplane.dto.PrepareDirectUploadRequest;
import com.aimusic.controlplane.dto.PrepareDirectUploadResponse;
import com.aimusic.controlplane.service.AssetService;
import com.aimusic.controlplane.service.CosStorageService;
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

    @GetMapping("/{assetId}")
    public MediaAssetResponse get(@PathVariable UUID assetId) {
        return assetService.get(assetId);
    }

    @DeleteMapping("/{assetId}")
    public void delete(@PathVariable UUID assetId) {
        assetService.delete(assetId);
    }

    @PostMapping
    public MediaAssetResponse create(@Valid @RequestBody CreateMediaAssetRequest request) {
        return assetService.create(request);
    }

    @PostMapping("/upload-prepare")
    public PrepareDirectUploadResponse prepareUpload(@Valid @RequestBody PrepareDirectUploadRequest request) {
        CosStorageService.DirectUploadTicket ticket = cosStorageService.prepareDirectUpload(request.fileName(), "assets");
        return new PrepareDirectUploadResponse(
                request.fileName(),
                request.assetType(),
                ticket.objectKey(),
                ticket.publicUrl(),
                ticket.uploadUrl(),
                ticket.headers(),
                ticket.expiresAt()
        );
    }

    @PostMapping("/upload-complete")
    public MediaAssetResponse completeUpload(@Valid @RequestBody CompleteDirectUploadRequest request) {
        return assetService.completeDirectUpload(request);
    }

    @PostMapping("/{assetId}/download-ticket")
    public DirectDownloadTicketResponse prepareDownload(@PathVariable UUID assetId) {
        MediaAssetResponse asset = assetService.get(assetId);
        if (asset.objectKey() == null || asset.objectKey().isBlank()) {
            throw new IllegalArgumentException("Asset does not have a COS object key");
        }
        var ticket = cosStorageService.prepareDirectDownload(asset.objectKey());
        return new DirectDownloadTicketResponse(ticket.objectKey(), ticket.downloadUrl(), ticket.expiresAt());
    }

    @PostMapping("/process-jobs")
    public JobResponse createProcessJob(@Valid @RequestBody CreateProcessJobRequest request) {
        return workflowService.createProcessJob(request);
    }
}
