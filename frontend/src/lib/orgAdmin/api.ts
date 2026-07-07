import { apiClient } from "@/lib/apiClient";
import type {
  OrgAdminOverview,
  OrgAdminSessionsStats,
  OrgAdminUsersStats,
} from "@/lib/orgAdmin/types";

export async function fetchOrgAdminOverview(): Promise<OrgAdminOverview> {
  const { data } = await apiClient.get<OrgAdminOverview>(
    "/api/v1/dashboard/organization-admin/overview",
  );
  return data;
}

export async function fetchOrgAdminUsersStats(): Promise<OrgAdminUsersStats> {
  const { data } = await apiClient.get<OrgAdminUsersStats>(
    "/api/v1/dashboard/organization-admin/users/stats",
  );
  return data;
}

export async function fetchOrgAdminSessionsStats(): Promise<OrgAdminSessionsStats> {
  const { data } = await apiClient.get<OrgAdminSessionsStats>(
    "/api/v1/dashboard/organization-admin/sessions/stats",
  );
  return data;
}
