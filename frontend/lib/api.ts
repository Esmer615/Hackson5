import type {
  ApiResponse,
  GraphData,
  PipelineRunResult,
  PipelineStatus,
  ProcessingMode,
  RagQueryResult,
  ReportResult,
  TeacherChatResult,
  UploadTextbooksData,
} from '@/lib/types';

// Instead of going through Vercel's proxy (which has a strict 4.5MB Serverless request body limit
// and a 10s maximum timeout), we bypass Vercel entirely and direct the browser to upload
// straight to the Railway backend. CORS has been enabled on the backend to allow this.
const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ||
  'https://hackson5-production.up.railway.app'
).replace(/\/+$/, '');

type JsonBody = Record<string, unknown>;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  });

  const payload = (await response.json().catch(() => null)) as
    | ApiResponse<T>
    | { detail?: string }
    | null;

  if (!response.ok) {
    const detail = payload && 'detail' in payload ? payload.detail : undefined;
    throw new Error(detail ?? `Request failed with status ${response.status}`);
  }

  if (!payload || !('data' in payload)) {
    throw new Error('API response did not include a data field');
  }

  return payload.data;
}

function postJson<T>(path: string, body: JsonBody): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function uploadTextbooks(
  files: File[],
  mode: ProcessingMode,
): Promise<UploadTextbooksData> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  formData.append('mode', mode);

  return request<UploadTextbooksData>('/api/textbooks/upload', {
    method: 'POST',
    body: formData,
  });
}

export function runPipeline(
  mode: ProcessingMode,
  textbookIds: number[],
): Promise<PipelineRunResult> {
  return postJson<PipelineRunResult>('/api/pipeline/run', {
    mode,
    textbook_ids: textbookIds,
  });
}

export function getPipelineStatus(): Promise<PipelineStatus> {
  return request<PipelineStatus>('/api/pipeline/status');
}

export function getGraph(): Promise<GraphData> {
  return request<GraphData>('/api/graph');
}

export function queryRag(
  question: string,
  nodeId?: string,
): Promise<RagQueryResult> {
  return postJson<RagQueryResult>('/api/rag/query', {
    question,
    node_id: nodeId,
  });
}

export function sendTeacherFeedback(
  message: string,
  decisionId?: string,
): Promise<TeacherChatResult> {
  return postJson<TeacherChatResult>('/api/teacher/chat', {
    message,
    decision_id: decisionId,
  });
}

export function getReport(): Promise<ReportResult> {
  return request<ReportResult>('/api/report');
}

export function clearSystem(): Promise<void> {
  return postJson<void>('/api/system/clear', {});
}
