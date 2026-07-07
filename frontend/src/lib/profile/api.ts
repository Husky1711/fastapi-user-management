import { apiClient } from "@/lib/apiClient";
import type {
  PasswordChangeResponse,
  SessionInfo,
  UserProfileDetail,
  UserProfileUpdateResponse,
} from "@/lib/profile/types";

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

export async function revokeSession(sessionId: number): Promise<void> {
  await apiClient.delete(`/api/v1/sessions/${sessionId}`);
}
