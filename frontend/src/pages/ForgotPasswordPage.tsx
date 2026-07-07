import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { getApiError } from "@/lib/apiClient";
import { confirmPasswordReset, requestPasswordReset } from "@/lib/security/api";
import styles from "@/pages/LoginPage.module.css";

export function ForgotPasswordPage() {
  const [searchParams] = useSearchParams();
  const tokenFromUrl = searchParams.get("token");

  const [email, setEmail] = useState("");
  const [token, setToken] = useState(tokenFromUrl ?? "");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [devToken, setDevToken] = useState<string | null>(null);

  const requestMutation = useMutation({
    mutationFn: () => requestPasswordReset(email),
    onSuccess: (data) => {
      setMessage(data.message);
      setError(null);
      if (data.reset_token) {
        setDevToken(data.reset_token);
        setToken(data.reset_token);
      }
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  const resetMutation = useMutation({
    mutationFn: () => confirmPasswordReset(token, newPassword),
    onSuccess: (data) => {
      setMessage(data.message);
      setError(null);
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  function onRequestSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setDevToken(null);
    requestMutation.mutate();
  }

  function onResetSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    resetMutation.mutate();
  }

  return (
    <div className={styles.page}>
      <div className={styles.card} style={{ width: "min(100%, 28rem)" }}>
        <h1>Reset password</h1>
        <Link to="/login">← Back to sign in</Link>

        {error && <p className={styles.error}>{error}</p>}
        {message && <p className={styles.banner}>{message}</p>}

        <form onSubmit={onRequestSubmit} style={{ marginTop: "1rem" }}>
          <h2 style={{ fontSize: "1rem" }}>Step 1 — Request reset link</h2>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={requestMutation.isPending}>
            {requestMutation.isPending ? "Sending…" : "Send reset request"}
          </button>
        </form>

        {devToken && (
          <p className={styles.banner} style={{ marginTop: "1rem" }}>
            Dev token (from API): <code>{devToken}</code>
          </p>
        )}

        <form onSubmit={onResetSubmit} style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1rem" }}>Step 2 — Set new password</h2>
          <label>
            Reset token
            <input value={token} onChange={(e) => setToken(e.target.value)} required />
          </label>
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <label>
            Confirm password
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <button type="submit" disabled={resetMutation.isPending}>
            {resetMutation.isPending ? "Resetting…" : "Reset password"}
          </button>
        </form>
      </div>
    </div>
  );
}
