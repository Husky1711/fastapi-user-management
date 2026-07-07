import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import { getHomePathForRole } from "@/lib/auth/routing";
import styles from "@/pages/AdminPage.module.css";

export function ComplianceShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const home = user ? getHomePathForRole(user.role) : "/dashboard";

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Compliance</h1>
          <p className={styles.subtitle}>
            {user?.username}
            <span className={styles.badge}>M8 production APIs</span>
          </p>
        </div>
        <button type="button" className={styles.logoutBtn} onClick={() => void logout()}>
          Log out
        </button>
      </header>

      <nav className={styles.nav}>
        <Link to={home}>Dashboard</Link>
        <Link
          to="/compliance"
          className={location.pathname === "/compliance" ? styles.navActive : undefined}
        >
          Compliance
        </Link>
        <Link to="/profile">Profile</Link>
      </nav>

      {children}
    </main>
  );
}
