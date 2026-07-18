// Mirrors app/services/permission_service.py — the backend role hierarchy is
// employee < manager < admin. The backend is the source of truth (every route
// re-checks); these helpers only decide what UI to render.
import { User, UserRole } from "@/types";

const ROLE_LEVEL: Record<UserRole, number> = {
  employee: 1,
  manager: 2,
  admin: 3,
};

function atLeast(user: User | null | undefined, role: UserRole): boolean {
  if (!user) return false;
  return (ROLE_LEVEL[user.role] ?? 0) >= ROLE_LEVEL[role];
}

export const permissions = {
  /** GET /api/audit requires manager+ */
  canViewAudit: (user: User | null | undefined) => atLeast(user, "manager"),
  /** Catalog/supplier writes require manager+ */
  canManageCatalog: (user: User | null | undefined) => atLeast(user, "manager"),
  /** Order create/edit/submit requires employee+ (any authenticated role) */
  canCreateOrders: (user: User | null | undefined) => atLeast(user, "employee"),
  /** Approve/reject/sent/complete/delete require manager+ */
  canApproveOrders: (user: User | null | undefined) => atLeast(user, "manager"),
  /** Tenant settings are admin-only */
  canEditSettings: (user: User | null | undefined) => atLeast(user, "admin"),
};

export function hasPermission(
  user: User | null | undefined,
  permission: keyof typeof permissions
): boolean {
  return permissions[permission](user);
}
