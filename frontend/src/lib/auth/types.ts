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
  status: string;
  phone_number?: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
}

export interface ApiErrorBody {
  detail: string;
  error_code?: string;
  fields?: Record<string, string>;
  correlation_id?: string;
}

export type AuthStatus = "bootstrapping" | "authenticated" | "unauthenticated";
