import { type FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { signupUser } from "@/lib/auth/api";
import { useAuth } from "@/lib/auth/AuthProvider";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/LoginPage.module.css";

function validatePassword(password: string): string | null {
  if (password.length < 8) return "Password must be at least 8 characters";
  if (!/[A-Z]/.test(password)) return "Password must include an uppercase letter";
  if (!/[a-z]/.test(password)) return "Password must include a lowercase letter";
  if (!/\d/.test(password)) return "Password must include a number";
  return null;
}

export function SignupPage() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [organizationId, setOrganizationId] = useState("1");

  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      signupUser({
        username,
        email,
        password,
        organization_id: Number(organizationId),
      }),
    onSuccess: () => {
      navigate("/login?reason=signup_success", { replace: true });
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  if (status === "bootstrapping") {
    return null;
  }

  if (status === "authenticated") {
    return <Navigate to="/" replace />;
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    mutation.mutate();
  }

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={onSubmit} style={{ width: "min(100%, 28rem)" }}>
        <h1>Create account</h1>
        <p className={styles.subtitle}>POST /api/v1/signup</p>
        <Link to="/login">← Back to sign in</Link>

        {error && <p className={styles.error}>{error}</p>}

        <label>
          Username
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            minLength={3}
            required
          />
        </label>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label>
          Organization ID
          <input
            type="number"
            min={1}
            value={organizationId}
            onChange={(e) => setOrganizationId(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
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
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Creating account…" : "Sign up"}
        </button>
      </form>
    </div>
  );
}
