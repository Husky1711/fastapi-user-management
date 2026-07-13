import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { getApiError } from "@/lib/apiClient";
import { acceptInvitation, validateInvitation } from "@/lib/onboarding/api";
import styles from "@/pages/LoginPage.module.css";

export function AcceptInvitePage() {
  const { token: tokenParam } = useParams<{ token: string }>();
  const token = tokenParam ?? "";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const validationQuery = useQuery({
    queryKey: ["invite-validate", token],
    queryFn: () => validateInvitation(token),
    enabled: token.length > 0,
    retry: false,
  });

  useEffect(() => {
    if (validationQuery.data?.email) {
      setError(null);
    }
  }, [validationQuery.data?.email]);

  const acceptMutation = useMutation({
    mutationFn: () => acceptInvitation(token, username, password),
    onSuccess: (data) => {
      setMessage(data.message ?? "Invitation accepted. You can sign in.");
      setError(null);
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (!validationQuery.data?.valid) {
      setError("Invitation is invalid or expired");
      return;
    }
    acceptMutation.mutate();
  }

  const invite = validationQuery.data;

  return (
    <div className={styles.page}>
      <div className={styles.card} style={{ width: "min(100%, 28rem)" }}>
        <h1>Accept invitation</h1>
        <Link to="/login">← Back to sign in</Link>

        {validationQuery.isLoading && <p>Checking invitation…</p>}
        {validationQuery.isError && (
          <p className={styles.error}>{getApiError(validationQuery.error).detail}</p>
        )}
        {error && <p className={styles.error}>{error}</p>}
        {message && <p className={styles.banner}>{message}</p>}

        {invite?.valid && !message && (
          <>
            <p style={{ marginTop: "1rem" }}>
              Join <strong>{invite.organization_name ?? `org #${invite.organization_id}`}</strong>{" "}
              as <strong>{invite.role}</strong>
              {invite.email ? (
                <>
                  {" "}
                  (<code>{invite.email}</code>)
                </>
              ) : null}
              .
            </p>
            <form onSubmit={onSubmit} style={{ marginTop: "1rem" }}>
              <label>
                Username
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={3}
                  autoComplete="username"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </label>
              <label>
                Confirm password
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </label>
              <button type="submit" disabled={acceptMutation.isPending}>
                {acceptMutation.isPending ? "Creating account…" : "Accept and create account"}
              </button>
            </form>
          </>
        )}

        {message && (
          <p style={{ marginTop: "1rem" }}>
            <Link to="/login">Continue to sign in</Link>
          </p>
        )}
      </div>
    </div>
  );
}
