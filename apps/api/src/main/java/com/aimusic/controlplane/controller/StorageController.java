package com.aimusic.controlplane.controller;

import com.aimusic.controlplane.dto.DirectDownloadTicketResponse;
import com.aimusic.controlplane.dto.PrepareStorageDownloadRequest;
import com.aimusic.controlplane.dto.PrepareStorageUploadRequest;
import com.aimusic.controlplane.dto.StorageUploadTicketResponse;
import com.aimusic.controlplane.service.CosStorageService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/storage")
public class StorageController {

    private final CosStorageService cosStorageService;

    public StorageController(CosStorageService cosStorageService) {
        this.cosStorageService = cosStorageService;
    }

    @PostMapping("/upload-prepare")
    public StorageUploadTicketResponse prepareUpload(@Valid @RequestBody PrepareStorageUploadRequest request) {
        CosStorageService.DirectUploadTicket ticket = cosStorageService.prepareDirectUpload(request.fileName(), request.category());
        return new StorageUploadTicketResponse(
                ticket.objectKey(),
                ticket.publicUrl(),
                ticket.uploadUrl(),
                ticket.headers(),
                ticket.expiresAt()
        );
    }

    @PostMapping("/download-prepare")
    public DirectDownloadTicketResponse prepareDownload(@Valid @RequestBody PrepareStorageDownloadRequest request) {
        CosStorageService.DirectDownloadTicket ticket = cosStorageService.prepareDirectDownload(request.objectKey());
        return new DirectDownloadTicketResponse(ticket.objectKey(), ticket.downloadUrl(), ticket.expiresAt());
    }
}
