import { apiClient } from "@/lib/apiClient";
import type {
  AdminActivityStats,
  AdminCreateUserPayload,
  AdminCreateUserResponse,
  AdminDashboardOverview,
  AdminUserDetail,
  AdminUserRow,
  AdminUsersListOrg,
  AdminUsersStats,
} from "@/lib/admin/types";

export async function fetchAdminOverview(): Promise<AdminDashboardOverview> {
  const { data } = await apiClient.get<AdminDashboardOverview>(
    "/api/v1/dashboard/admin/overview",
  );
  return data;
}

export async function fetchAdminUsersStats(): Promise<AdminUsersStats> {
  const { data } = await apiClient.get<AdminUsersStats>(
    "/api/v1/dashboard/admin/users/stats",
  );
  return data;
}

export async function fetchAdminActivityStats(): Promise<AdminActivityStats> {
  const { data } = await apiClient.get<AdminActivityStats>(
    "/api/v1/dashboard/admin/activity/stats",
  );
  return data;
}

export async function fetchUserById(userId: number): Promise<AdminUserDetail> {
  const { data } = await apiClient.get<AdminUserDetail>(`/api/v1/users/${userId}`);
  return data;
}

export async function createUser(
  payload: AdminCreateUserPayload,
): Promise<AdminCreateUserResponse> {
  const { data } = await apiClient.post<AdminCreateUserResponse>(
    "/api/v1/admin/users/create",
    payload,
  );
  return data;
}

export async function fetchUsers(): Promise<AdminUserRow[]> {
  const { data } = await apiClient.get<unknown>("/api/v1/users");
  return flattenUsersResponse(data);
}

export function flattenUsersResponse(data: unknown): AdminUserRow[] {
  if (!data || typeof data !== "object") {
    return [];
  }

  const obj = data as Record<string, unknown>;

  if (Array.isArray(obj.users)) {
    return obj.users as AdminUserRow[];
  }

  if (obj.user && typeof obj.user === "object") {
    return [obj.user as AdminUserRow];
  }

  const rows: AdminUserRow[] = [];
  for (const value of Object.values(obj)) {
    if (
      value &&
      typeof value === "object" &&
      Array.isArray((value as AdminUsersListOrg).users)
    ) {
      rows.push(...(value as AdminUsersListOrg).users);
    }
  }
  return rows;
}
