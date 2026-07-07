import { Link } from "react-router-dom";
import styles from "@/pages/AdminPage.module.css";
import type { AdminUserRow } from "@/lib/admin/types";

function statusClass(status: string) {
  if (status === "active") return styles.statusActive;
  if (status === "locked") return styles.statusLocked;
  return styles.statusInactive;
}

export function UsersTable({
  users,
  linkToDetail = false,
}: {
  users: AdminUserRow[];
  linkToDetail?: boolean;
}) {
  if (users.length === 0) {
    return <p className={styles.loading}>No users found.</p>;
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Username</th>
            <th>Email</th>
            <th>Role</th>
            <th>Status</th>
            <th>Phone</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.id}</td>
              <td>
                {linkToDetail ? (
                  <Link to={`/admin/users/${user.id}`}>{user.username}</Link>
                ) : (
                  user.username
                )}
              </td>
              <td>{user.email}</td>
              <td>
                <span className={styles.role}>{user.role}</span>
              </td>
              <td className={statusClass(user.status)}>{user.status}</td>
              <td>{user.phone_number || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
