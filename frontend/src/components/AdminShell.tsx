import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import styles from "@/pages/AdminPage.module.css";

export function AdminShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Admin</h1>
          <p className={styles.subtitle}>{user?.username}</p>
        </div>
        <button type="button" className={styles.logoutBtn} onClick={() => void logout()}>
          Log out
        </button>
      </header>

      <nav className={styles.nav}>
        <Link
          to="/admin"
          className={location.pathname === "/admin" ? styles.navActive : undefined}
        >
          Dashboard
        </Link>
        <Link
          to="/admin/users"
          className={
            location.pathname.startsWith("/admin/users") ? styles.navActive : undefined
          }
        >
          Users
        </Link>
        <Link
          to="/admin/users/new"
          className={location.pathname === "/admin/users/new" ? styles.navActive : undefined}
        >
          Create user
        </Link>
        <Link to="/compliance">Compliance</Link>
        <Link to="/profile">Profile</Link>
      </nav>

      {children}
    </main>
  );
}
