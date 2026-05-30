import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type {
  AssetType,
  CreateInferJobPayload,
  CreateProcessJobPayload,
  CreateTrainJobPayload,
  DashboardSummary,
  Dataset,
  ExecutionMode,
  Job,
  JobEvent,
  MediaAsset,
  ModelVersion,
  WorkerNode,
} from "./types";

type ViewKey = "overview" | "upload" | "dataset" | "training" | "inference" | "nodes";

type UploadFormState = {
  assetType: AssetType;
  language: string;
  note: string;
};

type TrainFormState = CreateTrainJobPayload & {
  datasetId: string;
};

type InferFormState = CreateInferJobPayload & {
  modelVersionId: string;
};

const REFRESH_INTERVAL_MS = 15000;

const EMPTY_SUMMARY: DashboardSummary = {
  totalWorkers: 0,
  onlineWorkers: 0,
  busyWorkers: 0,
  totalJobs: 0,
  queuedJobs: 0,
  runningJobs: 0,
  failedJobs: 0,
  totalAssets: 0,
  totalDatasets: 0,
  readyDatasets: 0,
  totalModels: 0,
  readyModels: 0,
  workerStatusCounts: [],
  jobStatusCounts: [],
  jobTypeCounts: [],
};

const MENU = [
  { key: "overview", label: "总览", helper: "看节点、任务与产能", section: "控制台" },
  { key: "upload", label: "数据上传", helper: "上传原始素材到音频库", section: "数据流程" },
  { key: "dataset", label: "数据集处理", helper: "发起提纯、切片和审核流程", section: "数据流程" },
  { key: "training", label: "模型训练与保存", helper: "把 ready 数据集送去训练", section: "模型流程" },
  { key: "inference", label: "模型推理", helper: "发起云端或本地推理任务", section: "模型流程" },
  { key: "nodes", label: "执行节点", helper: "查看 AutoDL 与未来客户端执行器", section: "系统" },
] as const satisfies ReadonlyArray<{
  key: ViewKey;
  label: string;
  helper: string;
  section: string;
}>;

const MENU_SECTIONS: Array<{ section: string; items: typeof MENU[number][] }> = [
  { section: "控制台", items: MENU.filter((item) => item.section === "控制台") },
  { section: "数据流程", items: MENU.filter((item) => item.section === "数据流程") },
  { section: "模型流程", items: MENU.filter((item) => item.section === "模型流程") },
  { section: "系统", items: MENU.filter((item) => item.section === "系统") },
];

const DEFAULT_UPLOAD_FORM: UploadFormState = {
  assetType: "AUDIO",
  language: "zh-CN",
  note: "",
};

const DEFAULT_PROCESS_FORM: CreateProcessJobPayload = {
  assetIds: [],
  datasetName: "",
  language: "zh-CN",
  note: "",
};

const DEFAULT_TRAIN_FORM: TrainFormState = {
  datasetId: "",
  modelName: "",
  modelType: "RVC",
  sampleRate: 40000,
  f0Method: "rmvpe",
  batchSize: 8,
  totalEpoch: 300,
  speakerId: "0",
  version: "v2",
  useF0: true,
  saveEveryEpoch: 10,
  saveLatest: true,
  cacheGpu: false,
  saveEveryWeights: false,
  note: "",
};

const DEFAULT_INFER_FORM: InferFormState = {
  modelVersionId: "",
  inputAssetIds: [],
  executionMode: "CLOUD",
  speakerId: "0",
  f0Method: "rmvpe",
  f0UpKey: 0,
  indexRate: 0.66,
  filterRadius: 3,
  resampleSr: 0,
  rmsMixRate: 1,
  protect: 0.33,
  note: "",
};

export function App() {
  const [view, setView] = useState<ViewKey>("overview");
  const [summary, setSummary] = useState<DashboardSummary>(EMPTY_SUMMARY);
  const [workers, setWorkers] = useState<WorkerNode[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [models, setModels] = useState<ModelVersion[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobEvents, setJobEvents] = useState<JobEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [uploadForm, setUploadForm] = useState<UploadFormState>(DEFAULT_UPLOAD_FORM);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [processForm, setProcessForm] = useState<CreateProcessJobPayload>(DEFAULT_PROCESS_FORM);
  const [trainForm, setTrainForm] = useState<TrainFormState>(DEFAULT_TRAIN_FORM);
  const [inferForm, setInferForm] = useState<InferFormState>(DEFAULT_INFER_FORM);

  async function loadData() {
    try {
      setError(null);
      const [summaryResponse, workersResponse, jobsResponse, assetsResponse, datasetsResponse, modelsResponse] =
        await Promise.all([
          api.getSummary(),
          api.getWorkers(),
          api.getJobs(),
          api.getAssets(),
          api.getDatasets(),
          api.getModels(),
        ]);
      setSummary(summaryResponse);
      setWorkers(workersResponse);
      setJobs(jobsResponse);
      setAssets(assetsResponse);
      setDatasets(datasetsResponse);
      setModels(modelsResponse);
      setSelectedJobId((current) => current ?? jobsResponse[0]?.id ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败");
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
        setError(eventsError instanceof Error ? eventsError.message : "加载事件流失败");
      })
      .finally(() => {
        setEventsLoading(false);
      });
  }, [selectedJobId]);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  );
  const processJobs = useMemo(() => jobs.filter((job) => job.jobType === "PROCESS"), [jobs]);
  const trainingJobs = useMemo(() => jobs.filter((job) => job.jobType === "TRAIN"), [jobs]);
  const inferJobs = useMemo(() => jobs.filter((job) => job.jobType === "INFER"), [jobs]);
  const processableAssets = useMemo(
    () => assets.filter((asset) => asset.status === "UPLOADED" || asset.status === "APPROVED"),
    [assets],
  );
  const readyDatasets = useMemo(() => datasets.filter((dataset) => dataset.status === "READY"), [datasets]);
  const readyModels = useMemo(() => models.filter((model) => model.status === "READY"), [models]);
  const outputAssets = useMemo(
    () => assets.filter((asset) => asset.note?.includes("generated by infer job")),
    [assets],
  );

  async function handleWorkerAction(nodeId: string, action: "drain" | "activate") {
    try {
      setFlash(null);
      if (action === "drain") {
        await api.drainWorker(nodeId);
      } else {
        await api.activateWorker(nodeId);
      }
      await loadData();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "节点操作失败");
    }
  }

  async function handleUploadAsset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadFile) {
      setError("请选择要上传的文件。");
      return;
    }

    try {
      setFlash(null);
      const prepared = await api.prepareDirectUpload({
        fileName: uploadFile.name,
        assetType: uploadForm.assetType,
        contentType: uploadFile.type || undefined,
        sizeBytes: uploadFile.size,
        language: uploadForm.language.trim() || undefined,
        note: uploadForm.note.trim() || undefined,
      });
      await api.uploadFileToCos(prepared.uploadUrl, uploadFile, prepared.headers);
      await api.completeDirectUpload({
        fileName: uploadFile.name,
        assetType: uploadForm.assetType,
        objectKey: prepared.objectKey,
        contentType: uploadFile.type || undefined,
        sizeBytes: uploadFile.size,
        language: uploadForm.language.trim() || undefined,
        note: uploadForm.note.trim() || undefined,
        metadata: {
          uploadSource: "web-direct-cos",
        },
      });
      setUploadFile(null);
      setUploadForm(DEFAULT_UPLOAD_FORM);
      const fileInput = document.getElementById("asset-file-input") as HTMLInputElement | null;
      if (fileInput) {
        fileInput.value = "";
      }
      setFlash("素材已直传 COS，并完成元数据登记。");
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "素材上传失败");
    }
  }

  async function handleCreateProcessJob(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!processForm.assetIds.length) {
      setError("请至少选择一个待处理素材。");
      return;
    }
    if (!processForm.datasetName.trim()) {
      setError("请填写处理后生成的数据集名称。");
      return;
    }

    try {
      setFlash(null);
      await api.createProcessJob({
        assetIds: processForm.assetIds,
        datasetName: processForm.datasetName.trim(),
        language: processForm.language?.trim() || undefined,
        note: processForm.note?.trim() || undefined,
      });
      setProcessForm(DEFAULT_PROCESS_FORM);
      setFlash("处理任务已进入队列。");
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "处理任务创建失败");
    }
  }

  async function handleCreateTrainJob(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trainForm.datasetId) {
      setError("请先选择一个 ready 数据集。");
      return;
    }
    if (!trainForm.modelName.trim()) {
      setError("请填写模型名称。");
      return;
    }

    try {
      setFlash(null);
      await api.createTrainJob(trainForm.datasetId, {
        modelName: trainForm.modelName.trim(),
        modelType: trainForm.modelType.trim() || "RVC",
        sampleRate: trainForm.sampleRate,
        f0Method: trainForm.f0Method?.trim() || undefined,
        batchSize: trainForm.batchSize,
        totalEpoch: trainForm.totalEpoch,
        speakerId: trainForm.speakerId?.trim() || undefined,
        version: trainForm.version,
        useF0: trainForm.useF0,
        saveEveryEpoch: trainForm.saveEveryEpoch,
        saveLatest: trainForm.saveLatest,
        cacheGpu: trainForm.cacheGpu,
        saveEveryWeights: trainForm.saveEveryWeights,
        note: trainForm.note?.trim() || undefined,
      });
      setTrainForm(DEFAULT_TRAIN_FORM);
      setFlash("训练任务已提交到 AutoDL 队列。");
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "训练任务创建失败");
    }
  }

  async function handleCreateInferJob(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!inferForm.modelVersionId) {
      setError("请先选择一个 ready 模型。");
      return;
    }
    if (!inferForm.inputAssetIds.length) {
      setError("请至少选择一个输入素材。");
      return;
    }

    try {
      setFlash(null);
      await api.createInferJob(inferForm.modelVersionId, {
        inputAssetIds: inferForm.inputAssetIds,
        executionMode: inferForm.executionMode,
        speakerId: inferForm.speakerId?.trim() || undefined,
        f0Method: inferForm.f0Method?.trim() || undefined,
        f0UpKey: inferForm.f0UpKey,
        indexRate: inferForm.indexRate,
        filterRadius: inferForm.filterRadius,
        resampleSr: inferForm.resampleSr,
        rmsMixRate: inferForm.rmsMixRate,
        protect: inferForm.protect,
        note: inferForm.note?.trim() || undefined,
      });
      setInferForm((current) => ({
        ...DEFAULT_INFER_FORM,
        executionMode: current.executionMode,
      }));
      setFlash("推理任务已创建。");
      await loadData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "推理任务创建失败");
    }
  }

  async function handleDeleteAsset(assetId: string) {
    if (!window.confirm("确定删除这个素材记录吗？")) {
      return;
    }
    try {
      setFlash(null);
      await api.deleteAsset(assetId);
      setFlash("素材记录已删除。");
      await loadData();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "素材删除失败");
    }
  }

  async function handleDeleteDataset(datasetId: string) {
    if (!window.confirm("确定删除这个数据集吗？")) {
      return;
    }
    try {
      setFlash(null);
      await api.deleteDataset(datasetId);
      setFlash("数据集已删除。");
      await loadData();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "数据集删除失败");
    }
  }

  async function handleDeleteModel(modelVersionId: string) {
    if (!window.confirm("确定删除这个模型版本吗？")) {
      return;
    }
    try {
      setFlash(null);
      await api.deleteModel(modelVersionId);
      setFlash("模型版本已删除。");
      await loadData();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "模型删除失败");
    }
  }

  async function handleDownloadModel(modelVersionId: string) {
    try {
      setFlash(null);
      const ticket = await api.prepareModelDownload(modelVersionId);
      window.open(ticket.downloadUrl, "_blank", "noopener,noreferrer");
      setFlash("已生成模型下载链接。");
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "模型下载链接生成失败");
    }
  }

  function updateUploadForm<K extends keyof UploadFormState>(key: K, value: UploadFormState[K]) {
    setUploadForm((current) => ({ ...current, [key]: value }));
  }

  function updateProcessForm<K extends keyof CreateProcessJobPayload>(key: K, value: CreateProcessJobPayload[K]) {
    setProcessForm((current) => ({ ...current, [key]: value }));
  }

  function updateTrainForm<K extends keyof TrainFormState>(key: K, value: TrainFormState[K]) {
    setTrainForm((current) => ({ ...current, [key]: value }));
  }

  function updateInferForm<K extends keyof InferFormState>(key: K, value: InferFormState[K]) {
    setInferForm((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div className="brand">
          <p>AI MUSIC OPS</p>
          <h1>Voice Factory</h1>
          <span>{loading ? "同步中" : "控制平面在线"}</span>
        </div>

        {MENU_SECTIONS.map(({ section, items }) => (
          <div key={section} className="menu-section">
            <p className="menu-title">{section}</p>
            {items.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`menu-item ${view === item.key ? "active" : ""}`}
                onClick={() => setView(item.key)}
              >
                <strong>{item.label}</strong>
                <span>{item.helper}</span>
              </button>
            ))}
          </div>
        ))}
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <p className="workspace-kicker">AI Audio Admin</p>
            <h2>{MENU.find((item) => item.key === view)?.label}</h2>
          </div>
          <div className="workspace-summary">
            <span>{summary.onlineWorkers} 节点在线</span>
            <span>{summary.runningJobs} 任务运行中</span>
            <span>{summary.readyModels} 个可用模型</span>
          </div>
        </header>

        {error ? <div className="banner error">{error}</div> : null}
        {flash ? <div className="banner success">{flash}</div> : null}

        {view === "overview" ? (
          <section className="view-stack">
            <section className="metric-grid">
              <MetricCard label="素材总数" value={summary.totalAssets} accent="green" sub="原始与产出素材" />
              <MetricCard label="数据集" value={summary.totalDatasets} accent="blue" sub={`${summary.readyDatasets} ready`} />
              <MetricCard label="模型数" value={summary.totalModels} accent="orange" sub={`${summary.readyModels} ready`} />
              <MetricCard label="节点在线" value={summary.onlineWorkers} accent="red" sub={`${summary.busyWorkers} busy`} />
            </section>

            <section className="three-column">
              <Panel title="任务状态" subtitle="当前调度态势">
                <StatusRail counts={summary.jobStatusCounts} />
              </Panel>
              <Panel title="任务类型" subtitle="按流程拆分">
                <StatusRail counts={summary.jobTypeCounts} />
              </Panel>
              <Panel title="流程进度" subtitle="当前业务库存">
                <div className="detail-stack compact">
                  <DetailLine label="待处理素材" value={`${processableAssets.length}`} />
                  <DetailLine label="Ready 数据集" value={`${readyDatasets.length}`} />
                  <DetailLine label="Ready 模型" value={`${readyModels.length}`} />
                  <DetailLine label="推理产物" value={`${outputAssets.length}`} />
                </div>
              </Panel>
            </section>

            <Panel title="最新任务" subtitle="点击任意任务即可查看事件流">
              <JobTable jobs={jobs.slice(0, 8)} onSelect={setSelectedJobId} selectedJobId={selectedJobId} />
            </Panel>
          </section>
        ) : null}

        {view === "upload" ? (
          <section className="view-stack">
            <section className="two-column">
              <Panel title="上传素材" subtitle="前端直传 COS，后端只保存素材基本信息">
                <form className="admin-form" onSubmit={handleUploadAsset}>
                  <Field label="选择文件" full>
                    <input
                      id="asset-file-input"
                      type="file"
                      accept="audio/*,video/*,.zip"
                      onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                    />
                  </Field>
                  <Field label="素材类型">
                    <select
                      value={uploadForm.assetType}
                      onChange={(event) => updateUploadForm("assetType", event.target.value as AssetType)}
                    >
                      <option value="AUDIO">AUDIO</option>
                      <option value="VIDEO">VIDEO</option>
                      <option value="ZIP">ZIP</option>
                    </select>
                  </Field>
                  <Field label="语言">
                    <input
                      value={uploadForm.language}
                      onChange={(event) => updateUploadForm("language", event.target.value)}
                      placeholder="zh-CN"
                    />
                  </Field>
                  <Field label="备注" full>
                    <textarea
                      value={uploadForm.note}
                      onChange={(event) => updateUploadForm("note", event.target.value)}
                      placeholder="例如：角色素材、直播切片、对白合集"
                    />
                  </Field>
                  <button className="primary-action" type="submit">上传并登记</button>
                </form>
              </Panel>

              <Panel title="上传说明" subtitle="建议先把原始素材堆到这里，再进入处理流程">
                <div className="detail-stack compact">
                  <DetailLine label="可处理素材" value={`${processableAssets.length}`} />
                  <DetailLine label="已审核素材" value={`${assets.filter((asset) => asset.status === "APPROVED").length}`} />
                  <DetailLine label="当前输出素材" value={`${outputAssets.length}`} />
                </div>
                <p className="helper-text">
                  建议把同一角色、同一语种的素材分批上传，后续在“数据集处理”里一次性发起提纯与切片。
                </p>
              </Panel>
            </section>

            <Panel title="素材列表" subtitle="上传成功后会出现在这里">
              <AssetTable assets={assets} onDelete={handleDeleteAsset} />
            </Panel>
          </section>
        ) : null}

        {view === "dataset" ? (
          <section className="view-stack">
            <section className="two-column">
              <Panel title="发起处理任务" subtitle="把上传素材送入清洗、降噪、切片流程">
                <form className="admin-form" onSubmit={handleCreateProcessJob}>
                  <Field label="输出数据集名称">
                    <input
                      value={processForm.datasetName}
                      onChange={(event) => updateProcessForm("datasetName", event.target.value)}
                      placeholder="例如：hanser-clean-v1"
                    />
                  </Field>
                  <Field label="语言">
                    <input
                      value={processForm.language ?? ""}
                      onChange={(event) => updateProcessForm("language", event.target.value)}
                      placeholder="zh-CN"
                    />
                  </Field>
                  <Field label="选择素材" full>
                    <SelectionGrid
                      items={processableAssets.map((asset) => ({
                        id: asset.id,
                        title: asset.name,
                        meta: `${asset.assetType} · ${asset.status}`,
                      }))}
                      selectedIds={processForm.assetIds}
                      onChange={(assetIds) => updateProcessForm("assetIds", assetIds)}
                    />
                  </Field>
                  <Field label="备注" full>
                    <textarea
                      value={processForm.note ?? ""}
                      onChange={(event) => updateProcessForm("note", event.target.value)}
                      placeholder="例如：优先保留独白，过滤背景音乐"
                    />
                  </Field>
                  <button className="primary-action" type="submit">创建处理任务</button>
                </form>
              </Panel>

              <Panel title="处理任务队列" subtitle="PROCESS 任务会在 AutoDL 上执行">
                <JobListCard title="PROCESS 任务" jobs={processJobs} onSelect={setSelectedJobId} selectedJobId={selectedJobId} />
              </Panel>
            </section>

            <Panel title="数据集列表" subtitle="处理完成的数据集会沉淀到这里">
              <DatasetTable datasets={datasets} onDelete={handleDeleteDataset} />
            </Panel>
          </section>
        ) : null}

        {view === "training" ? (
          <section className="view-stack">
            <section className="two-column">
              <Panel title="发起训练任务" subtitle="训练任务会自动创建模型版本草稿并跟踪状态">
                <form className="admin-form" onSubmit={handleCreateTrainJob}>
                  <Field label="选择数据集">
                    <select
                      value={trainForm.datasetId}
                      onChange={(event) => updateTrainForm("datasetId", event.target.value)}
                    >
                      <option value="">请选择 ready 数据集</option>
                      {readyDatasets.map((dataset) => (
                        <option key={dataset.id} value={dataset.id}>
                          {dataset.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="模型名称">
                    <input
                      value={trainForm.modelName}
                      onChange={(event) => updateTrainForm("modelName", event.target.value)}
                      placeholder="例如：hanser-rvc-v1"
                    />
                  </Field>
                  <Field label="模型类型">
                    <input
                      value={trainForm.modelType}
                      onChange={(event) => updateTrainForm("modelType", event.target.value)}
                    />
                  </Field>
                  <Field label="采样率" helper="决定模型目标音频质量与资源消耗。RVC v2 常用 40k，唱歌或高频细节更多时可以考虑 48k。">
                    <input
                      type="number"
                      value={trainForm.sampleRate ?? 40000}
                      onChange={(event) => updateTrainForm("sampleRate", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="F0 方法" helper="音高提取算法。`rmvpe` 通常是当前最稳的默认值，唱歌和较复杂语音都更适合。">
                    <input
                      value={trainForm.f0Method ?? ""}
                      onChange={(event) => updateTrainForm("f0Method", event.target.value)}
                    />
                  </Field>
                  <Field label="模型版本" helper="你当前这套 WebUI V4 工作流下，实际训练版本仍然是 v1 或 v2，常规推荐使用 v2。">
                    <select
                      value={trainForm.version ?? "v2"}
                      onChange={(event) => updateTrainForm("version", event.target.value as "v1" | "v2")}
                    >
                      <option value="v1">v1</option>
                      <option value="v2">v2</option>
                    </select>
                  </Field>
                  <Field label="启用 F0" helper="唱歌和需要强音高约束的角色建议开启；普通口播也通常建议开启，除非你明确要训练无 F0 模型。">
                    <select
                      value={trainForm.useF0 ? "true" : "false"}
                      onChange={(event) => updateTrainForm("useF0", event.target.value === "true")}
                    >
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </Field>
                  <Field label="Batch Size" helper="每张显卡单次喂入的样本数量。越大通常越快，但更吃显存，爆显存时先降这个值。">
                    <input
                      type="number"
                      value={trainForm.batchSize ?? 8}
                      onChange={(event) => updateTrainForm("batchSize", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="Epoch" helper="总训练轮数。轮数越高越可能拟合角色音色，但过高也可能带来过拟合和训练时间增加。">
                    <input
                      type="number"
                      value={trainForm.totalEpoch ?? 300}
                      onChange={(event) => updateTrainForm("totalEpoch", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="说话人 ID" helper="多说话人训练时用于指定角色编号。当前单角色训练一般保持 0 即可。">
                    <input
                      value={trainForm.speakerId ?? "0"}
                      onChange={(event) => updateTrainForm("speakerId", event.target.value)}
                    />
                  </Field>
                  <Field label="保存间隔" helper="每训练多少个 epoch 保存一次检查点。值越小越方便中途观察，但会增加磁盘写入。">
                    <input
                      type="number"
                      value={trainForm.saveEveryEpoch ?? 10}
                      onChange={(event) => updateTrainForm("saveEveryEpoch", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="仅保留最新 ckpt" helper="开启后节省磁盘空间，适合正式跑长任务；关闭后更方便回看中间训练阶段。">
                    <select
                      value={trainForm.saveLatest ? "true" : "false"}
                      onChange={(event) => updateTrainForm("saveLatest", event.target.value === "true")}
                    >
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </Field>
                  <Field label="缓存训练集到显存" helper="小数据集能提速，但非常吃显存。显存紧张时建议关闭。">
                    <select
                      value={trainForm.cacheGpu ? "true" : "false"}
                      onChange={(event) => updateTrainForm("cacheGpu", event.target.value === "true")}
                    >
                      <option value="false">否</option>
                      <option value="true">是</option>
                    </select>
                  </Field>
                  <Field label="每次保存都导出小模型" helper="开启后每个保存点都会产出可直接用的小模型，方便中途试听，但会占更多空间。">
                    <select
                      value={trainForm.saveEveryWeights ? "true" : "false"}
                      onChange={(event) => updateTrainForm("saveEveryWeights", event.target.value === "true")}
                    >
                      <option value="false">否</option>
                      <option value="true">是</option>
                    </select>
                  </Field>
                  <Field label="备注" full>
                    <textarea
                      value={trainForm.note ?? ""}
                      onChange={(event) => updateTrainForm("note", event.target.value)}
                      placeholder="例如：偏高音角色、适合旁白"
                    />
                  </Field>
                  <button className="primary-action" type="submit">创建训练任务</button>
                </form>
              </Panel>

              <Panel title="训练任务" subtitle="查看 AutoDL 训练进度与失败重试">
                <JobListCard title="TRAIN 任务" jobs={trainingJobs} onSelect={setSelectedJobId} selectedJobId={selectedJobId} />
              </Panel>
            </section>

            <Panel title="模型版本列表" subtitle="训练完成后自动沉淀到模型库">
              <ModelTable models={models} onDownload={handleDownloadModel} onDelete={handleDeleteModel} />
            </Panel>
          </section>
        ) : null}

        {view === "inference" ? (
          <section className="view-stack">
            <section className="two-column">
              <Panel title="发起推理任务" subtitle="支持云端执行，也为未来客户端本地推理预留入口">
                <form className="admin-form" onSubmit={handleCreateInferJob}>
                  <Field label="选择模型">
                    <select
                      value={inferForm.modelVersionId}
                      onChange={(event) => updateInferForm("modelVersionId", event.target.value)}
                    >
                      <option value="">请选择 ready 模型</option>
                      {readyModels.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="执行模式" helper="当前一般选择 CLOUD 交给 AutoDL。LOCAL 是给未来客户端本地推理预留的入口。">
                    <select
                      value={inferForm.executionMode}
                      onChange={(event) => updateInferForm("executionMode", event.target.value as ExecutionMode)}
                    >
                      <option value="CLOUD">CLOUD</option>
                      <option value="LOCAL">LOCAL</option>
                      <option value="AUTO">AUTO</option>
                    </select>
                  </Field>
                  <Field label="输入素材" helper="选择要做声线转换的原始音频。当前会以第一条输入素材作为主输出目标。" full>
                    <SelectionGrid
                      items={assets.map((asset) => ({
                        id: asset.id,
                        title: asset.name,
                        meta: `${asset.assetType} · ${asset.status}`,
                      }))}
                      selectedIds={inferForm.inputAssetIds}
                      onChange={(inputAssetIds) => updateInferForm("inputAssetIds", inputAssetIds)}
                    />
                  </Field>
                  <Field label="说话人 ID" helper="多说话人模型时用于切换目标说话人。单角色模型通常保持 0 即可。">
                    <input
                      value={inferForm.speakerId ?? "0"}
                      onChange={(event) => updateInferForm("speakerId", event.target.value)}
                    />
                  </Field>
                  <Field label="F0 方法" helper="推理时的音高提取算法。通常推荐 `rmvpe`，如果你有特别需求再尝试其它方法。">
                    <input
                      value={inferForm.f0Method ?? "rmvpe"}
                      onChange={(event) => updateInferForm("f0Method", event.target.value)}
                    />
                  </Field>
                  <Field label="变调（f0_up_key）" helper="以半音为单位升降调，男转女常见 +12，女转男常见 -12，普通同音域配音一般保持 0。">
                    <input
                      type="number"
                      value={inferForm.f0UpKey ?? 0}
                      onChange={(event) => updateInferForm("f0UpKey", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="索引占比" helper="越高越依赖检索库来贴近目标音色，通常 0.5 到 0.8 比较稳，太高可能带来奇怪口型感。">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={inferForm.indexRate ?? 0.66}
                      onChange={(event) => updateInferForm("indexRate", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="滤波半径" helper="主要影响 harvest 一类音高结果的平滑度。常见默认值是 3，越大越平滑。">
                    <input
                      type="number"
                      value={inferForm.filterRadius ?? 3}
                      onChange={(event) => updateInferForm("filterRadius", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="重采样输出" helper="设为 0 表示保持模型默认采样率；设为 16000 以上则会在输出阶段重采样到指定值。">
                    <input
                      type="number"
                      value={inferForm.resampleSr ?? 0}
                      onChange={(event) => updateInferForm("resampleSr", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="包络混合比" helper="控制输出音量包络与原始包络的融合程度。越接近 1 越偏向模型输出包络。">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={inferForm.rmsMixRate ?? 1}
                      onChange={(event) => updateInferForm("rmsMixRate", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="Protect" helper="保护清辅音、呼吸声和边缘细节。越低保护越强，但过低可能削弱索引效果，常用 0.33。">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="0.5"
                      value={inferForm.protect ?? 0.33}
                      onChange={(event) => updateInferForm("protect", Number(event.target.value))}
                    />
                  </Field>
                  <Field label="备注" full>
                    <textarea
                      value={inferForm.note ?? ""}
                      onChange={(event) => updateInferForm("note", event.target.value)}
                      placeholder="例如：第一版成品、保留呼吸声"
                    />
                  </Field>
                  <button className="primary-action" type="submit">创建推理任务</button>
                </form>
              </Panel>

              <Panel title="事件流" subtitle="观察当前选中任务的节点回报">
                {selectedJob ? (
                  <>
                    <div className="detail-stack">
                      <DetailLine label="任务 ID" value={selectedJob.id} />
                      <DetailLine label="状态" value={selectedJob.status} />
                      <DetailLine label="执行模式" value={selectedJob.executionMode} />
                      <DetailLine label="模型版本" value={selectedJob.modelVersion || "-"} />
                    </div>
                    <div className="event-stream">
                      {eventsLoading ? <p className="empty-state">事件流载入中...</p> : null}
                      {jobEvents.map((event) => (
                        <article key={event.id} className="event-entry">
                          <div>
                            <strong>{event.eventType}</strong>
                            <p>{event.message || "无说明"}</p>
                          </div>
                          <time>{formatDate(event.createdAt)}</time>
                        </article>
                      ))}
                      {!eventsLoading && !jobEvents.length ? <p className="empty-state">还没有事件。</p> : null}
                    </div>
                  </>
                ) : (
                  <p className="empty-state">先从下方任务表选择一个任务。</p>
                )}
              </Panel>
            </section>

            <section className="two-column">
              <Panel title="推理任务队列" subtitle="推理任务会产出新的音频资产">
                <JobTable jobs={inferJobs} onSelect={setSelectedJobId} selectedJobId={selectedJobId} />
              </Panel>
              <Panel title="推理输出" subtitle="Worker 上报成功后自动登记回素材库">
                <AssetTable assets={outputAssets} compact onDelete={handleDeleteAsset} />
              </Panel>
            </section>
          </section>
        ) : null}

        {view === "nodes" ? (
          <section className="view-stack">
            <section className="two-column">
              <Panel title="执行节点" subtitle="AutoDL 与未来本地执行器">
                <WorkerTable workers={workers} onAction={handleWorkerAction} />
              </Panel>
              <Panel title="节点状态分布" subtitle="用于判断当前可用算力">
                <StatusRail counts={summary.workerStatusCounts} />
              </Panel>
            </section>
          </section>
        ) : null}
      </main>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  children,
  helper,
  full = false,
}: {
  label: string;
  children: React.ReactNode;
  helper?: string;
  full?: boolean;
}) {
  return (
    <label className={`field ${full ? "field-full" : ""}`}>
      <span>{label}</span>
      {children}
      {helper ? <small className="field-help">{helper}</small> : null}
    </label>
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
  accent: "green" | "blue" | "orange" | "red";
}) {
  return (
    <article className={`metric-card accent-${accent}`}>
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{sub}</span>
    </article>
  );
}

function StatusRail({ counts }: { counts: Array<{ key: string; count: number }> }) {
  const max = Math.max(...counts.map((item) => item.count), 1);
  return (
    <div className="status-rail">
      {counts.map((item) => (
        <div key={item.key} className="status-row">
          <div className="status-labels">
            <span>{item.key}</span>
            <strong>{item.count}</strong>
          </div>
          <div className="status-bar">
            <div style={{ width: `${(item.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
      {!counts.length ? <p className="empty-state">暂无状态数据。</p> : null}
    </div>
  );
}

function SelectionGrid({
  items,
  selectedIds,
  onChange,
}: {
  items: Array<{ id: string; title: string; meta: string }>;
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  function toggle(id: string) {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((item) => item !== id));
      return;
    }
    onChange([...selectedIds, id]);
  }

  return (
    <div className="selection-grid">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`selection-card ${selectedIds.includes(item.id) ? "selected" : ""}`}
          onClick={() => toggle(item.id)}
        >
          <strong>{item.title}</strong>
          <span>{item.meta}</span>
          <small>{item.id}</small>
        </button>
      ))}
      {!items.length ? <p className="empty-state">当前没有可选项。</p> : null}
    </div>
  );
}

function AssetTable({
  assets,
  compact = false,
  onDelete,
}: {
  assets: MediaAsset[];
  compact?: boolean;
  onDelete: (assetId: string) => void;
}) {
  return (
    <div className="table-shell">
      <table className={`admin-table ${compact ? "compact-table" : ""}`}>
        <thead>
          <tr>
            <th>名称</th>
            <th>类型</th>
            <th>状态</th>
            <th>来源</th>
            <th>时长</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <tr key={asset.id}>
              <td>{asset.name}</td>
              <td>{asset.assetType}</td>
              <td><span className={`pill status-${asset.status.toLowerCase()}`}>{asset.status}</span></td>
              <td className="truncate">{renderSourceValue(asset.sourceUri || asset.objectKey || null)}</td>
              <td>{asset.durationSeconds ?? "-"}</td>
              <td>{formatDate(asset.createdAt)}</td>
              <td>
                <div className="inline-actions">
                  <button type="button" onClick={() => onDelete(asset.id)}>删除</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!assets.length ? <p className="empty-state">还没有素材记录。</p> : null}
    </div>
  );
}

function DatasetTable({
  datasets,
  onDelete,
}: {
  datasets: Dataset[];
  onDelete: (datasetId: string) => void;
}) {
  return (
    <div className="table-shell">
      <table className="admin-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>状态</th>
            <th>素材数</th>
            <th>片段数</th>
            <th>语言</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((dataset) => (
            <tr key={dataset.id}>
              <td>{dataset.name}</td>
              <td><span className={`pill status-${dataset.status.toLowerCase()}`}>{dataset.status}</span></td>
              <td>{dataset.assetIds.length}</td>
              <td>{dataset.segmentCount}</td>
              <td>{dataset.language || "-"}</td>
              <td>{formatDate(dataset.createdAt)}</td>
              <td>
                <div className="inline-actions">
                  <button type="button" onClick={() => onDelete(dataset.id)}>删除</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!datasets.length ? <p className="empty-state">还没有数据集。</p> : null}
    </div>
  );
}

function ModelTable({
  models,
  onDownload,
  onDelete,
}: {
  models: ModelVersion[];
  onDownload: (modelVersionId: string) => void;
  onDelete: (modelVersionId: string) => void;
}) {
  return (
    <div className="table-shell">
      <table className="admin-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>状态</th>
            <th>类型</th>
            <th>数据集</th>
            <th>存储路径</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr key={model.id}>
              <td>{model.name}</td>
              <td><span className={`pill status-${model.status.toLowerCase()}`}>{model.status}</span></td>
              <td>{model.modelType}</td>
              <td>{model.datasetId || "-"}</td>
              <td className="truncate">{renderSourceValue(model.storagePath)}</td>
              <td>
                <div className="inline-actions">
                  {model.storagePath ? (
                    <button type="button" onClick={() => onDownload(model.id)}>下载模型</button>
                  ) : (
                    <span>-</span>
                  )}
                  {model.sampleAudioUrl ? (
                    <a href={model.sampleAudioUrl} target="_blank" rel="noreferrer">
                      试听
                    </a>
                  ) : null}
                  <button type="button" onClick={() => onDelete(model.id)}>删除</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!models.length ? <p className="empty-state">还没有模型版本。</p> : null}
    </div>
  );
}

function JobTable({
  jobs,
  onSelect,
  selectedJobId,
}: {
  jobs: Job[];
  onSelect: (jobId: string) => void;
  selectedJobId: string | null;
}) {
  return (
    <div className="table-shell">
      <table className="admin-table">
        <thead>
          <tr>
            <th>任务类型</th>
            <th>状态</th>
            <th>执行模式</th>
            <th>版本</th>
            <th>进度</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.id}
              className={selectedJobId === job.id ? "selected-row" : ""}
              onClick={() => onSelect(job.id)}
            >
              <td>{job.jobType}</td>
              <td><span className={`pill status-${job.status.toLowerCase()}`}>{job.status}</span></td>
              <td>{job.executionMode}</td>
              <td>{job.modelVersion || job.datasetVersion || "-"}</td>
              <td>{job.progressPercent}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!jobs.length ? <p className="empty-state">当前没有任务。</p> : null}
    </div>
  );
}

function JobListCard({
  title,
  jobs,
  onSelect,
  selectedJobId,
}: {
  title: string;
  jobs: Job[];
  onSelect: (jobId: string) => void;
  selectedJobId: string | null;
}) {
  return (
    <>
      <p className="mini-title">{title}</p>
      <JobTable jobs={jobs} onSelect={onSelect} selectedJobId={selectedJobId} />
    </>
  );
}

function WorkerTable({
  workers,
  onAction,
}: {
  workers: WorkerNode[];
  onAction: (nodeId: string, action: "drain" | "activate") => void;
}) {
  return (
    <div className="worker-grid">
      {workers.map((worker) => (
        <article key={worker.nodeId} className="worker-card">
          <div className="worker-top">
            <div>
              <h4>{worker.hostname}</h4>
              <p>{worker.provider} · {worker.nodeType}</p>
            </div>
            <span className={`pill status-${worker.status.toLowerCase()}`}>{worker.status}</span>
          </div>
          <div className="worker-meta">
            <span>GPU: {worker.gpuName || "N/A"}</span>
            <span>显存: {worker.vramMb} MB</span>
            <span>任务: {worker.runningJobId || "-"}</span>
          </div>
          <div className="worker-actions">
            <button type="button" onClick={() => onAction(worker.nodeId, "drain")}>Drain</button>
            <button type="button" onClick={() => onAction(worker.nodeId, "activate")}>Activate</button>
          </div>
        </article>
      ))}
      {!workers.length ? <p className="empty-state">还没有注册节点。</p> : null}
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
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function renderSourceValue(value: string | null) {
  if (!value) return "-";
  if (/^https?:\/\//i.test(value)) {
    return (
      <a href={value} target="_blank" rel="noreferrer">
        {value}
      </a>
    );
  }
  return value;
}
