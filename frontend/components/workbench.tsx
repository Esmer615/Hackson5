'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  FileText,
  Loader2,
  MessageSquareText,
  Rocket,
  ShieldCheck,
  Sparkles,
  Upload,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { GraphView } from '@/components/graph-view';
import {
  getGraph,
  getPipelineStatus,
  getReport,
  queryRag,
  runPipeline,
  sendTeacherFeedback,
  uploadTextbooks,
} from '@/lib/api';
import type {
  GraphData,
  GraphNode,
  PipelineStatus,
  ProcessingMode,
  RagCitation,
  ReportResult,
  Textbook,
} from '@/lib/types';
import { cn } from '@/lib/utils';

type ToastState = {
  tone: 'success' | 'error' | 'info';
  message: string;
} | null;

const modeMeta: Record<
  ProcessingMode,
  { label: string; description: string; accent: string }
> = {
  demo: {
    label: 'Demo Mode',
    description:
      'Fast feedback loop for showcasing the pipeline with lighter processing.',
    accent: 'from-cyan-500 to-sky-600',
  },
  quality: {
    label: 'Quality Mode',
    description:
      'Stronger validation, deeper parsing, and richer graph construction.',
    accent: 'from-amber-500 to-orange-600',
  },
};

function SectionCard({
  icon,
  title,
  description,
  children,
  className,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        'rounded-[2rem] border border-white/70 bg-white/75 p-5 shadow-[0_18px_60px_-32px_rgba(15,23,42,0.35)] backdrop-blur',
        className,
      )}
    >
      <div className="mb-4 flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-lg shadow-slate-950/20">
          {icon}
        </div>
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-slate-950">
            {title}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="text-[11px] font-medium tracking-[0.25em] text-slate-500 uppercase">
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function NodeBadge({ node }: { node: GraphNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
        <span className="font-medium text-slate-950">{node.name}</span>
        <span className="rounded-full bg-slate-950 px-2 py-0.5 text-xs text-white">
          {node.category}
        </span>
      </div>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">
        {node.definition || '暂无定义'}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
        <span>页码 {node.page ?? '—'}</span>
        <span>频次 {node.frequency}</span>
        <span>{node.is_integrated ? '已整合' : '待整合'}</span>
      </div>
    </div>
  );
}

function formatSummary(summary: PipelineStatus['summary'] | undefined) {
  if (!summary || Object.keys(summary).length === 0) {
    return '流水线摘要会在这里显示。';
  }

  return JSON.stringify(summary, null, 2);
}

export default function Workbench() {
  const [mode, setMode] = useState<ProcessingMode>('demo');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadedTextbooks, setUploadedTextbooks] = useState<Textbook[]>([]);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({
    nodes: [],
    edges: [],
  });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [ragQuestion, setRagQuestion] =
    useState('这份教材中的核心概念之间是什么关系？');
  const [ragAnswer, setRagAnswer] = useState('');
  const [ragCitations, setRagCitations] = useState<RagCitation[]>([]);
  const [ragBusy, setRagBusy] = useState(false);
  const [teacherMessage, setTeacherMessage] = useState(
    '请检查这个节点是否适合保留在当前知识图谱中，并给出建议。',
  );
  const [teacherReply, setTeacherReply] = useState('');
  const [teacherBusy, setTeacherBusy] = useState(false);
  const [report, setReport] = useState('');
  const [reportBusy, setReportBusy] = useState(false);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);

  const refreshStatus = useCallback(async () => {
    try {
      const nextStatus = await getPipelineStatus();
      setStatus(nextStatus);
    } catch (error) {
      setToast({
        tone: 'error',
        message:
          error instanceof Error ? error.message : 'Failed to load status',
      });
    }
  }, []);

  const refreshGraph = useCallback(async () => {
    try {
      const graph = await getGraph();
      setGraphData(graph);
      setSelectedNode((currentNode) => currentNode ?? graph.nodes[0] ?? null);
    } catch (error) {
      setToast({
        tone: 'error',
        message:
          error instanceof Error ? error.message : 'Failed to load graph',
      });
    }
  }, []);

  const refreshReport = useCallback(async () => {
    try {
      const payload: ReportResult = await getReport();
      setReport(payload.report);
    } catch {
      setReport(
        '尚未生成报告。上传教材并运行流水线后，这里会显示摘要与诊断结果。',
      );
    }
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void refreshStatus();
      void refreshGraph();
      void refreshReport();
    }, 0);

    return () => window.clearTimeout(timeout);
  }, [refreshGraph, refreshReport, refreshStatus]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  async function handleUpload(files: File[]) {
    if (files.length === 0) return;

    setUploadBusy(true);
    try {
      const response = await uploadTextbooks(files, mode);
      setUploadedTextbooks(response.textbooks);
      setToast({
        tone: 'success',
        message: `已上传 ${response.textbooks.length} 本教材`,
      });
      await refreshStatus();
      await refreshGraph();
    } catch (error) {
      setToast({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Upload failed',
      });
    } finally {
      setUploadBusy(false);
    }
  }

  async function handleRunPipeline() {
    if (uploadedTextbooks.length === 0) {
      setToast({ tone: 'info', message: '请先上传教材，再运行流水线。' });
      return;
    }

    setPipelineBusy(true);
    try {
      const response = await runPipeline(
        mode,
        uploadedTextbooks.map((item) => item.id),
      );
      setToast({
        tone: 'success',
        message: `流水线已启动：${response.run_id}`,
      });
      await refreshStatus();
      await refreshGraph();
      await refreshReport();
    } catch (error) {
      setToast({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Pipeline failed',
      });
    } finally {
      setPipelineBusy(false);
    }
  }

  async function handleRagQuery() {
    if (!ragQuestion.trim()) {
      setToast({ tone: 'info', message: '请输入一个问题。' });
      return;
    }

    setRagBusy(true);
    try {
      const response = await queryRag(
        ragQuestion.trim(),
        selectedNode?.node_id,
      );
      setRagAnswer(response.answer);
      setRagCitations(response.citations);
      setToast({ tone: 'success', message: 'RAG 问答已完成。' });
    } catch (error) {
      setToast({
        tone: 'error',
        message: error instanceof Error ? error.message : 'RAG query failed',
      });
    } finally {
      setRagBusy(false);
    }
  }

  async function handleTeacherReply() {
    if (!teacherMessage.trim()) {
      setToast({ tone: 'info', message: '请输入反馈内容。' });
      return;
    }

    setTeacherBusy(true);
    try {
      const response = await sendTeacherFeedback(teacherMessage.trim());
      setTeacherReply(`${response.decision}\n${response.message}`);
      setToast({
        tone: 'success',
        message: response.updated ? '教师反馈已写入。' : '教师反馈已返回。',
      });
    } catch (error) {
      setToast({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Teacher chat failed',
      });
    } finally {
      setTeacherBusy(false);
    }
  }

  const activeTextbookCount =
    uploadedTextbooks.length || status?.textbook_ids.length || 0;
  const progress = status?.progress ?? 0;
  const modeInfo = modeMeta[mode];

  const metrics = useMemo(
    () => [
      { label: '上传教材', value: `${activeTextbookCount}` },
      { label: '节点', value: `${graphData.nodes.length}` },
      { label: '边', value: `${graphData.edges.length}` },
      { label: '进度', value: `${progress}%` },
    ],
    [
      activeTextbookCount,
      graphData.edges.length,
      graphData.nodes.length,
      progress,
    ],
  );

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.14),_transparent_30%),radial-gradient(circle_at_top_right,_rgba(251,191,36,0.16),_transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] text-slate-950">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[linear-gradient(135deg,rgba(15,23,42,0.08),transparent_60%)]" />
      <main className="relative mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="rounded-[2rem] border border-white/70 bg-slate-950 px-6 py-6 text-white shadow-[0_24px_80px_-40px_rgba(15,23,42,0.8)]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/8 px-3 py-1 text-xs font-medium tracking-[0.28em] text-cyan-100 uppercase">
                <Sparkles className="size-3.5" />
                Knowledge Integration Workbench
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                一体化教材处理、知识图谱、RAG 和教师审阅工作台
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                上传教材后，先看状态，再跑流水线，接着在图谱中点选节点、追问知识、给教师反馈并查看报告。
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[360px] lg:grid-cols-2">
              {metrics.map((metric) => (
                <div
                  key={metric.label}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3"
                >
                  <div className="text-[11px] tracking-[0.24em] text-slate-400 uppercase">
                    {metric.label}
                  </div>
                  <div className="mt-1 text-xl font-semibold text-white">
                    {metric.value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <SectionCard
              icon={<ShieldCheck className="size-5" />}
              title="Processing Mode"
              description="切换 demo 或 quality，控制整套流水线的输出节奏和深度。"
            >
              <div className="grid gap-4 md:grid-cols-[1.2fr_1fr]">
                <div className="space-y-3">
                  <div className="flex rounded-2xl bg-slate-100 p-1">
                    {(['demo', 'quality'] as ProcessingMode[]).map((value) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setMode(value)}
                        className={cn(
                          'flex-1 rounded-xl px-4 py-3 text-sm font-semibold transition',
                          mode === value
                            ? 'bg-slate-950 text-white shadow-lg'
                            : 'text-slate-600 hover:text-slate-950',
                        )}
                      >
                        {modeMeta[value].label}
                      </button>
                    ))}
                  </div>
                  <div
                    className={cn(
                      'rounded-3xl p-4 text-white shadow-lg',
                      `bg-gradient-to-br ${modeInfo.accent}`,
                    )}
                  >
                    <div className="text-sm font-medium tracking-[0.25em] text-white/80 uppercase">
                      {modeInfo.label}
                    </div>
                    <p className="mt-2 max-w-xl text-sm leading-6 text-white/90">
                      {modeInfo.description}
                    </p>
                  </div>
                </div>
                <div className="rounded-3xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-950">
                        上传教材
                      </div>
                      <div className="text-xs text-slate-500">
                        支持 PDF / MD / TXT
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      {uploadBusy ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Upload className="size-4" />
                      )}
                      {uploadBusy ? '上传中' : '就绪'}
                    </div>
                  </div>
                  <label className="mt-4 flex cursor-pointer flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center transition hover:border-slate-400 hover:bg-slate-100">
                    <input
                      type="file"
                      accept=".pdf,.md,.txt"
                      multiple
                      className="hidden"
                      onChange={(event) => {
                        const files = Array.from(event.target.files ?? []);
                        setSelectedFiles(files);
                        void handleUpload(files);
                      }}
                    />
                    <Upload className="size-6 text-slate-400" />
                    <div>
                      <div className="text-sm font-medium text-slate-950">
                        选择教材文件
                      </div>
                      <div className="text-xs text-slate-500">
                        选择后自动上传，也可再手动触发
                      </div>
                    </div>
                  </label>
                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void handleUpload(selectedFiles)}
                      disabled={selectedFiles.length === 0 || uploadBusy}
                      className="rounded-full bg-slate-950 px-4 text-white hover:bg-slate-800"
                    >
                      <FileText className="size-4" />
                      Upload Files
                    </Button>
                    <span className="text-xs text-slate-500">
                      {selectedFiles.length > 0
                        ? `${selectedFiles.length} files selected`
                        : 'No files selected yet'}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <StatPill
                  label="上传结果"
                  value={`${uploadedTextbooks.length} 本教材`}
                />
                <StatPill label="处理状态" value={status?.status ?? '未启动'} />
                <StatPill
                  label="当前阶段"
                  value={status?.current_stage ?? '待命'}
                />
              </div>
            </SectionCard>

            <SectionCard
              icon={<Rocket className="size-5" />}
              title="Pipeline Control"
              description="启动流水线并查看实时进度、错误和摘要信息。"
            >
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  onClick={() => void handleRunPipeline()}
                  disabled={pipelineBusy || uploadedTextbooks.length === 0}
                  className="rounded-full bg-amber-500 px-5 text-slate-950 hover:bg-amber-400"
                >
                  {pipelineBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <ArrowRight className="size-4" />
                  )}
                  Run Pipeline
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void refreshStatus()}
                  className="rounded-full border-slate-300 bg-white px-4 text-slate-700 hover:bg-slate-100"
                >
                  Refresh Status
                </Button>
              </div>
              <div className="mt-5 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between text-sm text-slate-500">
                    <span>进度</span>
                    <span className="font-semibold text-slate-950">
                      {progress}%
                    </span>
                  </div>
                  <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-sky-500 to-indigo-600 transition-all"
                      style={{ width: `${Math.max(4, progress)}%` }}
                    />
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-slate-600">
                    <div>
                      <span className="font-medium text-slate-950">
                        Run ID:
                      </span>{' '}
                      {status?.id ?? '—'}
                    </div>
                    <div>
                      <span className="font-medium text-slate-950">Mode:</span>{' '}
                      {status?.mode ?? mode}
                    </div>
                    <div>
                      <span className="font-medium text-slate-950">
                        Textbooks:
                      </span>{' '}
                      {(status?.textbook_ids ?? []).join(', ') || '—'}
                    </div>
                  </div>
                </div>
                <div className="rounded-3xl border border-slate-200 bg-white p-4">
                  <div className="text-sm font-medium text-slate-950">
                    Summary
                  </div>
                  <p className="mt-2 text-sm leading-7 whitespace-pre-wrap text-slate-600">
                    {formatSummary(status?.summary)}
                  </p>
                  {status?.errors?.length ? (
                    <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                      <div className="font-medium">Errors</div>
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {status.errors.map((error) => (
                          <li key={error}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            </SectionCard>

            <SectionCard
              icon={<BrainCircuit className="size-5" />}
              title="Knowledge Graph"
              description="点击节点查看定义、来源和整合状态。"
              className="min-h-[620px]"
            >
              <GraphView
                graph={graphData}
                selectedNodeId={selectedNode?.node_id}
                onSelectNode={(node) => setSelectedNode(node)}
              />
              <div className="mt-4 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="rounded-3xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-slate-950">
                        Selected Node
                      </div>
                      <div className="text-xs text-slate-500">图谱节点详情</div>
                    </div>
                    <CheckCircle2
                      className={cn(
                        'size-5',
                        selectedNode ? 'text-emerald-600' : 'text-slate-300',
                      )}
                    />
                  </div>
                  {selectedNode ? (
                    <div className="mt-4 space-y-3">
                      <div className="text-xl font-semibold text-slate-950">
                        {selectedNode.name}
                      </div>
                      <p className="text-sm leading-7 text-slate-600">
                        {selectedNode.definition || '暂无定义'}
                      </p>
                      <div className="grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                        <div>
                          <span className="font-medium text-slate-950">
                            节点 ID:
                          </span>{' '}
                          {selectedNode.node_id}
                        </div>
                        <div>
                          <span className="font-medium text-slate-950">
                            分类:
                          </span>{' '}
                          {selectedNode.category}
                        </div>
                        <div>
                          <span className="font-medium text-slate-950">
                            教材:
                          </span>{' '}
                          {selectedNode.textbook_id ?? '—'}
                        </div>
                        <div>
                          <span className="font-medium text-slate-950">
                            章节:
                          </span>{' '}
                          {selectedNode.chapter_id ?? '—'}
                        </div>
                        <div>
                          <span className="font-medium text-slate-950">
                            页码:
                          </span>{' '}
                          {selectedNode.page ?? '—'}
                        </div>
                        <div>
                          <span className="font-medium text-slate-950">
                            频次:
                          </span>{' '}
                          {selectedNode.frequency}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                        {selectedNode.source_node_ids.length ? (
                          selectedNode.source_node_ids.map((sourceId) => (
                            <span
                              key={sourceId}
                              className="rounded-full bg-slate-100 px-2.5 py-1"
                            >
                              {sourceId}
                            </span>
                          ))
                        ) : (
                          <span className="rounded-full bg-slate-100 px-2.5 py-1">
                            无来源节点
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <p className="mt-4 text-sm leading-7 text-slate-500">
                      选择一个节点后，这里会显示详细信息。
                    </p>
                  )}
                </div>
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm font-medium text-slate-950">
                    Nodes in view
                  </div>
                  <div className="mt-3 grid max-h-[280px] gap-3 overflow-auto pr-1">
                    {graphData.nodes.slice(0, 6).map((node) => (
                      <NodeBadge key={node.node_id} node={node} />
                    ))}
                    {graphData.nodes.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
                        图谱为空，先上传教材并运行流水线。
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </SectionCard>
          </div>

          <div className="space-y-6">
            <SectionCard
              icon={<MessageSquareText className="size-5" />}
              title="RAG Query"
              description="对当前选中节点或整张图谱发起提问。"
            >
              <textarea
                value={ragQuestion}
                onChange={(event) => setRagQuestion(event.target.value)}
                rows={6}
                className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm leading-7 text-slate-950 transition outline-none placeholder:text-slate-400 focus:border-slate-950"
                placeholder="请输入你的问题"
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  onClick={() => void handleRagQuery()}
                  disabled={ragBusy}
                  className="rounded-full bg-slate-950 px-5 text-white hover:bg-slate-800"
                >
                  {ragBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <MessageSquareText className="size-4" />
                  )}
                  Ask RAG
                </Button>
                <span className="text-xs text-slate-500">
                  {selectedNode
                    ? `当前节点：${selectedNode.name}`
                    : '未选中节点'}
                </span>
              </div>
              <div className="mt-4 rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm font-medium text-slate-950">Answer</div>
                <p className="mt-2 text-sm leading-7 whitespace-pre-wrap text-slate-600">
                  {ragAnswer || '问答结果会显示在这里。'}
                </p>
              </div>
              <div className="mt-4">
                <div className="text-sm font-medium text-slate-950">
                  Citations
                </div>
                <div className="mt-3 space-y-2">
                  {ragCitations.length ? (
                    ragCitations.map((citation, index) => (
                      <div
                        key={`${citation.node_id ?? 'citation'}-${index}`}
                        className="rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-600"
                      >
                        <div className="font-medium text-slate-950">
                          {citation.title ??
                            citation.node_id ??
                            `Citation ${index + 1}`}
                        </div>
                        <p className="mt-1 line-clamp-3 leading-5">
                          {citation.content ?? '暂无引用内容'}
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-3 text-sm text-slate-500">
                      暂无引用。
                    </div>
                  )}
                </div>
              </div>
            </SectionCard>

            <SectionCard
              icon={<BookOpen className="size-5" />}
              title="Teacher Feedback"
              description="把人工审阅建议回写到教师环节。"
            >
              <textarea
                value={teacherMessage}
                onChange={(event) => setTeacherMessage(event.target.value)}
                rows={5}
                className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm leading-7 text-slate-950 transition outline-none placeholder:text-slate-400 focus:border-slate-950"
                placeholder="请输入教师反馈"
              />
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  onClick={() => void handleTeacherReply()}
                  disabled={teacherBusy}
                  className="rounded-full bg-emerald-600 px-5 text-white hover:bg-emerald-500"
                >
                  {teacherBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <BookOpen className="size-4" />
                  )}
                  Send Feedback
                </Button>
              </div>
              <div className="mt-4 rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm font-medium text-slate-950">Reply</div>
                <p className="mt-2 text-sm leading-7 whitespace-pre-wrap text-slate-600">
                  {teacherReply || '教师回复会显示在这里。'}
                </p>
              </div>
            </SectionCard>

            <SectionCard
              icon={<FileText className="size-5" />}
              title="Report Preview"
              description="展示最新的整体报告摘要。"
            >
              <div className="rounded-3xl border border-slate-200 bg-slate-950 p-5 text-slate-100">
                <div className="flex items-center gap-2 text-sm font-medium text-cyan-200">
                  <Sparkles className="size-4" />
                  Live report snapshot
                </div>
                <p className="mt-3 text-sm leading-7 whitespace-pre-wrap text-slate-200">
                  {report || '报告加载中...'}
                </p>
              </div>
              <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                <span>报告状态</span>
                <button
                  type="button"
                  onClick={() => {
                    setReportBusy(true);
                    void refreshReport().finally(() => setReportBusy(false));
                  }}
                  disabled={reportBusy}
                  className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:opacity-50"
                >
                  {reportBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : null}
                  Reload report
                </button>
              </div>
            </SectionCard>
          </div>
        </div>
      </main>

      {toast ? (
        <div className="fixed right-4 bottom-4 z-50 max-w-sm rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-2xl shadow-slate-950/15">
          <div
            className={cn(
              'text-xs font-semibold tracking-[0.24em] uppercase',
              toast.tone === 'error' && 'text-rose-600',
              toast.tone === 'success' && 'text-emerald-600',
              toast.tone === 'info' && 'text-cyan-600',
            )}
          >
            {toast.tone}
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-700">
            {toast.message}
          </p>
        </div>
      ) : null}
    </div>
  );
}
