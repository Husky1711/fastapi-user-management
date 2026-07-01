import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";

export function UnauthorizedPage() {
  const { user } = useAuth();

  return (
    <main style={{ padding: "2rem", maxWidth: 480 }}>
      <h1>403 — Unauthorized</h1>
      <p>
        {user
          ? `Signed in as ${user.username}, but you do not have access to this area.`
          : "You do not have access to this area."}
      </p>
      <p>
        <Link to={user?.role === "user" ? "/dashboard" : "/admin"}>Go back</Link>
      </p>
    </main>
  );
}
