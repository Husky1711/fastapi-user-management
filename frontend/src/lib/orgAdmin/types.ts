export interface OrgAdminOverview {
  organization_id: number;
  total_users: number;
  active_users: number;
  users_by_role: {
    admins: number;
    organization_admins: number;
    users: number;
  };
  active_sessions: number;
  today_stats: {
    logins: number;
    new_users: number;
  };
}

export interface OrgAdminUsersStats {
  total_users: number;
  users_by_role: {
    admins: number;
    organization_admins: number;
    users: number;
  };
  users_by_status: {
    active: number;
    inactive: number;
    locked: number;
  };
  recent_users: Array<{
    id: number;
    username: string;
    email: string;
    role: string;
    status: string;
    created_at?: string | null;
  }>;
}

export interface OrgAdminSessionsStats {
  total_sessions: number;
  active_sessions: number;
  revoked_sessions: number;
  recent_sessions: Array<{
    id: number;
    user_id: number;
    device_info: string;
    created_at?: string | null;
    is_revoked: boolean;
  }>;
}
