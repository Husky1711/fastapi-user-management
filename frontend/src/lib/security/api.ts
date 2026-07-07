import { apiClient } from "@/lib/apiClient";
import type {
  Enable2FAResponse,
  PasswordResetConfirmResponse,
  PasswordResetRequestResponse,
  PasswordResetValidateResponse,
  TwoFactorActionResponse,
  TwoFactorStatus,
} from "@/lib/security/types";

export async function fetch2faStatus(): Promise<TwoFactorStatus> {
  const { data } = await apiClient.get<TwoFactorStatus>("/api/v1/2fa/status");
  return data;
}

export async function enable2fa(): Promise<Enable2FAResponse> {
  const { data } = await apiClient.post<Enable2FAResponse>("/api/v1/2fa/enable", {});
  return data;
}

export async function verify2fa(totpCode: string): Promise<TwoFactorActionResponse> {
  const { data } = await apiClient.post<TwoFactorActionResponse>("/api/v1/2fa/verify", {
    totp_code: totpCode,
  });
  return data;
}

export async function disable2fa(totpCode: string): Promise<TwoFactorActionResponse> {
  const { data } = await apiClient.post<TwoFactorActionResponse>("/api/v1/2fa/disable", {
    totp_code: totpCode,
  });
  return data;
}

export async function fetchPasswordHistory(): Promise<unknown> {
  const { data } = await apiClient.get("/api/v1/password/history");
  return data;
}

export async function requestPasswordReset(
  email: string,
): Promise<PasswordResetRequestResponse> {
  const { data } = await apiClient.post<PasswordResetRequestResponse>(
    "/api/v1/password/reset-request",
    { email },
  );
  return data;
}

export async function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<PasswordResetConfirmResponse> {
  const { data } = await apiClient.post<PasswordResetConfirmResponse>(
    "/api/v1/password/reset",
    { token, new_password: newPassword },
  );
  return data;
}

export async function validatePasswordResetToken(
  token: string,
): Promise<PasswordResetValidateResponse> {
  const { data } = await apiClient.get<PasswordResetValidateResponse>(
    `/api/v1/password/reset/validate/${encodeURIComponent(token)}`,
  );
  return data;
}
