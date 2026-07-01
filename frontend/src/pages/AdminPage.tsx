import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";

export function AdminPage() {
  const { user, logout } = useAuth();
  const isSuperAdmin = user?.role === "super_admin";

  return (
    <main style={{ padding: "2rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
        <div>
          <h1>Admin</h1>
          <p>
            {user?.username}
            {isSuperAdmin && (
              <span style={{ marginLeft: 8, fontSize: 12, color: "#0369a1" }}>
                System-wide view
              </span>
            )}
          </p>
        </div>
        <button type="button" onClick={() => void logout()}>
          Log out
        </button>
      </header>
      <nav style={{ marginTop: "1rem", display: "flex", gap: "1rem" }}>
        <Link to="/admin/users">Users</Link>
        <Link to="/profile">Profile</Link>
      </nav>
      <p style={{ marginTop: "2rem", color: "#64748b" }}>
        Admin dashboard cards — Milestone 3
      </p>
    </main>
  );
}
