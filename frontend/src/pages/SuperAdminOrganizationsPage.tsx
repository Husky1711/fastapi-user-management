import { useQuery } from "@tanstack/react-query";
import { SuperAdminShell } from "@/components/SuperAdminShell";
import { getApiError } from "@/lib/apiClient";
import { fetchSuperAdminOrganizationsStats } from "@/lib/superAdmin/api";
import styles from "@/pages/AdminPage.module.css";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.card}>
      <p className={styles.cardLabel}>{label}</p>
      <p className={styles.cardValue}>{value}</p>
    </div>
  );
}

export function SuperAdminOrganizationsPage() {
  const orgsQuery = useQuery({
    queryKey: ["super-admin", "organizations-stats"],
    queryFn: fetchSuperAdminOrganizationsStats,
  });

  return (
    <SuperAdminShell>
      {orgsQuery.isLoading && <p className={styles.loading}>Loading organizations…</p>}
      {orgsQuery.error && (
        <p className={styles.error}>{getApiError(orgsQuery.error).detail}</p>
      )}

      {orgsQuery.data && (
        <>
          <section className={styles.section}>
            <h2>Organizations overview</h2>
            <p className={styles.subtitle}>GET /api/v1/dashboard/super-admin/organizations/stats</p>
            <div className={styles.grid}>
              <StatCard label="Total" value={orgsQuery.data.total_organizations} />
              <StatCard label="Active" value={orgsQuery.data.active_organizations} />
              <StatCard label="Inactive" value={orgsQuery.data.inactive_organizations} />
              <StatCard
                label="Small (&lt;10 users)"
                value={orgsQuery.data.organizations_by_size.small}
              />
              <StatCard
                label="Medium (10–100)"
                value={orgsQuery.data.organizations_by_size.medium}
              />
              <StatCard
                label="Large (&gt;100)"
                value={orgsQuery.data.organizations_by_size.large}
              />
            </div>
          </section>

          <section className={styles.section}>
            <h2>All organizations</h2>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Total users</th>
                    <th>Active users</th>
                  </tr>
                </thead>
                <tbody>
                  {orgsQuery.data.organizations.map((org) => (
                    <tr key={org.id}>
                      <td>{org.id}</td>
                      <td>{org.name}</td>
                      <td>{org.status}</td>
                      <td>{org.total_users}</td>
                      <td>{org.active_users}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </SuperAdminShell>
  );
}
