import { useQuery } from "@tanstack/react-query";
import { OrgAdminShell } from "@/components/OrgAdminShell";
import { UsersTable } from "@/components/UsersTable";
import {
  fetchOrgAdminOverview,
  fetchOrgAdminSessionsStats,
  fetchOrgAdminUsersStats,
} from "@/lib/orgAdmin/api";
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

export function OrgAdminPage() {
  const overviewQuery = useQuery({
    queryKey: ["org-admin", "overview"],
    queryFn: fetchOrgAdminOverview,
  });

  const usersStatsQuery = useQuery({
    queryKey: ["org-admin", "users-stats"],
    queryFn: fetchOrgAdminUsersStats,
  });

  const sessionsStatsQuery = useQuery({
    queryKey: ["org-admin", "sessions-stats"],
    queryFn: fetchOrgAdminSessionsStats,
  });

  const loading =
    overviewQuery.isLoading || usersStatsQuery.isLoading || sessionsStatsQuery.isLoading;
  const error =
    overviewQuery.error || usersStatsQuery.error || sessionsStatsQuery.error;

  return (
    <OrgAdminShell>
      {loading && <p className={styles.loading}>Loading organization dashboard…</p>}
      {error && <p className={styles.error}>{getApiError(error).detail}</p>}

      {overviewQuery.data && (
        <section className={styles.section}>
          <h2>Organization overview</h2>
          <div className={styles.grid}>
            <StatCard label="Total users" value={overviewQuery.data.total_users} />
            <StatCard label="Active users" value={overviewQuery.data.active_users} />
            <StatCard label="Active sessions" value={overviewQuery.data.active_sessions} />
            <StatCard label="Admins" value={overviewQuery.data.users_by_role.admins} />
            <StatCard
              label="Org admins"
              value={overviewQuery.data.users_by_role.organization_admins}
            />
            <StatCard label="Users" value={overviewQuery.data.users_by_role.users} />
            <StatCard label="Logins today" value={overviewQuery.data.today_stats.logins} />
            <StatCard label="New users today" value={overviewQuery.data.today_stats.new_users} />
          </div>
        </section>
      )}

      {usersStatsQuery.data && (
        <section className={styles.section}>
          <h2>Users by status</h2>
          <div className={styles.grid}>
            <StatCard label="Active" value={usersStatsQuery.data.users_by_status.active} />
            <StatCard label="Inactive" value={usersStatsQuery.data.users_by_status.inactive} />
            <StatCard label="Locked" value={usersStatsQuery.data.users_by_status.locked} />
          </div>
          {usersStatsQuery.data.recent_users.length > 0 && (
            <>
              <h2 style={{ marginTop: "1.5rem" }}>Recent users</h2>
              <UsersTable users={usersStatsQuery.data.recent_users} linkToDetail />
            </>
          )}
        </section>
      )}

      {sessionsStatsQuery.data && (
        <section className={styles.section}>
          <h2>Sessions</h2>
          <div className={styles.grid}>
            <StatCard label="Total" value={sessionsStatsQuery.data.total_sessions} />
            <StatCard label="Active" value={sessionsStatsQuery.data.active_sessions} />
            <StatCard label="Revoked" value={sessionsStatsQuery.data.revoked_sessions} />
          </div>
        </section>
      )}
    </OrgAdminShell>
  );
}
