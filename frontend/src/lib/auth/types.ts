export type UserRole =
  | "user"
  | "admin"
  | "organization_admin"
  | "super_admin";

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  organization_id: number;
  organization_name?: string | null;
  status: string;
  phone_number?: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  session_info?: {
    strategy_used?: string;
    existing_sessions?: number;
    sessions_revoked?: number;
    total_sessions?: number;
    max_sessions?: number;
  };
}

export interface ApiErrorBody {
  detail: string;
  error_code?: string;
  fields?: Record<string, string>;
  correlation_id?: string;
}

export type AuthStatus = "bootstrapping" | "authenticated" | "unauthenticated";
