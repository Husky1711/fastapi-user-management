import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  apiClient,
  applyLoginTokens,
  clearAuthTimers,
  configureApiClient,
  refreshAccessToken,
} from "@/lib/apiClient";
import { broadcastLogout, subscribeLogout } from "@/lib/auth/authChannel";
import { loginWithSessionControl, type SessionStrategy } from "@/lib/auth/api";
import { getHomePathForRole } from "@/lib/auth/routing";
import type { AuthStatus, TokenResponse, UserProfile } from "@/lib/auth/types";

interface AuthContextValue {
  status: AuthStatus;
  user: UserProfile | null;
  login: (username: string, password: string) => Promise<void>;
  loginWithSessionStrategy: (
    username: string,
    password: string,
    sessionStrategy: SessionStrategy,
  ) => Promise<TokenResponse["session_info"]>;
  logout: () => Promise<void>;
  bootstrapError: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const accessTokenRef = useRef<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("bootstrapping");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [bootstrapError, setBootstrapError] = useState(false);

  const fetchProfile = useCallback(async () => {
    const { data } = await apiClient.get<UserProfile>("/api/v1/profile");
    setUser(data);
    return data;
  }, []);

  const hardLogout = useCallback(
    (reason?: string) => {
      clearAuthTimers();
      accessTokenRef.current = null;
      setUser(null);
      setStatus("unauthenticated");
      navigate(reason ? `/login?reason=${reason}` : "/login", { replace: true });
    },
    [navigate],
  );

  useEffect(() => {
    configureApiClient({
      getAccessToken: () => accessTokenRef.current,
      setAccessToken: (token) => {
        accessTokenRef.current = token;
      },
      onForcedLogout: () => hardLogout("session_expired"),
    });
  }, [hardLogout]);

  useEffect(() => {
    return subscribeLogout(() => hardLogout());
  }, [hardLogout]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const token = await refreshAccessToken();
        if (cancelled) return;

        if (!token) {
          setStatus("unauthenticated");
          return;
        }

        await fetchProfile();
        if (!cancelled) {
          setStatus("authenticated");
        }
      } catch {
        if (!cancelled) {
          setBootstrapError(true);
          setStatus("unauthenticated");
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [fetchProfile]);

  const login = useCallback(
    async (username: string, password: string) => {
      const { data } = await apiClient.post<TokenResponse>("/api/v1/login", {
        username,
        password,
      });
      applyLoginTokens(data);
      const profile = await fetchProfile();
      setStatus("authenticated");
      navigate(getHomePathForRole(profile.role), { replace: true });
    },
    [fetchProfile, navigate],
  );

  const loginWithSessionStrategy = useCallback(
    async (username: string, password: string, sessionStrategy: SessionStrategy) => {
      const data = await loginWithSessionControl(username, password, sessionStrategy);
      applyLoginTokens(data);
      const profile = await fetchProfile();
      setStatus("authenticated");
      navigate(getHomePathForRole(profile.role), { replace: true });
      return data.session_info;
    },
    [fetchProfile, navigate],
  );

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/api/v1/logout", {});
    } catch {
      // Still clear client state if API fails
    }
    broadcastLogout();
    hardLogout();
  }, [hardLogout]);

  const value = useMemo(
    () => ({
      status,
      user,
      login,
      loginWithSessionStrategy,
      logout,
      bootstrapError,
    }),
    [status, user, login, loginWithSessionStrategy, logout, bootstrapError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
