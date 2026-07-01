import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { env } from "@/lib/env";
import type { ApiErrorBody, TokenResponse } from "@/lib/auth/types";

type AccessTokenGetter = () => string | null;
type AccessTokenSetter = (token: string | null, expiresIn?: number) => void;
type LogoutHandler = () => void;

let getAccessToken: AccessTokenGetter = () => null;
let setAccessToken: AccessTokenSetter = () => undefined;
let onForcedLogout: LogoutHandler = () => undefined;

let refreshPromise: Promise<string | null> | null = null;
let proactiveRefreshTimer: ReturnType<typeof setTimeout> | null = null;

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

export function configureApiClient(options: {
  getAccessToken: AccessTokenGetter;
  setAccessToken: AccessTokenSetter;
  onForcedLogout: LogoutHandler;
}) {
  getAccessToken = options.getAccessToken;
  setAccessToken = options.setAccessToken;
  onForcedLogout = options.onForcedLogout;
}

function scheduleProactiveRefresh(expiresIn: number) {
  if (proactiveRefreshTimer) {
    clearTimeout(proactiveRefreshTimer);
  }
  const delayMs = Math.max((expiresIn - 60) * 1000, 10_000);
  proactiveRefreshTimer = setTimeout(() => {
    void refreshAccessToken();
  }, delayMs);
}

async function doRefresh(): Promise<string | null> {
  try {
    const { data } = await apiClient.post<TokenResponse>("/api/v1/refresh", {});
    setAccessToken(data.access_token, data.expires_in);
    scheduleProactiveRefresh(data.expires_in);
    return data.access_token;
  } catch {
    setAccessToken(null);
    onForcedLogout();
    return null;
  }
}

export function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config;
    if (!original || error.response?.status !== 401) {
      return Promise.reject(error);
    }

    if (original.url?.includes("/api/v1/refresh") || original.url?.includes("/api/v1/login")) {
      return Promise.reject(error);
    }

    if ((original as InternalAxiosRequestConfig & { _retry?: boolean })._retry) {
      onForcedLogout();
      return Promise.reject(error);
    }

    (original as InternalAxiosRequestConfig & { _retry?: boolean })._retry = true;
    const token = await refreshAccessToken();
    if (!token) {
      return Promise.reject(error);
    }

    original.headers.Authorization = `Bearer ${token}`;
    return apiClient(original);
  },
);

export function applyLoginTokens(data: TokenResponse) {
  setAccessToken(data.access_token, data.expires_in);
  scheduleProactiveRefresh(data.expires_in);
}

export function clearAuthTimers() {
  if (proactiveRefreshTimer) {
    clearTimeout(proactiveRefreshTimer);
    proactiveRefreshTimer = null;
  }
}

export function getApiError(error: unknown): ApiErrorBody {
  if (axios.isAxiosError<ApiErrorBody>(error) && error.response?.data) {
    return error.response.data;
  }
  return { detail: "Unexpected error" };
}
