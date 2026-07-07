import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth/AuthProvider";
import { AdminShell } from "@/components/AdminShell";
import { OrgAdminShell } from "@/components/OrgAdminShell";
import { SuperAdminShell } from "@/components/SuperAdminShell";

export function StaffShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  if (user?.role === "super_admin") {
    return <SuperAdminShell>{children}</SuperAdminShell>;
  }
  if (user?.role === "organization_admin") {
    return <OrgAdminShell>{children}</OrgAdminShell>;
  }
  return <AdminShell>{children}</AdminShell>;
}
