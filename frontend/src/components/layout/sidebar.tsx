"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Package,
  ShoppingCart,
  Settings,
  History
} from "lucide-react";

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

  return (
    <aside className="hidden md:flex w-64 flex-col bg-white dark:bg-slate-950 border-e border-slate-200 dark:border-slate-800 h-screen sticky top-0">
      <div className="h-16 flex items-center px-6 border-b border-slate-200 dark:border-slate-800">
        <span className="text-lg font-bold text-slate-900 dark:text-white">SSOS Platform</span>
      </div>

      <nav className="flex-1 space-y-1 px-4 py-4 overflow-y-auto">
        {navigation.map((item) => {
          const isActive = pathname.endsWith(item.href) || pathname.includes(`${item.href}/`);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-md transition-colors",
                isActive
                  ? "bg-slate-950 text-white dark:bg-slate-800"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-900 dark:hover:text-white"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
