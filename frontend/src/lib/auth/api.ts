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
  organization_id: number;
}

export interface TwoFactorChallengeResponse {
  requires_2fa: true;
  challenge_token: string;
  message: string;
}

export function isTwoFactorChallenge(
  data: TokenResponse | TwoFactorChallengeResponse,
): data is TwoFactorChallengeResponse {
  return "requires_2fa" in data && data.requires_2fa === true;
}

export async function completeLoginWith2fa(
  challengeToken: string,
  totpCode: string,
): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/v1/login/2fa", {
    challenge_token: challengeToken,
    totp_code: totpCode,
  });
  return data;
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
