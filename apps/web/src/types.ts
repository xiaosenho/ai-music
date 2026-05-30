export type NodeStatus = "OFFLINE" | "IDLE" | "BUSY" | "DRAINING" | "ERROR";
export type NodeType = "AUTODL" | "CLIENT_LOCAL";
export type JobType = "PROCESS" | "TRAIN" | "INFER";
export type ExecutionMode = "CLOUD" | "LOCAL" | "AUTO";
export type JobStatus =
  | "PENDING"
  | "QUEUED"
  | "LEASED"
  | "RUNNING"
  | "UPLOADING"
  | "SUCCEEDED"
  | "FAILED"
  | "RETRY_WAITING"
  | "CANCELLED";

export interface StatusCount {
  key: string;
  count: number;
}

export interface DashboardSummary {
  totalWorkers: number;
  onlineWorkers: number;
  busyWorkers: number;
  totalJobs: number;
  queuedJobs: number;
  runningJobs: number;
  failedJobs: number;
  workerStatusCounts: StatusCount[];
  jobStatusCounts: StatusCount[];
  jobTypeCounts: StatusCount[];
}

export interface WorkerNode {
  nodeId: string;
  nodeType: NodeType;
  hostname: string;
  provider: string;
  gpuName: string;
  gpuCount: number;
  vramMb: number;
  status: NodeStatus;
  supportedJobTypes: string[];
  workerVersion: string;
  runningJobId: string | null;
  lastSeenAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Job {
  id: string;
  characterId: string | null;
  jobType: JobType;
  executionMode: ExecutionMode;
  status: JobStatus;
  priority: number;
  targetNodeId: string | null;
  assignedNodeId: string | null;
  inputAssetIds: string[];
  datasetVersion: string | null;
  modelVersion: string | null;
  sampleRate: number | null;
  f0Method: string | null;
  batchSize: number | null;
  totalEpoch: number | null;
  speakerId: string | null;
  retryCount: number;
  progressPercent: number;
  payload: string | null;
  resultManifest: string | null;
  note: string | null;
  errorMessage: string | null;
  leaseExpiresAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface JobEvent {
  id: number;
  jobId: string;
  nodeId: string | null;
  eventType: string;
  message: string | null;
  payload: string | null;
  createdAt: string;
}

export interface CreateJobPayload {
  characterId?: string;
  jobType: JobType;
  executionMode: ExecutionMode;
  priority?: number;
  targetNodeId?: string;
  inputAssetIds: string[];
  datasetVersion?: string;
  modelVersion?: string;
  sampleRate?: number;
  f0Method?: string;
  batchSize?: number;
  totalEpoch?: number;
  speakerId?: string;
  maxRetries?: number;
  note?: string;
  payload?: Record<string, unknown>;
}

