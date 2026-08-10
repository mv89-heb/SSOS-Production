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
  return (ROLE_RANK[user.role] ?? 0) >= ROLE_RANK[minimum];
}

export const permissions = {
  // orders.py: create_order / update_order / submit_order require "employee"
  canCreateOrders: (user: User | null | undefined) => atLeast(user, "employee"),
  // orders.py: approve_order / reject_order / mark_sent / mark_completed / delete_order require "manager"
  canApproveOrders: (user: User | null | undefined) => atLeast(user, "manager"),
  // catalog.py: create/update supplier & product require "manager"
  canManageCatalog: (user: User | null | undefined) => atLeast(user, "manager"),
  // audit.py: list_audit_logs / verify_audit_chain require "manager"
  canViewAudit: (user: User | null | undefined) => atLeast(user, "manager"),
  // imports.py: every import route (upload/analyze/mapping/validate/commit) requires "manager"
  canManageImports: (user: User | null | undefined) => atLeast(user, "manager"),
};

export function hasPermission(user: User | null | undefined, minimumRole: UserRole): boolean {
  return atLeast(user, minimumRole);
}
