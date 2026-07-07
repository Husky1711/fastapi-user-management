import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import styles from "@/pages/AdminPage.module.css";

export function SuperAdminShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Super Admin</h1>
          <p className={styles.subtitle}>
            {user?.username}
            <span className={styles.badge}>System-wide view</span>
          </p>
        </div>
        <button type="button" className={styles.logoutBtn} onClick={() => void logout()}>
          Log out
        </button>
      </header>

      <nav className={styles.nav}>
        <Link
          to="/super-admin"
          className={location.pathname === "/super-admin" ? styles.navActive : undefined}
        >
          Dashboard
        </Link>
        <Link
          to="/super-admin/organizations"
          className={
            location.pathname.startsWith("/super-admin/organizations")
              ? styles.navActive
              : undefined
          }
        >
          Organizations
        </Link>
        <Link to="/compliance">Compliance</Link>
        <Link to="/admin/users">Users</Link>
        <Link to="/admin/users/new">Create user</Link>
        <Link to="/profile">Profile</Link>
      </nav>

      {children}
    </main>
  );
}
