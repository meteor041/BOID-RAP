import { request } from "./http";

export type ObjectTypesResponse = {
  items: Array<"company" | "stock" | "commodity">;
};

export type RetrievalProvidersResponse = {
  default_provider: string;
  items: Array<{
    name: string;
    enabled: boolean;
  }>;
};

export type SearchInsightsResponse = {
  total_searches: number;
  recent_searches: Array<{
    keyword: string;
    scope: string;
    resource_id?: string;
    created_at: string;
  }>;
  popular_keywords: Array<{
    keyword: string;
    count: number;
  }>;
  popular_scopes: Array<{
    scope: string;
    count: number;
  }>;
};

export function getObjectTypes() {
  return request<ObjectTypesResponse>("/api/meta/object-types");
}

export function getRetrievalProviders() {
  return request<RetrievalProvidersResponse>("/api/meta/retrieval-providers");
}

export function getSearchInsights(token: string, limit = 10) {
  return request<SearchInsightsResponse>(`/api/meta/search-insights?limit=${limit}`, { token });
}
