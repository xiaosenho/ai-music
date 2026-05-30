import type { CreateJobPayload, DashboardSummary, Job, JobEvent, WorkerNode } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8092";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
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

