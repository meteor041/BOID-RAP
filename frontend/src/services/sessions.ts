import { request } from "./http";

export type SessionMessage = {
  role: string;
  content: string;
  created_at?: string;
};

export type WorkflowEvent = {
  stage: string;
  detail: string;
  created_at?: string;
};

export type SessionItem = {
  id: string;
  object_name: string;
  object_type: "company" | "stock" | "commodity";
  model_id: string;
  status: "draft" | "running" | "completed";
  retrieval_provider?: string | null;
  time_range?: string;
  authority_level?: string;
  depth?: string;
  focus_areas?: string[];
  query?: string;
  messages?: SessionMessage[];
  workflow?: WorkflowEvent[];
  report_id?: string | null;
  created_at: string;
  updated_at?: string;
};

export type SessionListResponse = {
  items: SessionItem[];
  pagination: {
    limit: number;
    offset: number;
    total: number;
  };
};

export function listSessions(token: string) {
  return request<SessionListResponse>("/api/research/sessions", { token });
}

export function getSession(token: string, sessionId: string) {
  return request<SessionItem>(`/api/research/sessions/${sessionId}`, { token });
}

export function createSession(
  token: string,
  payload: {
    object_name: string;
    object_type: "company" | "stock" | "commodity";
    model_id: string;
    retrieval_provider?: string;
    focus_areas?: string[];
    time_range?: string;
    authority_level?: string;
    depth?: string;
  },
) {
  return request<SessionItem>("/api/research/sessions", {
    method: "POST",
    body: payload,
    token,
  });
}

export function addSessionMessage(
  token: string,
  sessionId: string,
  payload: { role: string; content: string },
) {
  return request<SessionItem>(`/api/research/sessions/${sessionId}/messages`, {
    method: "POST",
    body: payload,
    token,
  });
}

export function runSession(token: string, sessionId: string, forceRefresh = false) {
  return request<{ job: { id: string } }>(`/api/research/sessions/${sessionId}/run`, {
    method: "POST",
    body: { force_refresh: forceRefresh },
    token,
  });
}
