"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Command, Search, X, LayoutDashboard, Package, ShoppingCart, Users, History, Settings, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const ACTIONS = [
  { label: "לוח בקרה", href: "/dashboard", icon: LayoutDashboard, keywords: "dashboard בית ראשי" },
  { label: "קטלוג מוצרים", href: "/dashboard/catalog", icon: Package, keywords: "מוצר קטלוג inventory" },
  { label: "הזמנות רכש", href: "/dashboard/orders", icon: ShoppingCart, keywords: "הזמנה purchase order" },
  { label: "ספקים", href: "/dashboard/suppliers", icon: Users, keywords: "supplier" },
  { label: "לוג ביקורת", href: "/dashboard/audit", icon: History, keywords: "audit history" },
  { label: "הגדרות", href: "/dashboard/settings", icon: Settings, keywords: "settings" },
  { label: "ייבוא מחירון", href: "/dashboard/import", icon: Upload, keywords: "import מחירון excel csv" },
] as const;

export default function CommandPalette() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return ACTIONS;
    return ACTIONS.filter((item) => `${item.label} ${item.keywords}`.toLowerCase().includes(normalized));
  }, [query]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setSelected(0);
  }, [open]);

  useEffect(() => {
    setSelected((current) => Math.min(current, Math.max(filtered.length - 1, 0)));
  }, [filtered.length]);

  const navigate = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelected((current) => Math.min(current + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelected((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" && filtered[selected]) {
      event.preventDefault();
      navigate(filtered[selected].href);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden h-9 min-w-56 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 text-right text-xs text-slate-400 shadow-sm transition hover:border-indigo-200 hover:bg-white hover:text-slate-600 md:flex dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800"
        aria-label="חיפוש מהיר"
      >
        <Search className="h-4 w-4" />
        <span className="flex-1">חיפוש מהיר או פעולה...</span>
        <kbd className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[10px] dark:border-slate-700 dark:bg-slate-950">Ctrl K</kbd>
      </button>

      {open && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center bg-slate-950/45 p-4 pt-[12vh] backdrop-blur-sm" onMouseDown={() => setOpen(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="חיפוש מהיר"
            className="w-full max-w-xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-slate-100 px-4 dark:border-slate-800">
              <Search className="h-5 w-5 text-slate-400" />
              <input
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="חפש מוצר, ספק, הזמנה או פעולה..."
                className="h-14 flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-white"
              />
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800" aria-label="סגירה">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[55vh] overflow-y-auto p-2">
              {filtered.length === 0 ? (
                <div className="px-4 py-10 text-center text-sm text-slate-400">לא נמצאו פעולות תואמות.</div>
              ) : (
                filtered.map((item, index) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.href}
                      type="button"
                      onMouseEnter={() => setSelected(index)}
                      onClick={() => navigate(item.href)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-right transition",
                        index === selected ? "bg-indigo-50 text-indigo-900 dark:bg-indigo-950/60 dark:text-indigo-200" : "text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800"
                      )}
                    >
                      <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg", index === selected ? "bg-indigo-100 text-indigo-600 dark:bg-indigo-900/70 dark:text-indigo-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800")}> 
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="flex-1 text-sm font-semibold">{item.label}</span>
                      {pathname === item.href && <span className="text-[10px] font-bold text-indigo-500">כאן</span>}
                      {index === selected && <kbd className="rounded border border-slate-200 px-1.5 py-0.5 text-[10px] text-slate-400 dark:border-slate-700">Enter</kbd>}
                    </button>
                  );
                })
              )}
            </div>
            <div className="flex items-center gap-4 border-t border-slate-100 px-4 py-2.5 text-[10px] text-slate-400 dark:border-slate-800">
              <span>↑↓ ניווט</span><span>Enter פתיחה</span><span>Esc סגירה</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
