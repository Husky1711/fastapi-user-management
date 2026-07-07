import { apiClient } from "@/lib/apiClient";
import type {
  PasswordChangeResponse,
  SessionInfo,
  UserProfileDetail,
  UserProfileUpdateResponse,
} from "@/lib/profile/types";

export interface SessionInfoDetail {
  id: number;
  device_info?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  expires_at: string;
  is_current: boolean;
}

export interface SessionsInfoResponse {
  user_id: number;
  total_sessions: number;
  sessions: SessionInfoDetail[];
  max_sessions: number;
}

export async function fetchProfileDetail(): Promise<UserProfileDetail> {
  const { data } = await apiClient.get<UserProfileDetail>("/api/v1/profile");
  return data;
}

export async function updateProfile(payload: {
  email?: string;
  phone_number?: string;
}): Promise<UserProfileUpdateResponse> {
  const { data } = await apiClient.put<UserProfileUpdateResponse>(
    "/api/v1/profile",
    payload,
  );
  return data;
}

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<PasswordChangeResponse> {
  const { data } = await apiClient.post<PasswordChangeResponse>(
    "/api/v1/password/change",
    payload,
  );
  return data;
}

export async function fetchSessions(): Promise<SessionInfo[]> {
  const { data } = await apiClient.get<SessionInfo[]>("/api/v1/sessions");
  return data;
}

export async function fetchSessionInfo(): Promise<SessionsInfoResponse> {
  const { data } = await apiClient.get<SessionsInfoResponse>("/api/v1/sessions/info");
  return data;
}

export async function revokeSession(sessionId: number): Promise<void> {
  await apiClient.delete(`/api/v1/sessions/${sessionId}`);
}

export async function revokeOtherSessions(): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(
    "/api/v1/sessions/revoke-others",
    {},
  );
  return data;
}

export async function logoutAllSessions(): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>("/api/v1/logout-all", {});
  return data;
}
