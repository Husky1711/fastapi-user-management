import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import { getHomePathForRole } from "@/lib/auth/routing";
import { AuthBootstrapShell } from "@/components/AuthBootstrapShell";

export function HomeRedirect() {
  const { status, user, bootstrapError } = useAuth();

  if (bootstrapError) {
    return <Navigate to="/maintenance" replace />;
  }

  if (status === "bootstrapping") {
    return <AuthBootstrapShell />;
  }

  if (status !== "authenticated" || !user) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={getHomePathForRole(user.role)} replace />;
}
