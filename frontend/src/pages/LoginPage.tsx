import { type FormEvent, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { getApiError } from "@/lib/apiClient";
import type { SessionStrategy } from "@/lib/auth/api";
import { useAuth } from "@/lib/auth/AuthProvider";
import styles from "./LoginPage.module.css";

export function LoginPage() {
  const { status, login, loginWith2fa, loginWithSessionStrategy } = useAuth();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showSessionOptions, setShowSessionOptions] = useState(false);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);

  const reason = searchParams.get("reason");

  if (status === "bootstrapping") {
    return null;
  }

  if (status === "authenticated") {
    return <Navigate to="/" replace />;
  }

  async function handleLogin(sessionStrategy?: SessionStrategy) {
    setSubmitting(true);
    setError(null);
    setSessionMessage(null);
    try {
      if (sessionStrategy) {
        const info = await loginWithSessionStrategy(username, password, sessionStrategy);
        if (info?.sessions_revoked) {
          setSessionMessage(`Signed in. Revoked ${info.sessions_revoked} other session(s).`);
        }
      } else {
        const challenge = await login(username, password);
        if (challenge) {
          setChallengeToken(challenge.challenge_token);
        }
      }
    } catch (err) {
      const apiError = getApiError(err);
      const challenge = (err as { challenge?: { challenge_token: string } }).challenge;
      if (challenge?.challenge_token) {
        setChallengeToken(challenge.challenge_token);
        return;
      }
      setError(apiError.detail);
      if (apiError.error_code === "SESSION_EXISTS") {
        setShowSessionOptions(true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmit2fa(event: FormEvent) {
    event.preventDefault();
    if (!challengeToken) return;
    setSubmitting(true);
    setError(null);
    try {
      await loginWith2fa(challengeToken, totpCode);
    } catch (err) {
      setError(getApiError(err).detail);
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await handleLogin();
  }

  if (challengeToken) {
    return (
      <div className={styles.page} data-testid="login-2fa-page">
        <form className={styles.card} onSubmit={onSubmit2fa}>
          <h1>Two-factor authentication</h1>
          <p className={styles.subtitle}>Enter the 6-digit code from your authenticator app.</p>
          {error && <p className={styles.error}>{error}</p>}
          <label>
            Authentication code
            <input
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              autoComplete="one-time-code"
              inputMode="numeric"
              minLength={6}
              maxLength={8}
              required
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? "Verifying…" : "Verify and sign in"}
          </button>
          <button
            type="button"
            className={styles.linkBtn}
            onClick={() => {
              setChallengeToken(null);
              setTotpCode("");
              setError(null);
            }}
          >
            ← Back to password
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className={styles.page} data-testid="login-page">
      <form className={styles.card} onSubmit={onSubmit}>
        <h1>Sign in</h1>
        {reason === "session_expired" && (
          <p className={styles.banner}>Your session expired. Please sign in again.</p>
        )}
        {reason === "signup_success" && (
          <p className={styles.banner}>Account created. Sign in with your new credentials.</p>
        )}
        {error && <p className={styles.error}>{error}</p>}
        {sessionMessage && <p className={styles.banner}>{sessionMessage}</p>}
        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>

        <button
          type="button"
          className={styles.linkBtn}
          onClick={() => setShowSessionOptions((open) => !open)}
        >
          {showSessionOptions ? "Hide session options" : "Already signed in elsewhere?"}
        </button>

        {showSessionOptions && (
          <div className={styles.sessionPanel}>
            <p className={styles.subtitle}>
              Uses POST /api/v1/login-with-session-control
            </p>
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={submitting}
              onClick={() => void handleLogin("replace_all")}
            >
              Sign in and replace other sessions
            </button>
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={submitting}
              onClick={() => void handleLogin("allow_multiple")}
            >
              Sign in and keep other sessions
            </button>
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={submitting}
              onClick={() => void handleLogin("replace_same_device")}
            >
              Sign in (replace this device only)
            </button>
          </div>
        )}

        <Link to="/forgot-password">Forgot password?</Link>
        <Link to="/verify">Verify email</Link>
        <Link to="/signup">Create an account</Link>
      </form>
    </div>
  );
}
