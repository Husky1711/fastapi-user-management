import { apiClient } from "@/lib/apiClient";
import type {
  OrganizationCreatePayload,
  OrganizationMutationResponse,
  OrganizationUpdatePayload,
  SuperAdminOrganizationsStats,
  SuperAdminOrganizationRow,
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

export async function fetchOrganizations(): Promise<SuperAdminOrganizationRow[]> {
  const { data } = await apiClient.get<{ organizations: SuperAdminOrganizationRow[] }>(
    "/api/v1/organizations",
  );
  return data.organizations;
}

export async function fetchOrganizationById(
  organizationId: number,
): Promise<SuperAdminOrganizationRow> {
  const { data } = await apiClient.get<SuperAdminOrganizationRow>(
    `/api/v1/organizations/${organizationId}`,
  );
  return data;
}

export async function createOrganization(
  payload: OrganizationCreatePayload,
): Promise<OrganizationMutationResponse> {
  const { data } = await apiClient.post<OrganizationMutationResponse>(
    "/api/v1/organizations",
    payload,
  );
  return data;
}

export async function updateOrganization(
  organizationId: number,
  payload: OrganizationUpdatePayload,
): Promise<OrganizationMutationResponse> {
  const { data } = await apiClient.patch<OrganizationMutationResponse>(
    `/api/v1/organizations/${organizationId}`,
    payload,
  );
  return data;
}
