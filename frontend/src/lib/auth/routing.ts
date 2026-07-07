export function getHomePathForRole(role: string): string {
  if (role === "super_admin") {
    return "/super-admin";
  }
  if (role === "admin") {
    return "/admin";
  }
  if (role === "organization_admin") {
    return "/org-admin";
  }
  return "/dashboard";
}

export function isOrgAdminRole(role: string): boolean {
  return role === "organization_admin";
}

export function isSuperAdminRole(role: string): boolean {
  return role === "super_admin";
}
