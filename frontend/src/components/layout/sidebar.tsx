"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { LayoutDashboard, Users, Package, ShoppingCart, Settings, History, ShieldCheck, ChevronRight, HelpCircle } from "lucide-react";

const ORGANIZATION_NAME = "ישיבת אוהבי ירושלים - ראשית";
const navigation = [
  { name: "לוח בקרה", href: "/dashboard", icon: LayoutDashboard },
  { name: "ניהול ספקים", href: "/dashboard/suppliers", icon: Users },
  { name: "קטלוג מוצרים", href: "/dashboard/catalog", icon: Package },
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
    <aside dir="rtl" className="sticky right-0 top-0 z-30 hidden h-screen w-64 shrink-0 flex-col border-s border-slate-200/80 bg-white/95 backdrop-blur-md dark:border-slate-800 dark:bg-slate-950/95" aria-label="תפריט ניווט ראשי">
      <div className="flex min-h-24 items-center gap-3 border-b border-slate-100 px-5 dark:border-slate-800"><div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-700 to-violet-700 text-lg font-black text-white shadow-lg shadow-indigo-700/20">ר</div><div className="min-w-0"><div className="truncate text-[15px] font-black leading-5 text-slate-950 dark:text-white">ישיבת אוהבי ירושלים</div><div className="truncate text-xs font-bold text-indigo-600 dark:text-indigo-300">ראשית</div></div></div>
      <div className="px-5 pt-6"><p className="px-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">ניהול מערכת</p></div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-3" aria-label="ניווט ראשי">
        {items.map((item) => { const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(`${item.href}/`)); const Icon = item.icon; return <Link key={item.href} href={item.href} aria-current={isActive ? "page" : undefined} className={cn("group flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-semibold transition-all duration-200", isActive ? "bg-indigo-50 text-indigo-700 shadow-sm dark:bg-indigo-950/60 dark:text-indigo-300" : "text-slate-500 hover:bg-slate-50 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-white")}><span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors", isActive ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20" : "bg-slate-100 text-slate-500 group-hover:bg-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:group-hover:bg-slate-800")}><Icon className="h-[18px] w-[18px]" aria-hidden="true" /></span><span className="flex-1">{item.name}</span>{isActive && <ChevronRight className="h-4 w-4 opacity-70" aria-hidden="true" />}</Link>; })}
      </nav>
      <div className="space-y-2 border-t border-slate-100 p-4 dark:border-slate-800"><Link href="/dashboard/help" className={cn("flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-bold transition", pathname.startsWith("/dashboard/help") ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900 dark:hover:bg-slate-900 dark:hover:text-white")}><HelpCircle className="h-5 w-5" /><span>מרכז עזרה</span></Link><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><p className="text-xs font-bold text-slate-700 dark:text-slate-200">{ORGANIZATION_NAME}</p><p className="mt-0.5 text-[11px] text-slate-400">מערכת ניהול רכש</p></div></div>
    </aside>
  );
}
