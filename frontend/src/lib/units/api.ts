import { AxiosError } from "axios";
import { apiClient } from "@/lib/apiClient";
import type { ApiErrorBody } from "@/lib/auth/types";

export interface OrgUnit {
  id: number;
  parent_id: number | null;
  unit_type: string;
  name: string;
  depth: number;
  path: string;
  member_count?: number;
}

export interface UnitPerson {
  id: number;
  username: string;
  email: string;
  role: string;
}

export interface UnitRoleGrant {
  user_id: number;
  username: string;
  role: string;
  unit_id: number;
}

export async function listUnits(): Promise<OrgUnit[]> {
  return (await apiClient.get<{ units: OrgUnit[] }>("/api/v1/units")).data.units;
}

export async function createUnit(body: { name: string; unit_type: string; parent_id: number | null }) {
  return (await apiClient.post<OrgUnit>("/api/v1/units", body)).data;
}

export async function renameUnit(unitId: number, name: string) {
  return (await apiClient.patch<OrgUnit>(`/api/v1/units/${unitId}`, { name })).data;
}

export async function deleteUnit(unitId: number) {
  await apiClient.delete(`/api/v1/units/${unitId}`);
}

export async function moveUnit(unitId: number, parentId: number | null) {
  return (await apiClient.post<OrgUnit>(`/api/v1/units/${unitId}/move`, { parent_id: parentId })).data;
}

export async function listUnitMembers(unitId: number, includeSubtree = false): Promise<UnitPerson[]> {
  const { data } = await apiClient.get<{ members: UnitPerson[] }>(
    `/api/v1/units/${unitId}/members`,
    { params: { include_subtree: includeSubtree } },
  );
  return data.members;
}

export async function addUnitMember(unitId: number, userId: number) {
  await apiClient.post(`/api/v1/units/${unitId}/members`, { user_id: userId });
}

export async function removeUnitMember(unitId: number, userId: number) {
  await apiClient.delete(`/api/v1/units/${unitId}/members/${userId}`);
}

export async function listUnitRoles(unitId: number): Promise<UnitRoleGrant[]> {
  return (await apiClient.get<{ roles: UnitRoleGrant[] }>(`/api/v1/units/${unitId}/roles`)).data.roles;
}

export async function grantUnitRole(unitId: number, userId: number, role: string) {
  await apiClient.post(`/api/v1/units/${unitId}/roles`, { user_id: userId, role });
}

export async function revokeUnitRole(unitId: number, userId: number, role: string) {
  await apiClient.delete(`/api/v1/units/${unitId}/roles/${userId}/${encodeURIComponent(role)}`);
}

/** Server message for a failed request (detail), else a generic fallback. */
export function errorMessage(err: unknown, fallback = "Something went wrong"): string {
  const ax = err as AxiosError<ApiErrorBody>;
  return ax?.response?.data?.detail ?? fallback;
}
