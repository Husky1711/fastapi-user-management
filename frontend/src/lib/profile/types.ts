import type { UserProfile } from "@/lib/auth/types";

export interface UserProfileDetail extends UserProfile {
  created_at: string;
  last_login?: string | null;
}

export interface UserProfileUpdateResponse {
  success: boolean;
  message: string;
  user?: UserProfileDetail;
}

export interface PasswordChangeResponse {
  success: boolean;
  message: string;
}

export interface SessionInfo {
  id: number;
  device_info?: string | null;
  ip_address?: string | null;
  created_at: string;
  expires_at: string;
  is_active: boolean;
}

export type ProfileTab = "profile" | "security" | "sessions";
