export function getHomePathForRole(role: string): string {
  if (role === "super_admin" || role === "admin") {
    return "/admin";
  }
  if (role === "organization_admin") {
    return "/org-admin";
  }
  return "/dashboard";
}

export function isOrgAdminRole(role: string): boolean {
  return role === "organization_admin" || role === "super_admin";
}
