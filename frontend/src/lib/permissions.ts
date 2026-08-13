import type { User, UserRole } from "@/types";

// Mirrors app/models/user.py ROLE_RANK and each route's
// PermissionService.require_role_at_least(...) call, so the UI only shows
// actions the backend will actually allow.
const ROLE_RANK: Record<UserRole, number> = {
  employee: 1,
  manager: 2,
  admin: 3,
};

function atLeast(user: User | null | undefined, minimum: UserRole): boolean {
  if (!user) return false;
  const role = String(user.role ?? "").trim().toLowerCase() as UserRole;
  const required = String(minimum).trim().toLowerCase() as UserRole;
  return (ROLE_RANK[role] ?? 0) >= (ROLE_RANK[required] ?? 99);
}

export const permissions = {
  canCreateOrders: (user: User | null | undefined) => atLeast(user, "employee"),
  canApproveOrders: (user: User | null | undefined) => atLeast(user, "manager"),
  canManageCatalog: (user: User | null | undefined) => atLeast(user, "manager"),
  canViewAudit: (user: User | null | undefined) => atLeast(user, "manager"),
  canManageImports: (user: User | null | undefined) => atLeast(user, "manager"),
  canManageUsers: (user: User | null | undefined) => atLeast(user, "admin"),
};

export function hasPermission(user: User | null | undefined, minimumRole: UserRole): boolean {
  return atLeast(user, minimumRole);
}
