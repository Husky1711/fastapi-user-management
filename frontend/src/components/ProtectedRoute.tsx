import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import { AuthBootstrapShell } from "@/components/AuthBootstrapShell";

export function ProtectedRoute({ adminOnly = false }: { adminOnly?: boolean }) {
  const { status, user } = useAuth();

  if (status === "bootstrapping") {
    return <AuthBootstrapShell />;
  }

  if (status !== "authenticated" || !user) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly) {
    const isAdmin =
      user.role === "admin" ||
      user.role === "organization_admin" ||
      user.role === "super_admin";
    if (!isAdmin) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return <Outlet />;
}
