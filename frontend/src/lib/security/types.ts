export interface TwoFactorStatus {
  is_enabled: boolean;
  has_secret: boolean;
  has_backup_codes: boolean;
}

export interface Enable2FAResponse {
  success: boolean;
  message: string;
  qr_code: string;
  backup_codes: string[];
  username: string;
}

export interface TwoFactorActionResponse {
  success: boolean;
  message: string;
}

export interface PasswordResetRequestResponse {
  success: boolean;
  message: string;
  reset_token?: string | null;
  expires_in_minutes?: number;
}

export interface PasswordResetConfirmResponse {
  success: boolean;
  message: string;
}
