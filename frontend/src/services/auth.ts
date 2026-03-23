import { request } from "./http";

export type LoginResponse = {
  token: string;
  expires_at: string;
  user: {
    id: string;
    username: string;
    role: "admin" | "user";
    enabled: boolean;
  };
};

export function login(payload: { username: string; password: string }) {
  return request<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: payload,
  });
}
