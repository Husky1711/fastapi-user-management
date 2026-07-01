import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import { AuthBootstrapShell } from "@/components/AuthBootstrapShell";

function isAdminRole(role: string) {
  return role === "admin" || role === "organization_admin" || role === "super_admin";
}

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

  return <Navigate to={isAdminRole(user.role) ? "/admin" : "/dashboard"} replace />;
}
