import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import styles from "@/pages/AdminPage.module.css";

export function OrgAdminShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Organization Admin</h1>
          <p className={styles.subtitle}>
            {user?.username}
            <span className={styles.badge}>Org #{user?.organization_id}</span>
          </p>
        </div>
        <button type="button" className={styles.logoutBtn} onClick={() => void logout()}>
          Log out
        </button>
      </header>

      <nav className={styles.nav}>
        <Link
          to="/org-admin"
          className={location.pathname === "/org-admin" ? styles.navActive : undefined}
        >
          Dashboard
        </Link>
        <Link to="/admin/users">Users</Link>
        <Link to="/profile">Profile</Link>
      </nav>

      {children}
    </main>
  );
}
