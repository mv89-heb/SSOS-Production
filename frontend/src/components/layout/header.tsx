"use client";

import { useAuth } from "@/providers/auth-provider";
import { LogOut } from "lucide-react";

const ROLE_LABELS: Record<string, string> = {
  admin: "מנהל מערכת",
  manager: "מנהל",
  employee: "עובד",
};

export default function Header() {
  const { user, tenant, logout } = useAuth();

  return (
    <header className="h-16 bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 flex items-center px-6 justify-between">
      <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <span className="font-semibold">ארגון פעיל:</span>
        <span className="bg-slate-100 dark:bg-slate-900 px-2.5 py-1 rounded-md text-xs font-mono text-slate-800 dark:text-slate-200">
          {tenant?.name ?? "—"}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="text-end hidden sm:block">
            <div className="text-xs font-semibold">{user?.full_name ?? "—"}</div>
            <div className="text-[10px] text-slate-500">{user ? ROLE_LABELS[user.role] ?? user.role : "—"}</div>
          </div>
          <button
            onClick={() => logout()}
            className="p-1.5 rounded-full text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            title="התנתק מהמערכת"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
