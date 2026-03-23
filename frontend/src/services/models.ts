import { request } from "./http";

export type ModelItem = {
  id: string;
  name: string;
  provider: string;
  recommended_for: string[];
  permissions: string[];
  enabled: boolean;
  parameters: Record<string, unknown>;
};

export function listModels(token: string, objectType?: string) {
  const query = objectType ? `?object_type=${encodeURIComponent(objectType)}` : "";
  return request<{ items: ModelItem[] }>(`/api/models${query}`, { token });
}
