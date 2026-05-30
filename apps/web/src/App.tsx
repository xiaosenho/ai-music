import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type {
  CreateJobPayload,
  DashboardSummary,
  ExecutionMode,
  Job,
  JobEvent,
  JobType,
  WorkerNode,
} from "./types";

const REFRESH_INTERVAL_MS = 15000;

const EMPTY_SUMMARY: DashboardSummary = {
  totalWorkers: 0,
  onlineWorkers: 0,
  busyWorkers: 0,
  totalJobs: 0,
  queuedJobs: 0,
  runningJobs: 0,
  failedJobs: 0,
  workerStatusCounts: [],
  jobStatusCounts: [],
  jobTypeCounts: [],
};

const DEFAULT_FORM: CreateJobPayload = {
  jobType: "PROCESS",
  executionMode: "CLOUD",
  inputAssetIds: [],
  priority: 0,
  maxRetries: 3,
  payload: {},
};

export function App() {
  const [summary, setSummary] = useState<DashboardSummary>(EMPTY_SUMMARY);
  const [workers, setWorkers] = useState<WorkerNode[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobEvents, setJobEvents] = useState<JobEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [formState, setFormState] = useState<CreateJobPayload>(DEFAULT_FORM);

  async function loadData() {
    try {
      setError(null);
      const [summaryResponse, workersResponse, jobsResponse] = await Promise.all([
        api.getSummary(),
        api.getWorkers(),
        api.getJobs(),
      ]);
      setSummary(summaryResponse);
      setWorkers(workersResponse);
      setJobs(jobsResponse);
      setSelectedJobId((current) => current ?? jobsResponse[0]?.id ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
    const timer = window.setInterval(() => void loadData(), REFRESH_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedJobId) {
      setJobEvents([]);
      return;
    }

    setEventsLoading(true);
    api.getJobEvents(selectedJobId)
      .then(setJobEvents)
      .catch((eventsError) => {
        setError(eventsError instanceof Error ? eventsError.message : "Failed to load job events");
      })
      .finally(() => {
        setEventsLoading(false);
      });
  }, [selectedJobId]);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  );

  async function handleWorkerAction(nodeId: string, action: "drain" | "activate") {
    try {
      setSubmitMessage(null);
      if (action === "drain") {
        await api.drainWorker(nodeId);
      } else {
        await api.activateWorker(nodeId);
      }
      await loadData();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Worker action failed");
    }
  }

  async function handleCreateJob(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setSubmitMessage(null);
      setError(null);
      const payload: CreateJobPayload = {
        ...formState,
        inputAssetIds: formState.inputAssetIds,
        payload: formState.payload,
      };
      await api.createJob(payload);
      setSubmitMessage("任务已创建。");
      setFormState(DEFAULT_FORM);
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to create job");
    }
  }

  function updateForm<K extends keyof CreateJobPayload>(key: K, value: CreateJobPayload[K]) {
    setFormState((current) => ({
      ...current,
      [key]: value,
    }));
  }

  return (
    <div className="shell">
      <div className="backdrop backdrop-a" />
      <div className="backdrop backdrop-b" />

      <header className="hero">
        <div>
          <p className="eyebrow">AI AUDIO CONTROL PLANE</p>
          <h1>云端执行，本地扩展，围绕 AutoDL 的统一调度台。</h1>
          <p className="hero-copy">
            这里先把控制平面跑稳：节点注册、任务编排、状态流、事件审计。未来客户端本地推理也会沿用同一套任务体系。
          </p>
        </div>
        <div className="hero-side">
          <div className="status-chip">{loading ? "同步中" : "已连接"}</div>
          <p>默认每 15 秒自动刷新一次 summary、节点和任务列表。</p>
        </div>
      </header>

      {error ? <div className="banner error">{error}</div> : null}
      {submitMessage ? <div className="banner success">{submitMessage}</div> : null}

      <section className="metrics-grid">
        <MetricCard label="在线节点" value={summary.onlineWorkers} accent="teal" sub={`${summary.totalWorkers} total`} />
        <MetricCard label="忙碌节点" value={summary.busyWorkers} accent="orange" sub="正在处理任务" />
        <MetricCard label="排队任务" value={summary.queuedJobs} accent="blue" sub={`${summary.totalJobs} total`} />
        <MetricCard label="运行中任务" value={summary.runningJobs} accent="red" sub={`${summary.failedJobs} failed`} />
      </section>

      <section className="panel-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Dashboard</p>
              <h2>状态概览</h2>
            </div>
          </div>
          <div className="bars-grid">
            <StatusBlock title="节点状态" counts={summary.workerStatusCounts} />
            <StatusBlock title="任务状态" counts={summary.jobStatusCounts} />
            <StatusBlock title="任务类型" counts={summary.jobTypeCounts} />
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Scheduler</p>
              <h2>创建任务</h2>
            </div>
          </div>
          <form className="job-form" onSubmit={handleCreateJob}>
            <label>
              任务类型
              <select
                value={formState.jobType}
                onChange={(event) => updateForm("jobType", event.target.value as JobType)}
              >
                <option value="PROCESS">PROCESS</option>
                <option value="TRAIN">TRAIN</option>
                <option value="INFER">INFER</option>
              </select>
            </label>

            <label>
              执行模式
              <select
                value={formState.executionMode}
                onChange={(event) => updateForm("executionMode", event.target.value as ExecutionMode)}
              >
                <option value="CLOUD">CLOUD</option>
                <option value="LOCAL">LOCAL</option>
                <option value="AUTO">AUTO</option>
              </select>
            </label>

            <label>
              优先级
              <input
                type="number"
                value={formState.priority ?? 0}
                onChange={(event) => updateForm("priority", Number(event.target.value))}
              />
            </label>

            <label>
              数据集版本
              <input
                value={formState.datasetVersion ?? ""}
                onChange={(event) => updateForm("datasetVersion", event.target.value || undefined)}
                placeholder="dataset-v1"
              />
            </label>

            <label>
              模型版本
              <input
                value={formState.modelVersion ?? ""}
                onChange={(event) => updateForm("modelVersion", event.target.value || undefined)}
                placeholder="model-v3"
              />
            </label>

            <label className="span-2">
              输入资源 ID
              <textarea
                value={(formState.inputAssetIds ?? []).join("\n")}
                onChange={(event) =>
                  updateForm(
                    "inputAssetIds",
                    event.target.value
                      .split("\n")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  )
                }
                placeholder="一行一个 asset id"
              />
            </label>

            <label className="span-2">
              备注
              <textarea
                value={formState.note ?? ""}
                onChange={(event) => updateForm("note", event.target.value || undefined)}
                placeholder="任务意图、角色名、调度备注"
              />
            </label>

            <button type="submit" className="primary-button">
              创建任务
            </button>
          </form>
        </section>
      </section>

      <section className="panel-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Workers</p>
              <h2>执行节点</h2>
            </div>
          </div>
          <div className="worker-list">
            {workers.map((worker) => (
              <article key={worker.nodeId} className="worker-card">
                <div className="worker-head">
                  <div>
                    <h3>{worker.hostname}</h3>
                    <p>{worker.provider} · {worker.nodeType}</p>
                  </div>
                  <span className={`pill status-${worker.status.toLowerCase()}`}>{worker.status}</span>
                </div>
                <dl>
                  <div><dt>GPU</dt><dd>{worker.gpuName || "N/A"}</dd></div>
                  <div><dt>显存</dt><dd>{worker.vramMb} MB</dd></div>
                  <div><dt>支持任务</dt><dd>{worker.supportedJobTypes.join(", ")}</dd></div>
                  <div><dt>当前任务</dt><dd>{worker.runningJobId || "-"}</dd></div>
                </dl>
                <div className="worker-actions">
                  <button type="button" onClick={() => handleWorkerAction(worker.nodeId, "drain")}>
                    Drain
                  </button>
                  <button type="button" onClick={() => handleWorkerAction(worker.nodeId, "activate")}>
                    Activate
                  </button>
                </div>
              </article>
            ))}
            {!workers.length && <p className="empty">还没有注册节点。</p>}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Jobs</p>
              <h2>任务队列</h2>
            </div>
          </div>
          <div className="jobs-layout">
            <div className="job-list">
              {jobs.map((job) => (
                <button
                  key={job.id}
                  type="button"
                  className={`job-row ${selectedJobId === job.id ? "selected" : ""}`}
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div>
                    <strong>{job.jobType}</strong>
                    <span>{job.executionMode}</span>
                  </div>
                  <div>
                    <span className={`pill status-${job.status.toLowerCase()}`}>{job.status}</span>
                    <small>{job.progressPercent}%</small>
                  </div>
                </button>
              ))}
              {!jobs.length && <p className="empty">还没有任务。</p>}
            </div>

            <div className="job-detail">
              {selectedJob ? (
                <>
                  <div className="detail-card">
                    <h3>任务详情</h3>
                    <DetailLine label="Job ID" value={selectedJob.id} />
                    <DetailLine label="状态" value={selectedJob.status} />
                    <DetailLine label="执行模式" value={selectedJob.executionMode} />
                    <DetailLine label="节点" value={selectedJob.assignedNodeId || "-"} />
                    <DetailLine label="数据集" value={selectedJob.datasetVersion || "-"} />
                    <DetailLine label="模型" value={selectedJob.modelVersion || "-"} />
                    <DetailLine label="备注" value={selectedJob.note || "-"} />
                  </div>

                  <div className="detail-card">
                    <h3>事件流</h3>
                    {eventsLoading ? <p className="empty">载入事件中...</p> : null}
                    <div className="event-list">
                      {jobEvents.map((event) => (
                        <article key={event.id} className="event-item">
                          <div>
                            <strong>{event.eventType}</strong>
                            <p>{event.message || "无消息"}</p>
                          </div>
                          <time>{formatDate(event.createdAt)}</time>
                        </article>
                      ))}
                      {!eventsLoading && !jobEvents.length ? <p className="empty">暂无事件。</p> : null}
                    </div>
                  </div>
                </>
              ) : (
                <p className="empty">选择一个任务查看详情。</p>
              )}
            </div>
          </div>
        </section>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: number;
  sub: string;
  accent: "teal" | "orange" | "blue" | "red";
}) {
  return (
    <article className={`metric-card accent-${accent}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{sub}</span>
    </article>
  );
}

function StatusBlock({ title, counts }: { title: string; counts: Array<{ key: string; count: number }> }) {
  const max = Math.max(...counts.map((item) => item.count), 1);

  return (
    <div className="status-block">
      <h3>{title}</h3>
      <div className="status-list">
        {counts.map((item) => (
          <div key={item.key} className="status-row">
            <div className="status-meta">
              <span>{item.key}</span>
              <strong>{item.count}</strong>
            </div>
            <div className="status-bar">
              <div style={{ width: `${(item.count / max) * 100}%` }} />
            </div>
          </div>
        ))}
        {!counts.length && <p className="empty">暂无数据。</p>}
      </div>
    </div>
  );
}

function DetailLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-line">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN");
}

