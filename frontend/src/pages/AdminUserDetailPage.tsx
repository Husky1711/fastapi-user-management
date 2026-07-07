import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/AdminShell";
import { fetchUserById } from "@/lib/admin/api";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/ProfilePage.module.css";

export function AdminUserDetailPage() {
  const { userId } = useParams();
  const id = Number(userId);

  const userQuery = useQuery({
    queryKey: ["admin", "user", id],
    queryFn: () => fetchUserById(id),
    enabled: Number.isFinite(id),
  });

  return (
    <AdminShell>
      <section className={styles.panel}>
        <Link to="/admin/users" className={styles.backLink}>
          ← Back to users
        </Link>
        <h2 style={{ marginTop: "1rem" }}>User detail</h2>
        <p className={styles.subtitle}>GET /api/v1/users/{userId}</p>

        {userQuery.isLoading && <p className={styles.loading}>Loading user…</p>}
        {userQuery.error && (
          <p className={styles.error}>{getApiError(userQuery.error).detail}</p>
        )}

        {userQuery.data && (
          <div className={styles.card} style={{ marginTop: "1rem" }}>
            <div className={styles.fieldGrid}>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>ID</span>
                <span className={styles.fieldValue}>{userQuery.data.id}</span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Username</span>
                <span className={styles.fieldValue}>{userQuery.data.username}</span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Email</span>
                <span className={styles.fieldValue}>{userQuery.data.email}</span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Role</span>
                <span className={styles.fieldValue}>{userQuery.data.role}</span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Status</span>
                <span className={styles.fieldValue}>{userQuery.data.status}</span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Organization</span>
                <span className={styles.fieldValue}>
                  {userQuery.data.organization_id}
                </span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Phone</span>
                <span className={styles.fieldValue}>
                  {userQuery.data.phone_number || "—"}
                </span>
              </div>
            </div>
          </div>
        )}
      </section>
    </AdminShell>
  );
}
