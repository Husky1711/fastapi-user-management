import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth/AuthProvider";
import {
  fetchUserActivity,
  fetchUserDashboardSessions,
  fetchUserOverview,
} from "@/lib/dashboard/api";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/AdminPage.module.css";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.card}>
      <p className={styles.cardLabel}>{label}</p>
      <p className={styles.cardValue}>{value}</p>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export function DashboardPage() {
  const { user, logout } = useAuth();

  const overviewQuery = useQuery({
    queryKey: ["dashboard", "user", "overview"],
    queryFn: fetchUserOverview,
  });

  const activityQuery = useQuery({
    queryKey: ["dashboard", "user", "activity"],
    queryFn: fetchUserActivity,
  });

  const sessionsQuery = useQuery({
    queryKey: ["dashboard", "user", "sessions"],
    queryFn: fetchUserDashboardSessions,
  });

  const loading =
    overviewQuery.isLoading || activityQuery.isLoading || sessionsQuery.isLoading;
  const error = overviewQuery.error || activityQuery.error || sessionsQuery.error;

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Dashboard</h1>
          <p className={styles.subtitle}>Welcome, {user?.username}</p>
        </div>
        <button type="button" className={styles.logoutBtn} onClick={() => void logout()}>
          Log out
        </button>
      </header>

      <nav className={styles.nav}>
        <Link to="/profile">Profile</Link>
      </nav>

      {loading && <p className={styles.loading}>Loading dashboard…</p>}
      {error && <p className={styles.error}>{getApiError(error).detail}</p>}

      {overviewQuery.data && (
        <section className={styles.section}>
          <h2>Account overview</h2>
          <div className={styles.grid}>
            <StatCard
              label="Active sessions"
              value={overviewQuery.data.active_sessions}
            />
            <StatCard
              label="Last login"
              value={formatDate(overviewQuery.data.last_login)}
            />
            <StatCard
              label="Account created"
              value={formatDate(overviewQuery.data.account_created)}
            />
            <StatCard label="Status" value={overviewQuery.data.profile.status} />
            <StatCard label="Role" value={overviewQuery.data.profile.role} />
            <StatCard
              label="2FA"
              value={overviewQuery.data.profile.is_2fa_enabled ? "On" : "Off"}
            />
          </div>
        </section>
      )}

      {activityQuery.data && (
        <section className={styles.section}>
          <h2>Login activity</h2>
          <div className={styles.grid}>
            <StatCard label="Today" value={activityQuery.data.total_logins_today} />
            <StatCard label="This week" value={activityQuery.data.total_logins_this_week} />
            <StatCard label="This month" value={activityQuery.data.total_logins_this_month} />
          </div>
          {activityQuery.data.recent_activity.length > 0 && (
            <div className={styles.tableWrap} style={{ marginTop: "1rem" }}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Time</th>
                    <th>IP</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {activityQuery.data.recent_activity.map((item, index) => (
                    <tr key={`${item.action}-${item.time}-${index}`}>
                      <td>{item.action}</td>
                      <td>{formatDate(item.time)}</td>
                      <td>{item.ip_address || "—"}</td>
                      <td>{item.status || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {sessionsQuery.data && (
        <section className={styles.section}>
          <h2>Active sessions ({sessionsQuery.data.total_sessions})</h2>
          {sessionsQuery.data.active_sessions.length === 0 ? (
            <p className={styles.loading}>No active sessions.</p>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Device</th>
                    <th>Location</th>
                    <th>IP</th>
                    <th>Last active</th>
                    <th>Expires</th>
                  </tr>
                </thead>
                <tbody>
                  {sessionsQuery.data.active_sessions.map((session) => (
                    <tr key={session.id}>
                      <td>{session.device}</td>
                      <td>{session.location}</td>
                      <td>{session.ip_address || "—"}</td>
                      <td>{formatDate(session.last_active)}</td>
                      <td>{formatDate(session.expires_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
