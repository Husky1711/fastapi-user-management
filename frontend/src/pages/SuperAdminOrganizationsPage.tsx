import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { SuperAdminShell } from "@/components/SuperAdminShell";
import { getApiError } from "@/lib/apiClient";
import { fetchOrganizations, fetchSuperAdminOrganizationsStats } from "@/lib/superAdmin/api";
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
    queryKey: ["super-admin", "organizations"],
    queryFn: fetchOrganizations,
  });

  const statsQuery = useQuery({
    queryKey: ["super-admin", "organizations-stats"],
    queryFn: fetchSuperAdminOrganizationsStats,
  });

  const loading = orgsQuery.isLoading || statsQuery.isLoading;
  const error = orgsQuery.error || statsQuery.error;

  return (
    <SuperAdminShell>
      <section className={styles.section}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2>Organizations</h2>
            <p className={styles.subtitle}>
              GET /api/v1/organizations · /dashboard/super-admin/organizations/stats
            </p>
          </div>
          <Link to="/super-admin/organizations/new" className={styles.logoutBtn}>
            Create organization
          </Link>
        </div>
      </section>

      {loading && <p className={styles.loading}>Loading organizations…</p>}
      {error && <p className={styles.error}>{getApiError(error).detail}</p>}

      {statsQuery.data && (
        <section className={styles.section}>
          <div className={styles.grid}>
            <StatCard label="Total" value={statsQuery.data.total_organizations} />
            <StatCard label="Active" value={statsQuery.data.active_organizations} />
            <StatCard label="Inactive" value={statsQuery.data.inactive_organizations} />
            <StatCard
              label="Small (&lt;10 users)"
              value={statsQuery.data.organizations_by_size.small}
            />
            <StatCard
              label="Medium (10–100)"
              value={statsQuery.data.organizations_by_size.medium}
            />
            <StatCard label="Large (&gt;100)" value={statsQuery.data.organizations_by_size.large} />
          </div>
        </section>
      )}

      {orgsQuery.data && (
        <section className={styles.section}>
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
                {orgsQuery.data.map((org) => (
                  <tr key={org.id}>
                    <td>{org.id}</td>
                    <td>
                      <Link to={`/super-admin/organizations/${org.id}`}>{org.name}</Link>
                    </td>
                    <td>{org.status}</td>
                    <td>{org.total_users}</td>
                    <td>{org.active_users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </SuperAdminShell>
  );
}
