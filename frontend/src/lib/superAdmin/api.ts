import { apiClient } from "@/lib/apiClient";
import type {
  SuperAdminOrganizationsStats,
  SuperAdminOverview,
  SuperAdminSessionsStats,
  SuperAdminUsersStats,
} from "@/lib/superAdmin/types";

export async function fetchSuperAdminOverview(): Promise<SuperAdminOverview> {
  const { data } = await apiClient.get<SuperAdminOverview>(
    "/api/v1/dashboard/super-admin/overview",
  );
  return data;
}

export async function fetchSuperAdminUsersStats(): Promise<SuperAdminUsersStats> {
  const { data } = await apiClient.get<SuperAdminUsersStats>(
    "/api/v1/dashboard/super-admin/users/stats",
  );
  return data;
}

export async function fetchSuperAdminOrganizationsStats(): Promise<SuperAdminOrganizationsStats> {
  const { data } = await apiClient.get<SuperAdminOrganizationsStats>(
    "/api/v1/dashboard/super-admin/organizations/stats",
  );
  return data;
}

export async function fetchSuperAdminSessionsStats(): Promise<SuperAdminSessionsStats> {
  const { data } = await apiClient.get<SuperAdminSessionsStats>(
    "/api/v1/dashboard/super-admin/sessions/stats",
  );
  return data;
}
