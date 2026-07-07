import { apiClient } from "@/lib/apiClient";
import type {
  UserActivityResponse,
  UserDashboardOverview,
  UserSessionsResponse,
} from "@/lib/dashboard/types";

export async function fetchUserOverview(): Promise<UserDashboardOverview> {
  const { data } = await apiClient.get<UserDashboardOverview>(
    "/api/v1/dashboard/user/overview",
  );
  return data;
}

export async function fetchUserActivity(): Promise<UserActivityResponse> {
  const { data } = await apiClient.get<UserActivityResponse>(
    "/api/v1/dashboard/user/activity",
  );
  return data;
}

export async function fetchUserDashboardSessions(): Promise<UserSessionsResponse> {
  const { data } = await apiClient.get<UserSessionsResponse>(
    "/api/v1/dashboard/user/sessions",
  );
  return data;
}
