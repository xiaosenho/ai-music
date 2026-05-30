package com.aimusic.controlplane.service;

import com.qcloud.cos.COSClient;
import com.qcloud.cos.ClientConfig;
import com.qcloud.cos.auth.BasicCOSCredentials;
import com.qcloud.cos.auth.COSCredentials;
import com.qcloud.cos.http.HttpMethodName;
import com.qcloud.cos.http.HttpProtocol;
import com.qcloud.cos.model.GeneratePresignedUrlRequest;
import com.qcloud.cos.region.Region;
import java.net.URL;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.Date;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class CosStorageService {

    private final String region;
    private final String bucket;
    private final String secretId;
    private final String secretKey;
    private final String publicBaseUrl;
    private final long uploadTokenTtlSeconds;

    public CosStorageService(
            @Value("${aimusic.cos.region}") String region,
            @Value("${aimusic.cos.bucket}") String bucket,
            @Value("${aimusic.cos.secret-id}") String secretId,
            @Value("${aimusic.cos.secret-key}") String secretKey,
            @Value("${aimusic.cos.public-base-url}") String publicBaseUrl,
            @Value("${aimusic.cos.upload-token-ttl-seconds}") long uploadTokenTtlSeconds
    ) {
        this.region = region;
        this.bucket = bucket;
        this.secretId = secretId;
        this.secretKey = secretKey;
        this.publicBaseUrl = publicBaseUrl;
        this.uploadTokenTtlSeconds = uploadTokenTtlSeconds;
    }

    public DirectUploadTicket prepareDirectUpload(String fileName, String category) {
        String safeFileName = StringUtils.cleanPath(fileName == null ? "asset.bin" : fileName);
        String objectKey = buildObjectKey(category, safeFileName);
        OffsetDateTime expiresAt = OffsetDateTime.now().plusSeconds(uploadTokenTtlSeconds);
        COSClient client = createClient();

        try {
            GeneratePresignedUrlRequest request = new GeneratePresignedUrlRequest(bucket, objectKey, HttpMethodName.PUT);
            request.setExpiration(Date.from(expiresAt.toInstant()));
            URL uploadUrl = client.generatePresignedUrl(request);
            return new DirectUploadTicket(
                    objectKey,
                    publicUrlFor(objectKey),
                    uploadUrl.toString(),
                    Map.of(),
                    expiresAt
            );
        } finally {
            client.shutdown();
        }
    }

    public DirectDownloadTicket prepareDirectDownload(String objectKey) {
        String normalizedObjectKey = normalizeObjectKey(objectKey);
        OffsetDateTime expiresAt = OffsetDateTime.now().plusSeconds(uploadTokenTtlSeconds);
        COSClient client = createClient();

        try {
            GeneratePresignedUrlRequest request = new GeneratePresignedUrlRequest(bucket, normalizedObjectKey, HttpMethodName.GET);
            request.setExpiration(Date.from(expiresAt.toInstant()));
            URL downloadUrl = client.generatePresignedUrl(request);
            return new DirectDownloadTicket(normalizedObjectKey, downloadUrl.toString(), expiresAt);
        } finally {
            client.shutdown();
        }
    }

    public String publicUrlFor(String objectKey) {
        return publicBaseUrl.endsWith("/")
                ? publicBaseUrl + objectKey
                : publicBaseUrl + "/" + objectKey;
    }

    private COSClient createClient() {
        COSCredentials credentials = new BasicCOSCredentials(secretId, secretKey);
        ClientConfig clientConfig = new ClientConfig(new Region(region));
        clientConfig.setHttpProtocol(HttpProtocol.https);
        return new COSClient(credentials, clientConfig);
    }

    private String buildObjectKey(String category, String filename) {
        String datePath = OffsetDateTime.now(ZoneOffset.UTC).format(DateTimeFormatter.ofPattern("yyyy/MM/dd"));
        return category + "/" + datePath + "/" + UUID.randomUUID() + "-" + filename.replaceAll("\\s+", "_");
    }

    public String normalizeObjectKey(String reference) {
        if (reference == null || reference.isBlank()) {
            throw new IllegalArgumentException("Object key is blank");
        }

        String value = reference.trim();
        if (value.startsWith("cos://")) {
            value = value.substring("cos://".length());
            if (value.startsWith(bucket + "/")) {
                return value.substring(bucket.length() + 1);
            }
            return value;
        }

        String publicPrefix = publicBaseUrl.endsWith("/") ? publicBaseUrl : publicBaseUrl + "/";
        if (value.startsWith(publicPrefix)) {
            return value.substring(publicPrefix.length());
        }

        return value;
    }

    public record DirectUploadTicket(
            String objectKey,
            String publicUrl,
            String uploadUrl,
            Map<String, String> headers,
            OffsetDateTime expiresAt
    ) {
    }

    public record DirectDownloadTicket(
            String objectKey,
            String downloadUrl,
            OffsetDateTime expiresAt
    ) {
    }
}
