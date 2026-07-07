import { useQuery } from "@tanstack/react-query";
import { SuperAdminShell } from "@/components/SuperAdminShell";
import { UsersTable } from "@/components/UsersTable";
import { getApiError } from "@/lib/apiClient";
import {
  fetchSuperAdminOrganizationsStats,
  fetchSuperAdminOverview,
  fetchSuperAdminSessionsStats,
  fetchSuperAdminUsersStats,
} from "@/lib/superAdmin/api";
import styles from "@/pages/AdminPage.module.css";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.card}>
      <p className={styles.cardLabel}>{label}</p>
      <p className={styles.cardValue}>{value}</p>
    </div>
  );
}

export function SuperAdminPage() {
  const overviewQuery = useQuery({
    queryKey: ["super-admin", "overview"],
    queryFn: fetchSuperAdminOverview,
  });

  const usersStatsQuery = useQuery({
    queryKey: ["super-admin", "users-stats"],
    queryFn: fetchSuperAdminUsersStats,
  });

  const orgsStatsQuery = useQuery({
    queryKey: ["super-admin", "organizations-stats"],
    queryFn: fetchSuperAdminOrganizationsStats,
  });

  const sessionsStatsQuery = useQuery({
    queryKey: ["super-admin", "sessions-stats"],
    queryFn: fetchSuperAdminSessionsStats,
  });

  const loading =
    overviewQuery.isLoading ||
    usersStatsQuery.isLoading ||
    orgsStatsQuery.isLoading ||
    sessionsStatsQuery.isLoading;
  const error =
    overviewQuery.error ||
    usersStatsQuery.error ||
    orgsStatsQuery.error ||
    sessionsStatsQuery.error;

  return (
    <SuperAdminShell>
      {loading && <p className={styles.loading}>Loading system dashboard…</p>}
      {error && <p className={styles.error}>{getApiError(error).detail}</p>}

      {overviewQuery.data && (
        <section className={styles.section}>
          <h2>System overview</h2>
          <div className={styles.grid}>
            <StatCard label="Organizations" value={overviewQuery.data.total_organizations} />
            <StatCard label="Total users" value={overviewQuery.data.total_users} />
            <StatCard label="Active users" value={overviewQuery.data.active_users} />
            <StatCard label="Total admins" value={overviewQuery.data.total_admins} />
            <StatCard label="Active sessions" value={overviewQuery.data.active_sessions} />
            <StatCard label="Total sessions" value={overviewQuery.data.total_sessions} />
            <StatCard
              label="Super admins"
              value={overviewQuery.data.users_by_role.super_admin}
            />
            <StatCard
              label="Org admins"
              value={overviewQuery.data.users_by_role.organization_admin}
            />
            <StatCard label="Admins" value={overviewQuery.data.users_by_role.admin} />
            <StatCard label="Users" value={overviewQuery.data.users_by_role.user} />
            <StatCard label="Logins today" value={overviewQuery.data.today_stats.logins} />
            <StatCard
              label="New users today"
              value={overviewQuery.data.today_stats.new_users}
            />
            <StatCard
              label="Audit logs today"
              value={overviewQuery.data.today_stats.total_audit_logs}
            />
          </div>
        </section>
      )}

      {orgsStatsQuery.data && (
        <section className={styles.section}>
          <h2>Organizations</h2>
          <div className={styles.grid}>
            <StatCard label="Total" value={orgsStatsQuery.data.total_organizations} />
            <StatCard label="Active" value={orgsStatsQuery.data.active_organizations} />
            <StatCard label="Inactive" value={orgsStatsQuery.data.inactive_organizations} />
            <StatCard label="Small (&lt;10 users)" value={orgsStatsQuery.data.organizations_by_size.small} />
            <StatCard
              label="Medium (10–100)"
              value={orgsStatsQuery.data.organizations_by_size.medium}
            />
            <StatCard label="Large (&gt;100)" value={orgsStatsQuery.data.organizations_by_size.large} />
          </div>
        </section>
      )}

      {usersStatsQuery.data && (
        <section className={styles.section}>
          <h2>Users</h2>
          <div className={styles.grid}>
            <StatCard label="Active" value={usersStatsQuery.data.users_by_status.active} />
            <StatCard label="Inactive" value={usersStatsQuery.data.users_by_status.inactive} />
            <StatCard label="Locked" value={usersStatsQuery.data.users_by_status.locked} />
            <StatCard label="Created today" value={usersStatsQuery.data.users_today} />
            <StatCard label="Created this week" value={usersStatsQuery.data.users_this_week} />
            <StatCard label="Created this month" value={usersStatsQuery.data.users_this_month} />
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
    </SuperAdminShell>
  );
}
