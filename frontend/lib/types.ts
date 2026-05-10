export type ProcessingMode = 'demo' | 'quality';

export type ApiResponse<T> = {
  data: T;
  message?: string;
};

export type Textbook = {
  id: number;
  filename: string;
  original_name: string;
  file_format: string;
  file_size: number;
  title: string;
  parse_status: string;
  processing_mode: ProcessingMode | string;
};

export type UploadTextbooksData = {
  textbooks: Textbook[];
};

export type PipelineRunResult = {
  run_id: string;
  status: string;
  result: unknown;
};

export type PipelineStatus = {
  id: string;
  mode: ProcessingMode | string;
  status: string;
  current_stage: string;
  progress: number;
  errors: string[];
  summary: string;
  textbook_ids: number[];
};

export type GraphNode = {
  id: number;
  node_id: string;
  name: string;
  definition: string;
  category: string;
  page: number | null;
  frequency: number;
  is_integrated: boolean;
  source_node_ids: string[];
  textbook_id: number | null;
  chapter_id: number | null;
};

export type GraphEdge = {
  id: number;
  source: string;
  target: string;
  relation_type: string;
  description: string;
};

export type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type RagCitation = {
  textbook_id?: number;
  chapter_id?: number;
  node_id?: string;
  page?: number;
  title?: string;
  content?: string;
  score?: number;
  [key: string]: string | number | boolean | null | undefined;
};

export type SourceChunk = {
  id?: number | string;
  textbook_id?: number;
  chapter_id?: number;
  node_id?: string;
  content?: string;
  score?: number;
  [key: string]: string | number | boolean | null | undefined;
};

export type RagQueryResult = {
  answer: string;
  citations: RagCitation[];
  source_chunks: SourceChunk[];
};

export type TeacherChatResult = {
  updated: boolean;
  message: string;
  decision: string;
};

export type ReportResult = {
  report: string;
};
