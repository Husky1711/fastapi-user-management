import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";

export interface OrganizationMembership {
  organization_id: number;
  organization_name: string | null;
  organization_slug: string | null;
  role: string;
  is_home: boolean;
}

export interface MyOrganizationsResponse {
  active_organization_id: number;
  organizations: OrganizationMembership[];
}

export async function fetchMyOrganizations(): Promise<MyOrganizationsResponse> {
  const { data } = await apiClient.get<MyOrganizationsResponse>("/api/v1/me/organizations");
  return data;
}

export function useMyOrganizations(enabled = true) {
  return useQuery({
    queryKey: ["me", "organizations"],
    queryFn: fetchMyOrganizations,
    enabled,
    staleTime: 60_000,
  });
}
