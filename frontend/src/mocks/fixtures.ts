import type { UserProfile, UserRole } from "@/lib/auth/types";
import type {
  UserActivityResponse,
  UserDashboardOverview,
  UserSessionsResponse,
} from "@/lib/dashboard/types";

export function mockUserProfile(role: UserRole = "user"): UserProfile {
  return {
    id: 1,
    username: role === "user" ? "testuser" : "testadmin",
    email: role === "user" ? "user@test.com" : "admin@test.com",
    role,
    organization_id: 1,
    organization_name: "Default Organization",
    status: "active",
    phone_number: "1234567890",
  };
}

export const mockDashboardResponses = {
  overview(profile: UserProfile): UserDashboardOverview {
    return {
      profile: {
        username: profile.username,
        email: profile.email,
        role: profile.role,
        status: profile.status,
        organization_id: profile.organization_id,
        organization_name: profile.organization_name,
        phone_number: profile.phone_number,
      },
      active_sessions: 1,
      last_login: "2026-07-09T12:00:00Z",
      account_created: "2026-01-01T00:00:00Z",
    };
  },
  activity: {
    recent_activity: [],
    total_logins_today: 0,
    total_logins_this_week: 1,
    total_logins_this_month: 1,
  } satisfies UserActivityResponse,
  sessions: {
    active_sessions: [],
    total_sessions: 1,
    can_revoke: true,
  } satisfies UserSessionsResponse,
};
