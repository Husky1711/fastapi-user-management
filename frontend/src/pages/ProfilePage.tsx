import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth/AuthProvider";
import { getApiError } from "@/lib/apiClient";
import {
  changePassword,
  fetchProfileDetail,
  fetchSessions,
  revokeSession,
  updateProfile,
} from "@/lib/profile/api";
import { getHomePathForRole } from "@/lib/auth/routing";
import { TwoFactorPanel } from "@/components/TwoFactorPanel";
import type { ProfileTab, SessionInfo, UserProfileDetail } from "@/lib/profile/types";
import styles from "@/pages/ProfilePage.module.css";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function ProfileDetails({ profile }: { profile: UserProfileDetail }) {
  return (
    <div className={styles.fieldGrid}>
      <div className={styles.fieldRow}>
        <span className={styles.fieldLabel}>Username</span>
        <span className={styles.fieldValue}>{profile.username}</span>
      </div>
      <div className={styles.fieldRow}>
        <span className={styles.fieldLabel}>Role</span>
        <span className={styles.fieldValue}>
          <span className={styles.role}>{profile.role}</span>
        </span>
      </div>
      <div className={styles.fieldRow}>
        <span className={styles.fieldLabel}>Status</span>
        <span className={styles.fieldValue}>{profile.status}</span>
      </div>
      <div className={styles.fieldRow}>
        <span className={styles.fieldLabel}>Organization ID</span>
        <span className={styles.fieldValue}>{profile.organization_id}</span>
      </div>
      <div className={styles.fieldRow}>
        <span className={styles.fieldLabel}>Created</span>
        <span className={styles.fieldValue}>{formatDate(profile.created_at)}</span>
      </div>
      <div className={styles.fieldRow}>
        <span className={styles.fieldLabel}>Last login</span>
        <span className={styles.fieldValue}>{formatDate(profile.last_login)}</span>
      </div>
    </div>
  );
}

function ProfileEditForm({ profile }: { profile: UserProfileDetail }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState(profile.email);
  const [phone, setPhone] = useState(profile.phone_number ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      updateProfile({
        email: email !== profile.email ? email : undefined,
        phone_number: phone !== (profile.phone_number ?? "") ? phone : undefined,
      }),
    onSuccess: (data) => {
      setMessage(data.message);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (err) => {
      setError(getApiError(err).detail);
      setMessage(null);
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    mutation.mutate();
  }

  return (
    <form className={styles.form} onSubmit={onSubmit}>
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
        Phone number
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          inputMode="numeric"
          placeholder="Digits only"
        />
      </label>
      {error && <p className={styles.error}>{error}</p>}
      {message && <p className={styles.success}>{message}</p>}
      <button className={styles.primaryBtn} type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Saving…" : "Save changes"}
      </button>
    </form>
  );
}

function SecurityTab() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => changePassword({ current_password: currentPassword, new_password: newPassword }),
    onSuccess: (data) => {
      setMessage(data.message);
      setError(null);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    },
    onError: (err) => {
      setError(getApiError(err).detail);
      setMessage(null);
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match");
      return;
    }
    mutation.mutate();
  }

  return (
  <>
    <div className={styles.card}>
      <h2>Change password</h2>
      <p className={styles.subtitle}>Uses POST /api/v1/password/change</p>
      <form className={styles.form} onSubmit={onSubmit}>
        <label>
          Current password
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
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
          Confirm new password
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>
        {error && <p className={styles.error}>{error}</p>}
        {message && <p className={styles.success}>{message}</p>}
        <button className={styles.primaryBtn} type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Updating…" : "Update password"}
        </button>
      </form>
    </div>
    <TwoFactorPanel />
  </>
  );
}

function SessionsTable({
  sessions,
  onRevoke,
  revokingId,
}: {
  sessions: SessionInfo[];
  onRevoke: (id: number) => void;
  revokingId: number | null;
}) {
  if (sessions.length === 0) {
    return <p className={styles.loading}>No active sessions.</p>;
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Device</th>
            <th>IP</th>
            <th>Created</th>
            <th>Expires</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr key={session.id}>
              <td>{session.id}</td>
              <td>{session.device_info || "—"}</td>
              <td>{session.ip_address || "—"}</td>
              <td>{formatDate(session.created_at)}</td>
              <td>{formatDate(session.expires_at)}</td>
              <td>{session.is_active ? "active" : "revoked"}</td>
              <td>
                <button
                  type="button"
                  className={styles.dangerBtn}
                  disabled={!session.is_active || revokingId === session.id}
                  onClick={() => onRevoke(session.id)}
                >
                  {revokingId === session.id ? "Revoking…" : "Revoke"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SessionsTab() {
  const queryClient = useQueryClient();
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["profile", "sessions"],
    queryFn: fetchSessions,
  });

  async function handleRevoke(sessionId: number) {
    setError(null);
    setRevokingId(sessionId);
    try {
      await revokeSession(sessionId);
      await queryClient.invalidateQueries({ queryKey: ["profile", "sessions"] });
    } catch (err) {
      setError(getApiError(err).detail);
    } finally {
      setRevokingId(null);
    }
  }

  if (sessionsQuery.isLoading) {
    return <p className={styles.loading}>Loading sessions…</p>;
  }

  if (sessionsQuery.error) {
    return <p className={styles.error}>{getApiError(sessionsQuery.error).detail}</p>;
  }

  return (
    <div>
      <p className={styles.subtitle}>Data from GET /api/v1/sessions</p>
      {error && <p className={styles.error}>{error}</p>}
      <SessionsTable
        sessions={sessionsQuery.data ?? []}
        onRevoke={(id) => void handleRevoke(id)}
        revokingId={revokingId}
      />
    </div>
  );
}

export function ProfilePage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<ProfileTab>("profile");

  const profileQuery = useQuery({
    queryKey: ["profile"],
    queryFn: fetchProfileDetail,
  });

  const homeLink = user ? getHomePathForRole(user.role) : "/dashboard";

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <Link to={homeLink} className={styles.backLink}>
            ← Back
          </Link>
          <h1>Profile</h1>
          <p className={styles.subtitle}>{user?.username}</p>
        </div>
      </header>

      <nav className={styles.tabs}>
        <button
          type="button"
          className={tab === "profile" ? styles.tabActive : styles.tab}
          onClick={() => setTab("profile")}
        >
          Profile
        </button>
        <button
          type="button"
          className={tab === "security" ? styles.tabActive : styles.tab}
          onClick={() => setTab("security")}
        >
          Security
        </button>
        <button
          type="button"
          className={tab === "sessions" ? styles.tabActive : styles.tab}
          onClick={() => setTab("sessions")}
        >
          Sessions
        </button>
      </nav>

      <div className={styles.panel}>
        {tab === "profile" && (
          <>
            {profileQuery.isLoading && <p className={styles.loading}>Loading profile…</p>}
            {profileQuery.error && (
              <p className={styles.error}>{getApiError(profileQuery.error).detail}</p>
            )}
            {profileQuery.data && (
              <>
                <div className={styles.card}>
                  <h2>Account details</h2>
                  <ProfileDetails profile={profileQuery.data} />
                </div>
                <div className={styles.card} style={{ marginTop: "1rem" }}>
                  <h2>Edit profile</h2>
                  <ProfileEditForm key={profileQuery.data.email} profile={profileQuery.data} />
                </div>
              </>
            )}
          </>
        )}

        {tab === "security" && <SecurityTab />}
        {tab === "sessions" && <SessionsTab />}
      </div>
    </main>
  );
}
