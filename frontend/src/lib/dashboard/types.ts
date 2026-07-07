export interface ProfileInfo {
  username: string;
  email: string;
  role: string;
  status: string;
  organization_id?: number | null;
  phone_number?: string | null;
  is_2fa_enabled?: boolean | null;
  failed_login_attempts?: number | null;
}

export interface UserDashboardOverview {
  profile: ProfileInfo;
  active_sessions: number;
  last_login?: string | null;
  account_created?: string | null;
}

export interface ActivityItem {
  action: string;
  time?: string | null;
  ip_address?: string | null;
  status?: string | null;
  resource_type?: string | null;
}

export interface UserActivityResponse {
  recent_activity: ActivityItem[];
  total_logins_today: number;
  total_logins_this_week: number;
  total_logins_this_month: number;
}

export interface DashboardSessionInfo {
  id: number;
  device: string;
  location: string;
  last_active?: string | null;
  ip_address?: string | null;
  expires_at?: string | null;
}

export interface UserSessionsResponse {
  active_sessions: DashboardSessionInfo[];
  total_sessions: number;
  can_revoke: boolean;
}
