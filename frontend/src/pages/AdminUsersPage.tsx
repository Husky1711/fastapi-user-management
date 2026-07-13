import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { StaffShell } from "@/components/StaffShell";
import { UsersTable } from "@/components/UsersTable";
import { fetchUsers } from "@/lib/admin/api";
import { allowedCreateRoles } from "@/lib/admin/roles";
import { useAuth } from "@/lib/auth/AuthProvider";
import { createInvitation } from "@/lib/onboarding/api";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/AdminPage.module.css";

export function AdminUsersPage() {
  const { user } = useAuth();
  const inviteRoles = (user ? allowedCreateRoles(user.role) : []).filter(
    (role) => role !== "super_admin",
  );

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState(inviteRoles.includes("user") ? "user" : inviteRoles[0] ?? "user");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteMessage, setInviteMessage] = useState<string | null>(null);
  const [devInviteToken, setDevInviteToken] = useState<string | null>(null);

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: fetchUsers,
  });

  const inviteMutation = useMutation({
    mutationFn: () =>
      createInvitation({
        email: inviteEmail,
        role: inviteRole,
      }),
    onSuccess: (data) => {
      setInviteError(null);
      setInviteMessage(data.message);
      setDevInviteToken(data.invite_token ?? null);
      setInviteEmail("");
    },
    onError: (err) => {
      setInviteMessage(null);
      setDevInviteToken(null);
      setInviteError(getApiError(err).detail);
    },
  });

  function onInviteSubmit(event: FormEvent) {
    event.preventDefault();
    setInviteError(null);
    setInviteMessage(null);
    setDevInviteToken(null);
    inviteMutation.mutate();
  }

  return (
    <StaffShell>
      <section className={styles.section}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
          <div>
            <h2>All users</h2>
            <p className={styles.subtitle}>
              Data from <code>GET /api/v1/users</code>
            </p>
          </div>
          <Link to="/admin/users/new">Create user</Link>
        </div>

        {inviteRoles.length > 0 && (
          <form onSubmit={onInviteSubmit} style={{ margin: "1.25rem 0", maxWidth: "28rem" }}>
            <h3 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Invite by email</h3>
            <p className={styles.subtitle}>Sends an org-bound invitation (accept at `/accept-invite/:token`).</p>
            {inviteError && <p className={styles.error}>{inviteError}</p>}
            {inviteMessage && <p className={styles.subtitle}>{inviteMessage}</p>}
            {devInviteToken && (
              <p className={styles.subtitle}>
                Dev invite link:{" "}
                <Link to={`/accept-invite/${devInviteToken}`}>/accept-invite/{devInviteToken.slice(0, 8)}…</Link>
              </p>
            )}
            <label style={{ display: "block", marginTop: "0.75rem" }}>
              Email
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                required
                style={{ display: "block", width: "100%", marginTop: "0.25rem" }}
              />
            </label>
            <label style={{ display: "block", marginTop: "0.75rem" }}>
              Role
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: "0.25rem" }}
              >
                {inviteRoles.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={inviteMutation.isPending} style={{ marginTop: "0.75rem" }}>
              {inviteMutation.isPending ? "Sending…" : "Send invitation"}
            </button>
          </form>
        )}

        {usersQuery.isLoading && <p className={styles.loading}>Loading users…</p>}

        {usersQuery.error && (
          <p className={styles.error}>{getApiError(usersQuery.error).detail}</p>
        )}

        {usersQuery.data && (
          <>
            <p className={styles.subtitle} style={{ marginBottom: "1rem" }}>
              {usersQuery.data.length} user{usersQuery.data.length === 1 ? "" : "s"}
            </p>
            <UsersTable users={usersQuery.data} linkToDetail />
          </>
        )}
      </section>
    </StaffShell>
  );
}
