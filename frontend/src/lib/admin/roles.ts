import type { UserRole } from "@/lib/auth/types";

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
