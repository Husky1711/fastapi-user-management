import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/AdminShell";
import { UsersTable } from "@/components/UsersTable";
import { fetchAdminOverview, fetchAdminUsersStats } from "@/lib/admin/api";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/AdminPage.module.css";

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className={styles.card}>
      <p className={styles.cardLabel}>{label}</p>
      <p className={styles.cardValue}>{value}</p>
    </div>
  );
}

export function AdminPage() {
  const overviewQuery = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: fetchAdminOverview,
  });

  const usersStatsQuery = useQuery({
    queryKey: ["admin", "users-stats"],
    queryFn: fetchAdminUsersStats,
  });

  const loading = overviewQuery.isLoading || usersStatsQuery.isLoading;
  const error = overviewQuery.error || usersStatsQuery.error;

  return (
    <AdminShell>
      {loading && <p className={styles.loading}>Loading dashboard…</p>}

      {error && (
        <p className={styles.error}>{getApiError(error).detail}</p>
      )}

      {overviewQuery.data && (
        <section className={styles.section}>
          <h2>Organization overview</h2>
          <div className={styles.grid}>
            <StatCard label="Total users" value={overviewQuery.data.total_users} />
            <StatCard label="Active users" value={overviewQuery.data.active_users} />
            <StatCard
              label="Active sessions"
              value={overviewQuery.data.active_sessions}
            />
            <StatCard
              label="Logins today"
              value={overviewQuery.data.today_stats.logins}
            />
            <StatCard
              label="New users today"
              value={overviewQuery.data.today_stats.new_users}
            />
            <StatCard
              label="Password resets today"
              value={overviewQuery.data.today_stats.password_resets}
            />
          </div>
        </section>
      )}

      {usersStatsQuery.data && (
        <section className={styles.section}>
          <h2>User breakdown</h2>
          <div className={styles.grid}>
            <StatCard label="Active" value={usersStatsQuery.data.users_by_status.active} />
            <StatCard
              label="Inactive"
              value={usersStatsQuery.data.users_by_status.inactive}
            />
            <StatCard label="Locked" value={usersStatsQuery.data.users_by_status.locked} />
          </div>
        </section>
      )}

      {usersStatsQuery.data && usersStatsQuery.data.recent_users.length > 0 && (
        <section className={styles.section}>
          <h2>Recent users</h2>
          <UsersTable users={usersStatsQuery.data.recent_users} />
        </section>
      )}
    </AdminShell>
  );
}
