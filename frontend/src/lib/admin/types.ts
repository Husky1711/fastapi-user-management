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
  manager_id?: number | null;
  manager_username?: string | null;
}

export interface AdminUsersListOrg {
  organization_id: number;
  users: AdminUserRow[];
}

export interface AdminActivityItem {
  user_id?: number | null;
  username?: string | null;
  action?: string | null;
  time?: string | null;
  status?: string | null;
}

export interface AdminActivityStats {
  total_activity_today: number;
  activity_by_type: Record<string, number>;
  recent_activity: AdminActivityItem[];
}

export interface AdminCreateUserPayload {
  username: string;
  email: string;
  role?: string;
  phone_number?: string;
  auto_generate_password?: boolean;
  send_welcome_email?: boolean;
  password?: string;
  organization_id?: number;
  manager_id?: number;
}

export interface AdminCreateUserResponse {
  success: boolean;
  message: string;
  user?: AdminUserRow & { organization_id?: number; created_at?: string };
  generated_password?: string | null;
  email_sent?: boolean;
}

export interface AdminUserDetail extends AdminUserRow {
  organization_id: number;
  organization_name?: string | null;
}

export interface AdminUpdateUserPayload {
  email?: string;
  phone_number?: string;
  role?: string;
  status?: string;
  manager_id?: number | null;
  organization_id?: number;
}

export interface AdminUpdateUserResponse {
  success: boolean;
  message: string;
  user?: AdminUserDetail & { created_at?: string; last_login?: string | null };
}
