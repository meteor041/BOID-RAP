import { request } from "./http";

export type ReportListItem = {
  id: string;
  session_id: string;
  title: string;
  summary: string;
  highlighted_title?: string;
  highlighted_summary?: string;
  preview?: string;
  matched_section_count?: number;
  has_keyword_match?: boolean;
  created_at: string;
};

export type ReportCitation = {
  title: string;
  source: string;
  url: string;
  highlighted_title?: string;
};

export type ReportSegment = {
  text: string;
  highlighted_text?: string;
  citation_indexes: number[];
  evidence_items: ReportCitation[];
};

export type ReportSection = {
  heading: string;
  content: string;
  highlighted_content?: string;
  citation_indexes: number[];
  evidence_items: ReportCitation[];
  content_segments: ReportSegment[];
  structured_data?: Record<string, unknown>;
};

export type ReportDetail = {
  id: string;
  session_id: string;
  title: string;
  summary: string;
  highlighted_summary?: string;
  conclusion?: string;
  highlighted_conclusion?: string;
  body: ReportSection[];
  citations: ReportCitation[];
  matched_section_count?: number;
  created_at: string;
};

export type ReportProfile = {
  report_id: string;
  session_id: string;
  object_name: string;
  object_type: "company" | "stock" | "commodity";
  section_heading: string;
  profile: Record<string, unknown>;
};

export type FollowUpResponse = {
  question: string;
  answer: string;
  highlighted_answer?: string;
  keyword?: string;
  paragraph_index?: number;
  section?: ReportSection;
  citations: ReportCitation[];
  created_at: string;
};

export type ReportListResponse = {
  items: ReportListItem[];
  search_meta?: {
    keyword?: string;
    matched_item_count?: number;
    suggested_keywords?: string[];
  };
  pagination: {
    limit: number;
    offset: number;
    total: number;
  };
};

export function listReports(token: string, keyword?: string) {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return request<ReportListResponse>(`/api/reports${query}`, { token });
}

export function getReport(token: string, reportId: string, keyword?: string) {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return request<{ report: ReportDetail; session: { id: string } }>(`/api/reports/${reportId}${query}`, { token }).then(
    (payload) => payload.report,
  );
}

export function getReportProfile(token: string, reportId: string) {
  return request<ReportProfile>(`/api/reports/${reportId}/profile`, { token });
}

export function followUpReport(
  token: string,
  reportId: string,
  payload: { question: string; keyword?: string; paragraph_index?: number },
) {
  return request<FollowUpResponse>(`/api/reports/${reportId}/follow-up`, {
    method: "POST",
    body: payload,
    token,
  });
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function downloadReportMarkdown(token: string, reportId: string, keyword?: string) {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  const response = await fetch(`${API_BASE_URL}/api/reports/${reportId}/markdown${query}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("markdown export failed");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `report-${reportId}.md`;
  anchor.click();
  window.URL.revokeObjectURL(url);
}
