import type { UserRole } from "@/lib/auth/types";

const ROLE_RANK: Record<string, number> = {
  user: 1,
  admin: 2,
  organization_admin: 3,
  super_admin: 4,
};

export function allowedCreateRoles(creatorRole: UserRole | string): string[] {
  switch (creatorRole) {
    case "super_admin":
      return ["organization_admin", "admin", "user"];
    case "organization_admin":
      return ["admin", "user"];
    case "admin":
      return ["user"];
    default:
      return [];
  }
}

export function canEditUser(
  editorRole: UserRole | string,
  targetRole: string,
): boolean {
  if (editorRole === "user") {
    return false;
  }
  if (targetRole === "super_admin") {
    return editorRole === "super_admin";
  }
  if (editorRole === "super_admin") {
    return true;
  }
  const editorRank = ROLE_RANK[editorRole] ?? 0;
  const targetRank = ROLE_RANK[targetRole] ?? 0;
  return targetRank < editorRank;
}

export function isManagerRole(role: string): boolean {
  return role === "admin" || role === "organization_admin" || role === "super_admin";
}
