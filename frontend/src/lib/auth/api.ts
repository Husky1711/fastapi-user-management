import { apiClient } from "@/lib/apiClient";
import type { TokenResponse, UserProfile } from "@/lib/auth/types";

export type SessionStrategy =
  | "allow_multiple"
  | "replace_all"
  | "replace_same_device"
  | "deny_if_exists"
  | "limit_sessions";

export interface SignupPayload {
  username: string;
  email: string;
  password: string;
}

export interface SignupResponse extends UserProfile {
  created_at: string;
  last_login?: string | null;
}

export async function signupUser(payload: SignupPayload): Promise<SignupResponse> {
  const { data } = await apiClient.post<SignupResponse>("/api/v1/signup", payload);
  return data;
}

export async function loginWithSessionControl(
  username: string,
  password: string,
  sessionStrategy: SessionStrategy,
): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>(
    "/api/v1/login-with-session-control",
    { username, password },
    { params: { session_strategy: sessionStrategy } },
  );
  return data;
}
