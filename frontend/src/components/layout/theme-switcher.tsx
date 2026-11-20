"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "@/providers/theme-provider";

interface ThemeSwitcherProps {
  compact?: boolean;
}

export default function ThemeSwitcher({ compact = false }: ThemeSwitcherProps) {
  const { mode, setMode, resolvedTheme } = useTheme();
  const Icon = mode === "system" ? Monitor : resolvedTheme === "dark" ? Moon : Sun;

  return (
    <label className={compact ? "inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white/90 px-2.5 py-2 text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200" : "inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-2.5 text-slate-600 transition hover:border-teal-300 hover:text-teal-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-teal-800 dark:hover:text-teal-300"}>
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="sr-only">ערכת נושא</span>
      <select
        aria-label="בחירת ערכת נושא"
        value={mode}
        onChange={(event) => setMode(event.target.value as "light" | "dark" | "system")}
        className="max-w-[76px] sm:max-w-[112px] cursor-pointer bg-transparent text-xs font-bold outline-none"
      >
        <option value="light">מצב בהיר</option>
        <option value="dark">מצב כהה</option>
        <option value="system">לפי המכשיר</option>
      </select>
    </label>
  );
}
