"use client";

import { ArrowDownAZ, ArrowUpAZ } from "lucide-react";
import type { ProductSortDirection } from "@/lib/product-sorting";

export function ProductSortToggle({ direction, onToggle, className = "" }: { direction: ProductSortDirection; onToggle: () => void; className?: string }) {
  const ascending = direction === "asc";
  return <button type="button" onClick={onToggle} aria-label={ascending ? "מיון מוצרים בסדר יורד" : "מיון מוצרים בסדר עולה"} title={ascending ? "מיון א׳–ת׳ (לחץ לשינוי לת׳–א׳)" : "מיון ת׳–א׳ (לחץ לשינוי לא׳–ת׳)"} className={`inline-flex min-h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 transition hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 ${className}`}>
    {ascending ? <ArrowDownAZ size={16} aria-hidden="true" /> : <ArrowUpAZ size={16} aria-hidden="true" />}
    {ascending ? "סדר א׳–ת׳" : "סדר ת׳–א׳"}
  </button>;
}
