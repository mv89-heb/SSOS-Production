"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { LayoutDashboard, Users, Package, ShoppingCart, Settings, History, ShieldCheck, ChevronRight, HelpCircle, BarChart3 } from "lucide-react";

const ORGANIZATION_NAME = "ישיבת אוהבי ירושלים - ראשית";
const navigation = [
  { name: "לוח בקרה", href: "/dashboard", icon: LayoutDashboard },
  { name: "ניהול ספקים", href: "/dashboard/suppliers", icon: Users },
  { name: "קטלוג מוצרים", href: "/dashboard/catalog", icon: Package },
  { name: "השוואת ספקים", href: "/dashboard/price-intelligence", icon: BarChart3 },
  { name: "הזמנות רכש", href: "/dashboard/orders", icon: ShoppingCart },
  { name: "לוג ביקורת", href: "/dashboard/audit", icon: History },
  { name: "הגדרות מערכת", href: "/dashboard/settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const items = permissions.canManageUsers(user)
    ? [...navigation, { name: "מרכז מנהל מערכת", href: "/dashboard/admin", icon: ShieldCheck }]
    : navigation;

  return (
    <aside dir="rtl" className="fixed right-0 top-0 z-[100] hidden h-dvh w-64 flex-col border-l border-slate-800/80 bg-[#071d33] text-white shadow-2xl md:flex" aria-label="תפריט ניווט ראשי">
      <div className="relative flex min-h-24 shrink-0 items-center gap-3 overflow-hidden border-b border-white/10 px-5">
        <div className="absolute -left-10 -top-16 h-40 w-40 rounded-full bg-indigo-500/20 blur-3xl" aria-hidden="true" />
        <div className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-blue-600 text-lg font-black text-white shadow-lg shadow-indigo-950/40">ר</div>
        <div className="relative min-w-0"><div className="truncate text-[15px] font-black leading-5 text-white">ישיבת אוהבי ירושלים</div><div className="truncate text-xs font-bold text-blue-300">ראשית</div></div>
      </div>
      <div className="shrink-0 px-5 pt-6"><p className="px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">ניהול מערכת</p></div>
      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto px-4 py-3" aria-label="ניווט ראשי">
        {items.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(`${item.href}/`));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "group flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-semibold transition-all duration-200",
                isActive
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-950/30"
                  : "text-slate-300 hover:bg-white/8 hover:text-white"
              )}
            >
              <span className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors",
                isActive ? "bg-white/15 text-white" : "bg-white/5 text-slate-400 group-hover:bg-white/10 group-hover:text-white"
              )}>
                <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
              </span>
              <span className="flex-1">{item.name}</span>
              {isActive && <ChevronRight className="h-4 w-4 opacity-80" aria-hidden="true" />}
            </Link>
          );
        })}
      </nav>
      <div className="shrink-0 space-y-2 border-t border-white/10 p-4">
        <Link href="/dashboard/help" className={cn(
          "flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-bold transition",
          pathname.startsWith("/dashboard/help") ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/8 hover:text-white"
        )}>
          <HelpCircle className="h-5 w-5" />
          <span>מרכז עזרה</span>
        </Link>
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <p className="text-xs font-bold text-white">{ORGANIZATION_NAME}</p>
          <p className="mt-0.5 text-[11px] text-slate-400">מערכת ניהול רכש</p>
        </div>
      </div>
    </aside>
  );
}
