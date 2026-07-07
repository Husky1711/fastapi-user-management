export interface SuperAdminOverview {
  total_organizations: number;
  total_users: number;
  active_users: number;
  total_admins: number;
  total_sessions: number;
  active_sessions: number;
  users_by_role: {
    super_admin: number;
    organization_admin: number;
    admin: number;
    user: number;
  };
  today_stats: {
    logins: number;
    new_users: number;
    total_audit_logs: number;
  };
}

export interface SuperAdminUsersStats {
  total_users: number;
  active_users: number;
  locked_users: number;
  users_by_role: {
    super_admin: number;
    organization_admin: number;
    admin: number;
    user: number;
  };
  users_by_status: {
    active: number;
    inactive: number;
    locked: number;
  };
  users_today: number;
  users_this_week: number;
  users_this_month: number;
  recent_users: Array<{
    id: number;
    username: string;
    email: string;
    role: string;
    status: string;
    organization_id?: number | null;
    created_at?: string | null;
  }>;
}

export interface SuperAdminOrganizationRow {
  id: number;
  name: string;
  status: string;
  total_users: number;
  active_users: number;
}

export interface SuperAdminOrganizationsStats {
  total_organizations: number;
  active_organizations: number;
  inactive_organizations: number;
  organizations_by_size: {
    small: number;
    medium: number;
    large: number;
  };
  organizations: SuperAdminOrganizationRow[];
}

export interface SuperAdminSessionsStats {
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
