import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/auth/AuthProvider";
import { AuthBootstrapShell } from "@/components/AuthBootstrapShell";
import {
  canManageUsers,
  isOrgAdminRole,
  isSuperAdminRole,
  canAccessCompliance,
} from "@/lib/auth/routing";

export function ProtectedRoute({
  adminOnly = false,
  orgAdminOnly = false,
  superAdminOnly = false,
  userMgmtOnly = false,
  complianceOnly = false,
}: {
  adminOnly?: boolean;
  orgAdminOnly?: boolean;
  superAdminOnly?: boolean;
  userMgmtOnly?: boolean;
  complianceOnly?: boolean;
}) {
  const { status, user } = useAuth();

  if (status === "bootstrapping") {
    return <AuthBootstrapShell />;
  }

  if (status !== "authenticated" || !user) {
    return <Navigate to="/login" replace />;
  }

  if (superAdminOnly && !isSuperAdminRole(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (orgAdminOnly && !isOrgAdminRole(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (adminOnly && user.role !== "admin") {
    return <Navigate to="/unauthorized" replace />;
  }

  if (userMgmtOnly && !canManageUsers(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (complianceOnly && !canAccessCompliance(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <Outlet />;
}
