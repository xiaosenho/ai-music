import type {
  CompleteDirectUploadPayload,
  CreateDatasetPayload,
  CreateInferJobPayload,
  CreateJobPayload,
  CreateMediaAssetPayload,
  CreateModelVersionPayload,
  CreateProcessJobPayload,
  CreateTrainJobPayload,
  DashboardSummary,
  Dataset,
  Job,
  JobEvent,
  MediaAsset,
  ModelVersion,
  PrepareDirectUploadPayload,
  PrepareDirectUploadResponse,
  WorkerNode,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8092";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  getSummary: () => request<DashboardSummary>("/api/v1/dashboard/summary"),
  getAssets: () => request<MediaAsset[]>("/api/v1/assets"),
  createAsset: (payload: CreateMediaAssetPayload) =>
    request<MediaAsset>("/api/v1/assets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  prepareDirectUpload: (payload: PrepareDirectUploadPayload) =>
    request<PrepareDirectUploadResponse>("/api/v1/assets/upload-prepare", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  uploadFileToCos: async (uploadUrl: string, file: File, headers: Record<string, string>) => {
    const response = await fetch(uploadUrl, {
      method: "PUT",
      headers: {
        ...(file.type ? { "Content-Type": file.type } : {}),
        ...headers,
      },
      body: file,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `COS upload failed: ${response.status}`);
    }
  },
  completeDirectUpload: (payload: CompleteDirectUploadPayload) =>
    request<MediaAsset>("/api/v1/assets/upload-complete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createProcessJob: (payload: CreateProcessJobPayload) =>
    request<Job>("/api/v1/assets/process-jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDatasets: () => request<Dataset[]>("/api/v1/datasets"),
  createDataset: (payload: CreateDatasetPayload) =>
    request<Dataset>("/api/v1/datasets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createTrainJob: (datasetId: string, payload: CreateTrainJobPayload) =>
    request<Job>(`/api/v1/datasets/${datasetId}/train-jobs`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getModels: () => request<ModelVersion[]>("/api/v1/models"),
  createModelVersion: (payload: CreateModelVersionPayload) =>
    request<ModelVersion>("/api/v1/models", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createInferJob: (modelVersionId: string, payload: CreateInferJobPayload) =>
    request<Job>(`/api/v1/models/${modelVersionId}/infer-jobs`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getWorkers: () => request<WorkerNode[]>("/api/v1/workers"),
  drainWorker: (nodeId: string) => request<WorkerNode>(`/api/v1/workers/${nodeId}/drain`, { method: "POST" }),
  activateWorker: (nodeId: string) => request<WorkerNode>(`/api/v1/workers/${nodeId}/activate`, { method: "POST" }),
  getJobs: () => request<Job[]>("/api/v1/jobs"),
  getJobEvents: (jobId: string) => request<JobEvent[]>(`/api/v1/jobs/${jobId}/events`),
  createJob: (payload: CreateJobPayload) =>
    request<Job>("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
