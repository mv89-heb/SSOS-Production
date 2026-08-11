"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Users, Package, ShoppingCart, Settings, History, ShieldCheck, LogOut, Menu, X, HelpCircle } from "lucide-react";

const ORGANIZATION_NAME = "ישיבת אוהבי ירושלים - ראשית";
const ROLE_LABELS: Record<string, string> = { admin: "מנהל מערכת", manager: "מנהל", employee: "עובד" };
const NAVIGATION = [
  { name: "לוח בקרה", href: "/dashboard", icon: LayoutDashboard },
  { name: "ניהול ספקים", href: "/dashboard/suppliers", icon: Users },
  { name: "קטלוג מוצרים", href: "/dashboard/catalog", icon: Package },
  { name: "הזמנות רכש", href: "/dashboard/orders", icon: ShoppingCart },
  { name: "לוג ביקורת", href: "/dashboard/audit", icon: History },
  { name: "הגדרות מערכת", href: "/dashboard/settings", icon: Settings },
  { name: "מרכז עזרה", href: "/dashboard/help", icon: HelpCircle },
];

export default function Header() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigation = permissions.canManageUsers(user) ? [...NAVIGATION, { name: "מרכז מנהל מערכת", href: "/dashboard/admin", icon: ShieldCheck }] : NAVIGATION;
  useEffect(() => { setMobileOpen(false); }, [pathname]);
  useEffect(() => { if (!mobileOpen) return; const previousOverflow = document.body.style.overflow; document.body.style.overflow = "hidden"; const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileOpen(false); }; window.addEventListener("keydown", onKeyDown); return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown", onKeyDown); }; }, [mobileOpen]);

  return (
    <>
      <header className="sticky top-0 z-40 flex min-h-16 min-w-0 items-center justify-between border-b border-slate-200/80 bg-white/90 px-3 backdrop-blur-md sm:px-6 dark:border-slate-800 dark:bg-slate-950/90">
        <div className="flex min-w-0 items-center gap-2 sm:gap-4"><button type="button" onClick={() => setMobileOpen(true)} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 md:hidden dark:hover:bg-slate-900 dark:hover:text-white" aria-label="פתיחת תפריט" aria-expanded={mobileOpen}><Menu className="h-5 w-5" /></button><Link href="/dashboard" className="hidden items-center gap-2 md:flex" aria-label="חזרה ללוח הבקרה"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-700 to-violet-700 text-sm font-black text-white">ר</span><span className="hidden xl:inline text-sm font-black text-slate-900 dark:text-white">ראשית</span></Link><div className="h-5 w-px shrink-0 bg-slate-200 dark:bg-slate-800" aria-hidden="true" /><div className="min-w-0 text-sm text-slate-500 dark:text-slate-400"><span className="hidden font-semibold sm:inline">ארגון פעיל: </span><span className="inline-block max-w-[220px] truncate rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-800 dark:bg-slate-900 dark:text-slate-200">{ORGANIZATION_NAME}</span></div></div>
        <div className="flex shrink-0 items-center gap-2 sm:gap-3"><div className="hidden items-center gap-2 sm:flex"><div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-xs font-black text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300" aria-hidden="true">{(user?.full_name ?? "מ").slice(0, 1).toUpperCase()}</div><div className="text-end"><div className="max-w-[180px] truncate text-xs font-bold text-slate-800 dark:text-slate-100">{user?.full_name ?? "—"}</div><div className="text-[10px] text-slate-500 dark:text-slate-400">{user ? ROLE_LABELS[user.role] ?? user.role : "—"}</div></div></div><Link href="/dashboard/help" className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition hover:bg-indigo-50 hover:text-indigo-600 dark:hover:bg-indigo-950/40 dark:hover:text-indigo-300" title="מרכז עזרה" aria-label="מרכז עזרה"><HelpCircle className="h-4 w-4" /></Link><button type="button" onClick={() => logout()} className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30 dark:hover:text-red-400" title="התנתק מהמערכת" aria-label="התנתק מהמערכת"><LogOut className="h-4 w-4" /></button></div>
      </header>
      {mobileOpen && <div className="fixed inset-0 z-[90] md:hidden" role="dialog" aria-modal="true" aria-label="תפריט ניווט"><button type="button" className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm" onClick={() => setMobileOpen(false)} aria-label="סגירת תפריט" /><aside className="absolute inset-y-0 right-0 flex w-[min(86vw,340px)] flex-col bg-white shadow-2xl dark:bg-slate-950" dir="rtl"><div className="flex min-h-20 items-center justify-between border-b border-slate-100 px-4 dark:border-slate-800"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-700 to-violet-700 text-sm font-black text-white">ר</div><div><p className="text-sm font-black text-slate-900 dark:text-white">ישיבת אוהבי ירושלים</p><p className="text-xs font-bold text-indigo-600 dark:text-indigo-300">ראשית</p></div></div><button type="button" onClick={() => setMobileOpen(false)} className="rounded-xl p-2 text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-900" aria-label="סגירת תפריט"><X className="h-5 w-5" /></button></div><nav className="flex-1 space-y-1 overflow-y-auto p-4">{navigation.map((item) => { const Icon = item.icon; const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(`${item.href}/`)); return <Link key={item.href} href={item.href} onClick={() => setMobileOpen(false)} className={cn("flex items-center gap-3 rounded-xl px-3 py-3.5 text-sm font-bold transition", active ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300" : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-900")}><span className={cn("flex h-9 w-9 items-center justify-center rounded-lg", active ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-500 dark:bg-slate-900")}><Icon className="h-4 w-4" /></span>{item.name}</Link>; })}</nav><div className="border-t border-slate-100 p-4 dark:border-slate-800"><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><p className="text-xs font-bold text-slate-700 dark:text-slate-200">{ORGANIZATION_NAME}</p><p className="mt-0.5 text-[11px] text-slate-400">{user?.full_name ?? "משתמש"}</p></div></div></aside></div>}
    </>
  );
}
