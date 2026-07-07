import { apiClient } from "@/lib/apiClient";
import type {
  ApiKeysResponse,
  AuditLogsResponse,
  AuditStatisticsResponse,
  CleanupSessionsResponse,
  GroupMembersResponse,
  GroupsResponse,
  PasswordPolicyStatsResponse,
  PermissionStatisticsResponse,
  PermissionsResponse,
  SessionStatisticsResponse,
} from "@/lib/compliance/types";

export async function fetchAuditLogs(params?: {
  limit?: number;
  offset?: number;
}): Promise<AuditLogsResponse> {
  const { data } = await apiClient.get<AuditLogsResponse>("/api/v1/audit/logs", {
    params,
  });
  return data;
}

export async function fetchAuditStatistics(): Promise<AuditStatisticsResponse> {
  const { data } = await apiClient.get<AuditStatisticsResponse>("/api/v1/audit/statistics");
  return data;
}

export async function fetchSessionStatistics(): Promise<SessionStatisticsResponse> {
  const { data } = await apiClient.get<SessionStatisticsResponse>(
    "/api/v1/sessions/statistics",
  );
  return data;
}

export async function cleanupExpiredSessions(): Promise<CleanupSessionsResponse> {
  const { data } = await apiClient.post<CleanupSessionsResponse>(
    "/api/v1/sessions/cleanup",
    {},
  );
  return data;
}

export async function fetchPermissions(userId?: number): Promise<PermissionsResponse> {
  const { data } = await apiClient.get<PermissionsResponse>("/api/v1/permissions", {
    params: userId ? { user_id: userId } : undefined,
  });
  return data;
}

export async function fetchStandardPermissions(): Promise<Record<string, string>> {
  const { data } = await apiClient.get<Record<string, string>>(
    "/api/v1/permissions/standard",
  );
  return data;
}

export async function fetchPermissionStatistics(): Promise<PermissionStatisticsResponse> {
  const { data } = await apiClient.get<PermissionStatisticsResponse>(
    "/api/v1/permissions/statistics",
  );
  return data;
}

export async function fetchGroups(): Promise<GroupsResponse> {
  const { data } = await apiClient.get<GroupsResponse>("/api/v1/groups");
  return data;
}

export async function fetchGroupMembers(groupId: number): Promise<GroupMembersResponse> {
  const { data } = await apiClient.get<GroupMembersResponse>(
    `/api/v1/groups/${groupId}/members`,
  );
  return data;
}

export async function fetchGroupStatistics(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get<Record<string, unknown>>(
    "/api/v1/groups/statistics",
  );
  return data;
}

export async function fetchApiKeys(userId?: number): Promise<ApiKeysResponse> {
  const { data } = await apiClient.get<ApiKeysResponse>("/api/v1/api-keys", {
    params: userId ? { user_id: userId } : undefined,
  });
  return data;
}

export async function fetchApiKeyStandardPermissions(): Promise<Record<string, string>> {
  const { data } = await apiClient.get<Record<string, string>>(
    "/api/v1/api-keys/standard-permissions",
  );
  return data;
}

export async function fetchApiKeyStatistics(): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get<Record<string, unknown>>(
    "/api/v1/api-keys/statistics",
  );
  return data;
}

export async function fetchPasswordPolicyStats(
  userId?: number,
): Promise<PasswordPolicyStatsResponse> {
  const { data } = await apiClient.get<PasswordPolicyStatsResponse>(
    "/api/v1/password/policy-stats",
    { params: userId ? { user_id: userId } : undefined },
  );
  return data;
}
