import { useQuery } from "@tanstack/react-query";
import { AdminShell } from "@/components/AdminShell";
import { UsersTable } from "@/components/UsersTable";
import { fetchUsers } from "@/lib/admin/api";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/AdminPage.module.css";

export function AdminUsersPage() {
  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: fetchUsers,
  });

  return (
    <AdminShell>
      <section className={styles.section}>
        <h2>All users</h2>
        <p className={styles.subtitle}>
          Data from <code>GET /api/v1/users</code>
        </p>

        {usersQuery.isLoading && <p className={styles.loading}>Loading users…</p>}

        {usersQuery.error && (
          <p className={styles.error}>{getApiError(usersQuery.error).detail}</p>
        )}

        {usersQuery.data && (
          <>
            <p className={styles.subtitle} style={{ marginBottom: "1rem" }}>
              {usersQuery.data.length} user{usersQuery.data.length === 1 ? "" : "s"}
            </p>
            <UsersTable users={usersQuery.data} />
          </>
        )}
      </section>
    </AdminShell>
  );
}
