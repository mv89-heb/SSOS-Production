"use client";

import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { Globe, LogOut } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";

export default function Header() {
  const t = useTranslations("header");
  const locale = useLocale();
  const router = useRouter();
  const { user, tenant, logout } = useAuth();

  const toggleLanguage = () => {
    const nextLocale = locale === "he" ? "en" : "he";
    // ה-layout הראשי קורא את השפה מהעוגייה NEXT_LOCALE (force-dynamic),
    // כך שרענון רך של ה-router מספיק כדי להחליף שפה וכיוון (RTL/LTR)
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  };

  const roleLabel: Record<string, string> = {
    admin: t("roles.admin"),
    manager: t("roles.manager"),
    employee: t("roles.employee"),
  };

  return (
    <header className="h-16 bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 flex items-center px-6 justify-between">
      <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
        <span className="font-semibold">{t("tenant")}:</span>
        <span className="bg-slate-100 dark:bg-slate-900 px-2.5 py-1 rounded-md text-xs font-mono text-slate-800 dark:text-slate-200">
          {tenant?.name ?? "—"}
        </span>
      </div>

      <div className="flex items-center gap-4">
        {/* כפתור החלפת שפה גלובלי */}
        <button
          onClick={toggleLanguage}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors text-slate-700 dark:text-slate-300"
        >
          <Globe className="h-3.5 w-3.5" />
          <span>{locale === "he" ? "English" : "עברית"}</span>
        </button>

        <div className="flex items-center gap-3">
          <div className="text-end hidden sm:block">
            <div className="text-xs font-semibold">{user?.full_name ?? ""}</div>
            <div className="text-[10px] text-slate-500">
              {user ? roleLabel[user.role] ?? user.role : ""}
            </div>
          </div>
          <button
            onClick={logout}
            className="p-1.5 rounded-full text-slate-500 hover:text-slate-800 hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors"
            title={t("logout")}
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
