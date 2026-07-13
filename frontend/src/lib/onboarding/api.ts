import { apiClient } from "@/lib/apiClient";

export interface InvitationValidateResponse {
  valid: boolean;
  email?: string;
  role?: string;
  organization_id?: number;
  organization_name?: string | null;
  expires_at?: string | null;
  error?: string;
}

export interface AcceptInvitationResponse {
  success: boolean;
  message: string;
  user_id?: number;
  username?: string;
  email?: string;
  role?: string;
  organization_id?: number;
}

export interface VerifyEmailResponse {
  success: boolean;
  message: string;
  user_id?: number;
  email?: string;
}

export interface ResendVerificationResponse {
  success: boolean;
  message: string;
  expires_in_hours?: number;
  verification_token?: string;
}

export interface CreateInvitationResponse {
  success: boolean;
  invitation_id: number;
  email: string;
  role: string;
  organization_id: number;
  expires_at: string;
  message: string;
  invite_token?: string;
}

export async function validateInvitation(token: string): Promise<InvitationValidateResponse> {
  const { data } = await apiClient.get<InvitationValidateResponse>(
    `/api/v1/invitations/validate/${encodeURIComponent(token)}`,
  );
  return data;
}

export async function acceptInvitation(
  token: string,
  username: string,
  password: string,
): Promise<AcceptInvitationResponse> {
  const { data } = await apiClient.post<AcceptInvitationResponse>("/api/v1/invitations/accept", {
    token,
    username,
    password,
  });
  return data;
}

export async function verifyEmail(token: string): Promise<VerifyEmailResponse> {
  const { data } = await apiClient.post<VerifyEmailResponse>("/api/v1/email/verify", { token });
  return data;
}

export async function resendEmailVerification(
  email: string,
): Promise<ResendVerificationResponse> {
  const { data } = await apiClient.post<ResendVerificationResponse>(
    "/api/v1/email/resend-verification",
    { email },
  );
  return data;
}

export async function createInvitation(payload: {
  email: string;
  role?: string;
  organization_id?: number;
  expires_in_days?: number;
}): Promise<CreateInvitationResponse> {
  const { data } = await apiClient.post<CreateInvitationResponse>(
    "/api/v1/invitations",
    payload,
  );
  return data;
}
