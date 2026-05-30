package com.aimusic.controlplane.service;

import com.qcloud.cos.COSClient;
import com.qcloud.cos.ClientConfig;
import com.qcloud.cos.auth.BasicCOSCredentials;
import com.qcloud.cos.auth.COSCredentials;
import com.qcloud.cos.http.HttpProtocol;
import com.qcloud.cos.model.PutObjectRequest;
import com.qcloud.cos.region.Region;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

@Service
public class CosStorageService {

    private final String region;
    private final String bucket;
    private final String secretId;
    private final String secretKey;
    private final String publicBaseUrl;

    public CosStorageService(
            @Value("${aimusic.cos.region}") String region,
            @Value("${aimusic.cos.bucket}") String bucket,
            @Value("${aimusic.cos.secret-id}") String secretId,
            @Value("${aimusic.cos.secret-key}") String secretKey,
            @Value("${aimusic.cos.public-base-url}") String publicBaseUrl
    ) {
        this.region = region;
        this.bucket = bucket;
        this.secretId = secretId;
        this.secretKey = secretKey;
        this.publicBaseUrl = publicBaseUrl;
    }

    public UploadedObject upload(MultipartFile file, String category) {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("Uploaded file is empty");
        }

        String originalFilename = StringUtils.cleanPath(file.getOriginalFilename() == null ? "asset.bin" : file.getOriginalFilename());
        String objectKey = buildObjectKey(category, originalFilename);
        File tempFile = null;
        COSClient client = createClient();

        try {
            tempFile = Files.createTempFile("aimusic-upload-", "-" + originalFilename).toFile();
            file.transferTo(tempFile);
            client.putObject(new PutObjectRequest(bucket, objectKey, tempFile));
            return new UploadedObject(objectKey, publicBaseUrl.endsWith("/")
                    ? publicBaseUrl + objectKey
                    : publicBaseUrl + "/" + objectKey);
        } catch (IOException exception) {
            throw new IllegalStateException("Failed to upload file to COS", exception);
        } finally {
            if (tempFile != null && tempFile.exists()) {
                tempFile.delete();
            }
            client.shutdown();
        }
    }

    private COSClient createClient() {
        COSCredentials credentials = new BasicCOSCredentials(secretId, secretKey);
        ClientConfig clientConfig = new ClientConfig(new Region(region));
        clientConfig.setHttpProtocol(HttpProtocol.https);
        return new COSClient(credentials, clientConfig);
    }

    private String buildObjectKey(String category, String filename) {
        String datePath = OffsetDateTime.now().format(DateTimeFormatter.ofPattern("yyyy/MM/dd"));
        return category + "/" + datePath + "/" + UUID.randomUUID() + "-" + filename.replaceAll("\\s+", "_");
    }

    public record UploadedObject(String objectKey, String publicUrl) {
    }
}

