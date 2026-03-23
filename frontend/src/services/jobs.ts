import { request } from "./http";

export type JobItem = {
  id: string;
  session_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  current_stage: string;
  report_id?: string | null;
  error_message?: string | null;
  force_refresh?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type JobRetrievalDocument = {
  title: string;
  summary: string;
  source: string;
  url: string;
  category?: string;
  score?: number;
  highlighted_title?: string;
  highlighted_summary?: string;
  highlight_preview?: string;
};

export type JobRetrievalResponse = {
  job?: { id: string; session_id: string };
  provider: string;
  cache_hit: boolean;
  document_count: number;
  matched_document_count?: number;
  documents: JobRetrievalDocument[];
  search_meta?: {
    keyword?: string;
    matched_item_count?: number;
    suggested_keywords?: string[];
  };
};

export function getJob(token: string, jobId: string) {
  return request<JobItem>(`/api/research/jobs/${jobId}`, { token });
}

export function getJobRetrieval(token: string, jobId: string, keyword?: string) {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return request<JobRetrievalResponse>(`/api/research/jobs/${jobId}/retrieval${query}`, { token });
}

export function cancelJob(token: string, jobId: string) {
  return request<{ job: JobItem }>(`/api/research/jobs/${jobId}/cancel`, {
    method: "POST",
    body: {},
    token,
  });
}

export function retryJob(token: string, jobId: string) {
  return request<{ job: JobItem }>(`/api/research/jobs/${jobId}/retry`, {
    method: "POST",
    body: {},
    token,
  });
}
