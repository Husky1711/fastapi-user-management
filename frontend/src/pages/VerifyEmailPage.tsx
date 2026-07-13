import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { getApiError } from "@/lib/apiClient";
import { resendEmailVerification, verifyEmail } from "@/lib/onboarding/api";
import styles from "@/pages/LoginPage.module.css";

export function VerifyEmailPage() {
  const { token: tokenParam } = useParams<{ token?: string }>();
  const [searchParams] = useSearchParams();
  const tokenFromQuery = searchParams.get("token");
  const token = (tokenParam || tokenFromQuery || "").trim();

  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [autoTried, setAutoTried] = useState(false);

  const verifyMutation = useMutation({
    mutationFn: (value: string) => verifyEmail(value),
    onSuccess: (data) => {
      setMessage(data.message ?? "Email verified successfully.");
      setError(null);
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  const resendMutation = useMutation({
    mutationFn: () => resendEmailVerification(email),
    onSuccess: (data) => {
      setMessage(data.message);
      setError(null);
      if (data.verification_token) {
        setDevToken(data.verification_token);
      }
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  useEffect(() => {
    if (token && !autoTried) {
      setAutoTried(true);
      verifyMutation.mutate(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once when token present
  }, [token, autoTried]);

  function onResend(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setDevToken(null);
    resendMutation.mutate();
  }

  function onManualVerify(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (!token) {
      setError("Verification token is required");
      return;
    }
    verifyMutation.mutate(token);
  }

  return (
    <div className={styles.page}>
      <div className={styles.card} style={{ width: "min(100%, 28rem)" }}>
        <h1>Verify email</h1>
        <Link to="/login">← Back to sign in</Link>

        {error && <p className={styles.error}>{error}</p>}
        {message && <p className={styles.banner}>{message}</p>}

        {token ? (
          <form onSubmit={onManualVerify} style={{ marginTop: "1rem" }}>
            <p>
              Token: <code>{token.slice(0, 12)}…</code>
            </p>
            <button type="submit" disabled={verifyMutation.isPending}>
              {verifyMutation.isPending ? "Verifying…" : "Verify email"}
            </button>
          </form>
        ) : (
          <p style={{ marginTop: "1rem" }}>
            Open the link from your email, or paste a token below after requesting a new one.
          </p>
        )}

        <form onSubmit={onResend} style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1rem" }}>Resend verification</h2>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={resendMutation.isPending}>
            {resendMutation.isPending ? "Sending…" : "Resend verification email"}
          </button>
        </form>

        {devToken && (
          <p className={styles.banner} style={{ marginTop: "1rem" }}>
            Dev token: <code>{devToken}</code>
          </p>
        )}

        {message && !error && (
          <p style={{ marginTop: "1rem" }}>
            <Link to="/login">Continue to sign in</Link>
          </p>
        )}
      </div>
    </div>
  );
}
