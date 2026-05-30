package com.aimusic.controlplane.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "job_events")
public class JobEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "job_id", nullable = false)
    private UUID jobId;

    @Column(name = "node_id")
    private UUID nodeId;

    @Column(name = "event_type", nullable = false, length = 32)
    private String eventType;

    @Column(name = "message", columnDefinition = "TEXT")
    private String message;

    @Column(name = "payload", columnDefinition = "TEXT")
    private String payload;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @PrePersist
    public void onCreate() {
        this.createdAt = OffsetDateTime.now();
    }

    public void setJobId(UUID jobId) {
        this.jobId = jobId;
    }

    public void setNodeId(UUID nodeId) {
        this.nodeId = nodeId;
    }

    public void setEventType(String eventType) {
        this.eventType = eventType;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public void setPayload(String payload) {
        this.payload = payload;
    }

    public Long getId() {
        return id;
    }

    public UUID getJobId() {
        return jobId;
    }

    public UUID getNodeId() {
        return nodeId;
    }

    public String getEventType() {
        return eventType;
    }

    public String getMessage() {
        return message;
    }

    public String getPayload() {
        return payload;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
