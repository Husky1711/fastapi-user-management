import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { StaffShell } from "@/components/StaffShell";
import { createUser, fetchUsers } from "@/lib/admin/api";
import { allowedCreateRoles, isManagerRole } from "@/lib/admin/roles";
import { useAuth } from "@/lib/auth/AuthProvider";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/ProfilePage.module.css";

export function AdminCreateUserPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const roles = user ? allowedCreateRoles(user.role) : [];

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState(roles[roles.length - 1] ?? "user");
  const [phone, setPhone] = useState("");
  const [autoPassword, setAutoPassword] = useState(true);
  const [password, setPassword] = useState("");
  const [managerId, setManagerId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: fetchUsers,
    enabled: role === "user",
  });

  const managerOptions = useMemo(() => {
    if (!user) {
      return [];
    }
    if (user.role === "admin") {
      return [{ id: user.id, username: user.username, role: user.role }];
    }
    if (!usersQuery.data) {
      return [];
    }
    return usersQuery.data.filter((candidate) => isManagerRole(candidate.role));
  }, [user, usersQuery.data]);

  const mutation = useMutation({
    mutationFn: () =>
      createUser({
        username,
        email,
        role,
        phone_number: phone || undefined,
        auto_generate_password: autoPassword,
        send_welcome_email: false,
        password: autoPassword ? undefined : password,
        manager_id:
          role === "user" && managerId ? Number(managerId) : undefined,
      }),
    onSuccess: (data) => {
      setError(null);
      setGeneratedPassword(data.generated_password ?? null);
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "overview"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "users-stats"] });
      if (!data.generated_password) {
        navigate("/admin/users");
      }
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setGeneratedPassword(null);
    mutation.mutate();
  }

  if (roles.length === 0) {
    return (
      <StaffShell>
        <p className={styles.error}>You do not have permission to create users.</p>
      </StaffShell>
    );
  }

  return (
    <StaffShell>
      <section className={styles.panel}>
        <Link to="/admin/users" className={styles.backLink}>
          ← Back to users
        </Link>
        <h2 style={{ marginTop: "1rem" }}>Create user</h2>
        <p className={styles.subtitle}>POST /api/v1/admin/users/create</p>

        {generatedPassword && (
          <div className={styles.success} style={{ marginTop: "1rem" }}>
            User created. Generated password: <strong>{generatedPassword}</strong>
            <div style={{ marginTop: "0.75rem" }}>
              <Link to="/admin/users">View all users</Link>
            </div>
          </div>
        )}

        {!generatedPassword && (
          <form className={styles.form} onSubmit={onSubmit}>
            <label>
              Username
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Role
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {roles.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            {role === "user" && (
              <label>
                Reporting manager (optional)
                <select value={managerId} onChange={(e) => setManagerId(e.target.value)}>
                  <option value="">No manager</option>
                  {managerOptions.map((manager) => (
                    <option key={manager.id} value={manager.id}>
                      {manager.username} ({manager.role})
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Phone (optional)
              <input value={phone} onChange={(e) => setPhone(e.target.value)} />
            </label>
            <label style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
              <input
                type="checkbox"
                checked={autoPassword}
                onChange={(e) => setAutoPassword(e.target.checked)}
              />
              Auto-generate password
            </label>
            {!autoPassword && (
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </label>
            )}
            {error && <p className={styles.error}>{error}</p>}
            <button className={styles.primaryBtn} type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create user"}
            </button>
          </form>
        )}
      </section>
    </StaffShell>
  );
}
