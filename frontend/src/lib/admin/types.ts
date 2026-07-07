export interface TodayStats {
  logins: number;
  new_users: number;
  password_resets: number;
}

export interface AdminDashboardOverview {
  total_users: number;
  active_users: number;
  active_sessions: number;
  today_stats: TodayStats;
}

export interface UsersByStatus {
  active: number;
  inactive: number;
  locked: number;
}

export interface RecentUser {
  id: number;
  username: string;
  email: string;
  role: string;
  status: string;
  created_at?: string | null;
}

export interface AdminUsersStats {
  total_users: number;
  active_users: number;
  locked_users: number;
  users_by_status: UsersByStatus;
  recent_users: RecentUser[];
}

export interface AdminUserRow {
  id: number;
  username: string;
  email: string;
  role: string;
  status: string;
  phone_number?: string | null;
}

export interface AdminUsersListOrg {
  organization_id: number;
  users: AdminUserRow[];
}
