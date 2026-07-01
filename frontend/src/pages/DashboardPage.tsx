import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";

export function DashboardPage() {
  const { user, logout } = useAuth();

  return (
    <main style={{ padding: "2rem" }}>
      <header style={{ display: "flex", justifyContent: "space-between", gap: "1rem" }}>
        <div>
          <h1>Dashboard</h1>
          <p>Welcome, {user?.username}</p>
        </div>
        <button type="button" onClick={() => void logout()}>
          Log out
        </button>
      </header>
      <nav style={{ marginTop: "1rem", display: "flex", gap: "1rem" }}>
        <Link to="/profile">Profile</Link>
      </nav>
      <p style={{ marginTop: "2rem", color: "#64748b" }}>
        User dashboard cards — Milestone 2
      </p>
    </main>
  );
}
