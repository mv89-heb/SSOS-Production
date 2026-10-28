import { LayoutDashboard, ShoppingCart, Users, Package, Warehouse, BarChart3, BrainCircuit, FileSearch, CalendarDays, Bell, History, Settings, ClipboardCheck, Archive, ShieldCheck, HelpCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { User } from "@/types";
import { permissions } from "@/lib/permissions";

export type NavItem = { name: string; href: string; icon: LucideIcon; visible: (user: User | null | undefined) => boolean };
export type NavGroup = { label: string; items: NavItem[] };
const all = () => true;
export const NAV_GROUPS: NavGroup[] = [
 { label: "עבודה שוטפת", items: [
  { name: "לוח בקרה", href: "/dashboard", icon: LayoutDashboard, visible: all },
  { name: "הזמנות רכש", href: "/dashboard/orders", icon: ShoppingCart, visible: all },
  { name: "ספקים", href: "/dashboard/suppliers", icon: Users, visible: all },
  { name: "מוצרים ומחירים", href: "/dashboard/catalog", icon: Package, visible: all },
  { name: "מלאי וספירות", href: "/dashboard/inventory", icon: Warehouse, visible: all },
  { name: "דיווח ספירת מלאי", href: "/dashboard/inventory/count", icon: ClipboardCheck, visible: all }
 ]},
 { label: "ניתוח וקבלת החלטות", items: [
  { name: "השוואת מחירים", href: "/dashboard/price-intelligence", icon: BarChart3, visible: all },
  { name: "תמונת מצב רכש", href: "/dashboard/procurement-intelligence", icon: BrainCircuit, visible: all },
  { name: "מסמכים וקליטה", href: "/dashboard/document-intelligence", icon: FileSearch, visible: all }
 ]},
 { label: "מעקב וניהול", items: [
  { name: "יומן ותזכורות", href: "/dashboard/calendar", icon: CalendarDays, visible: all },
  { name: "מרכז תזכורות", href: "/dashboard/reminders", icon: Bell, visible: all },
  { name: "היסטוריית פעולות", href: "/dashboard/audit", icon: History, visible: u => permissions.canViewAudit(u) },
  { name: "הגדרות", href: "/dashboard/settings", icon: Settings, visible: all },
  { name: "ייבוא מחירונים", href: "/dashboard/settings/import", icon: ClipboardCheck, visible: u => permissions.canManageImports(u) },
  { name: "ייבוא היסטורי", href: "/dashboard/settings/historical-import", icon: Archive, visible: u => permissions.canManageImports(u) },
  { name: "Google Calendar", href: "/dashboard/settings/google-calendar", icon: CalendarDays, visible: all },
  { name: "ניהול מערכת", href: "/dashboard/admin", icon: ShieldCheck, visible: u => permissions.canManageUsers(u) },
  { name: "מרכז עזרה", href: "/dashboard/help", icon: HelpCircle, visible: all }
 ]}
];
export function getNavGroups(user: User | null | undefined): NavGroup[] {
 return NAV_GROUPS.map(g => ({ ...g, items: g.items.filter(i => i.visible(user)) })).filter(g => g.items.length);
}
export function getMobileNav(user: User | null | undefined): NavItem[] {
 return getNavGroups(user).flatMap(g => g.items);
}
