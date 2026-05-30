package com.aimusic.controlplane.controller;

import com.aimusic.controlplane.dto.RegisterWorkerRequest;
import com.aimusic.controlplane.dto.RegisterWorkerResponse;
import com.aimusic.controlplane.dto.WorkerHeartbeatRequest;
import com.aimusic.controlplane.dto.WorkerHeartbeatResponse;
import com.aimusic.controlplane.dto.WorkerNodeResponse;
import com.aimusic.controlplane.model.NodeStatus;
import com.aimusic.controlplane.service.WorkerService;
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
@RequestMapping("/api/v1/workers")
public class WorkerController {

    private final WorkerService workerService;

    public WorkerController(WorkerService workerService) {
        this.workerService = workerService;
    }

    @PostMapping("/register")
    public RegisterWorkerResponse register(@Valid @RequestBody RegisterWorkerRequest request) {
        return workerService.register(request);
    }

    @PostMapping("/heartbeat")
    public WorkerHeartbeatResponse heartbeat(@Valid @RequestBody WorkerHeartbeatRequest request) {
        return workerService.heartbeat(request);
    }

    @GetMapping
    public List<WorkerNodeResponse> listWorkers() {
        return workerService.listWorkers();
    }

    @PostMapping("/{nodeId}/drain")
    public WorkerNodeResponse drain(@PathVariable UUID nodeId) {
        return workerService.updateNodeStatus(nodeId, NodeStatus.DRAINING);
    }

    @PostMapping("/{nodeId}/activate")
    public WorkerNodeResponse activate(@PathVariable UUID nodeId) {
        return workerService.updateNodeStatus(nodeId, NodeStatus.IDLE);
    }
}
