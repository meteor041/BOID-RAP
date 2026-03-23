import { request } from "./http";

export type AdminUser = {
  id: string;
  username: string;
  role: "admin" | "user";
  enabled: boolean;
  deleted_at?: string | null;
  created_at?: string;
};

export type AdminModel = {
  id: string;
  name: string;
  provider: string;
  enabled: boolean;
  recommended_for: string[];
  permissions: string[];
  parameters: Record<string, unknown>;
};

export type AuditLog = {
  id: string;
  actor_user_id?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  detail?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
};

export function listAdminUsers(token: string) {
  return request<{ items: AdminUser[] }>("/api/admin/users", { token });
}

export function updateAdminUserStatus(token: string, userId: string, enabled: boolean) {
  return request<AdminUser>(`/api/admin/users/${userId}/status`, {
    method: "PATCH",
    body: { enabled },
    token,
  });
}

export function resetAdminUserPassword(token: string, userId: string, newPassword: string) {
  return request<{ status: string }>(`/api/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: { new_password: newPassword },
    token,
  });
}

export function softDeleteAdminUser(token: string, userId: string) {
  return request<{ status: string }>(`/api/admin/users/${userId}`, {
    method: "DELETE",
    token,
  });
}

export function listAdminModels(token: string) {
  return request<{ items: AdminModel[] }>("/api/admin/models", { token });
}

export function updateAdminModel(
  token: string,
  modelId: string,
  payload: Partial<{
    name: string;
    provider: string;
    enabled: boolean;
    recommended_for: string[];
    permissions: string[];
    parameters: Record<string, unknown>;
  }>,
) {
  return request<AdminModel>(`/api/admin/models/${modelId}`, {
    method: "PATCH",
    body: payload,
    token,
  });
}

export function listAuditLogs(token: string) {
  return request<{
    items: AuditLog[];
    pagination: { limit: number; offset: number; total: number };
  }>("/api/admin/audit-logs", { token });
}
