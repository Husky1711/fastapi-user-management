export interface AuditLogRow {
  id: number;
  user_id?: number | null;
  organization_id?: number | null;
  event_type?: string | null;
  event_category?: string | null;
  resource_type?: string | null;
  action?: string | null;
  status?: string | null;
  ip_address?: string | null;
  created_at?: string | null;
}

export interface AuditLogsResponse {
  success: boolean;
  logs?: AuditLogRow[];
  total_count?: number;
  limit?: number;
  offset?: number;
  error?: string;
}

export interface AuditStatisticsResponse {
  success: boolean;
  statistics?: {
    total_logs?: number;
    event_types?: Record<string, number>;
    status_counts?: Record<string, number>;
    category_counts?: Record<string, number>;
  };
}

export interface SessionStatisticsResponse {
  success: boolean;
  statistics?: {
    total_sessions?: number;
    active_sessions?: number;
    inactive_sessions?: number;
    device_types?: Record<string, number>;
    browsers?: Record<string, number>;
  };
}

export interface PermissionRow {
  id: number;
  permission_name: string;
  resource_type?: string | null;
  resource_id?: number | null;
  is_active?: boolean;
  granted_at?: string | null;
  expires_at?: string | null;
}

export interface PermissionsResponse {
  success: boolean;
  permissions?: PermissionRow[];
  total_count?: number;
}

export interface PermissionStatisticsResponse {
  success: boolean;
  statistics?: Record<string, unknown>;
}

export interface GroupRow {
  id: number;
  name: string;
  description?: string | null;
  organization_id?: number;
  is_active?: boolean;
  member_count?: number;
}

export interface GroupsResponse {
  success: boolean;
  groups?: GroupRow[];
  total_count?: number;
}

export interface GroupMemberRow {
  user_id: number;
  username?: string;
  email?: string;
  added_at?: string | null;
  is_active?: boolean;
}

export interface GroupMembersResponse {
  success: boolean;
  members?: GroupMemberRow[];
  group_id?: number;
  total_count?: number;
}

export interface ApiKeyRow {
  id: number;
  key_name: string;
  key_prefix?: string;
  user_id?: number;
  organization_id?: number;
  is_active?: boolean;
  last_used_at?: string | null;
  expires_at?: string | null;
}

export interface ApiKeysResponse {
  success: boolean;
  api_keys?: ApiKeyRow[];
  total_count?: number;
}

export interface CreateGroupResponse {
  success: boolean;
  group_id?: number;
  group?: GroupRow;
  message?: string;
  error?: string;
}

export interface CreateApiKeyResponse {
  success: boolean;
  api_key_id?: number;
  key_value?: string;
  key_prefix?: string;
  permissions?: string[];
  message?: string;
  error?: string;
}

export interface MutationResponse {
  success: boolean;
  message?: string;
  error?: string;
}

export interface PasswordPolicyStatsResponse {
  success: boolean;
  statistics?: Record<string, unknown>;
}

export interface CleanupSessionsResponse {
  success: boolean;
  message?: string;
  cleaned_count?: number;
}
