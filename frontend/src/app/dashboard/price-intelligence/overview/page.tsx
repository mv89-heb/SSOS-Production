"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Award, BarChart3, Search, TrendingDown } from "lucide-react";
import { apiClient } from "@/services/api-client";

const money = (value: number | null | undefined, currency = "ILS") =>
  value == null ? "—" : new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);

type Row = {
  product_id: number;
  product_name: string;
  category: string | null;
  sku: string | null;
  current_supplier: string | null;
  current_price: number | null;
  currency: string;
  comparison_unit: string | null;
  best_supplier: string | null;
  best_price: number | null;
  savings_per_unit: number;
  savings_percent: number;
  supplier_count: number;
  offers: Array<{ supplier_id: number; supplier_name: string | null; price: number; currency: string; unit: string | null; primary: boolean }>;
};

type Overview = {
  summary: any;
  supplier_scores: {
    products_analyzed: number;
    suppliers: Array<{
      supplier_id: number;
      supplier_name: string | null;
      participation: number;
      wins: number;
      coverage_percent: number;
      win_rate_percent: number;
      score: number;
    }>;
  };
  products: Row[];
  returned: number;
};

export default function SupplierOverviewPage() {
  const [search, setSearch] = useState("");
  const [opportunities, setOpportunities] = useState(false);
  const deferredSearch = useDeferredValue(search);

  const query = useQuery({
    queryKey: ["supplier-overview", deferredSearch, opportunities],
    queryFn: async () =>
      (
        await apiClient.get<Overview>("/api/price-intelligence/overview", {
          params: { limit: 300, search: deferredSearch, opportunities },
        })
      ).data,
    staleTime: 30000,
  });

  const data = query.data;
  const rows = data?.products ?? [];
  const suppliers = useMemo(() => data?.supplier_scores?.suppliers ?? [], [data]);

  return (
    <div dir="rtl" className="space-y-5 pb-12">
      <header className="rounded-3xl bg-gradient-to-l from-violet-700 via-indigo-700 to-blue-600 p-6 text-white shadow-sm sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-bold text-indigo-100">
              <BarChart3 size={18} /> רכש והשוואת ספקים
            </div>
            <h1 className="mt-2 text-3xl font-black sm:text-4xl">תמונת מצב של המחירים</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-indigo-100">
              חיפוש לפי מוצר, מק״ט, ברקוד, קטגוריה או ספק — והצגת המחירים והחלופות הרלוונטיות.
            </p>
          </div>
          <Link
            href="/dashboard/price-intelligence"
            className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 font-black text-indigo-700"
          >
            ניתוח מוצר מפורט <ArrowLeft size={17} />
          </Link>
        </div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[
          ["מוצרים שנבדקו", data?.summary?.products_analyzed ?? 0],
          ["עם חלופה להשוואה", data?.summary?.products_with_comparable_alternatives ?? 0],
          ["הזדמנויות חיסכון", data?.summary?.opportunity_products ?? 0],
          ["חיסכון פוטנציאלי", money(data?.summary?.potential_savings)],
          ["אחוז חיסכון", Number(data?.summary?.potential_savings_percent ?? 0).toFixed(1) + "%"],
        ].map(([label, value]) => (
          <div
            key={String(label)}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"
          >
            <div className="text-xs font-bold text-slate-500">{label}</div>
            <div className="mt-2 text-2xl font-black">{value}</div>
          </div>
        ))}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-3 lg:flex-row">
          <label className="relative flex-1">
            <Search className="absolute right-3 top-3.5 text-slate-400" size={18} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="חפש מוצר, מק״ט, ברקוד, קטגוריה או ספק..."
              aria-label="חיפוש בשולחן השוואת ספקים"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pr-10 pl-3 outline-none focus:border-violet-500 dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
          <button
            onClick={() => setOpportunities((v) => !v)}
            className={
              "rounded-xl px-5 py-3 text-sm font-black " +
              (opportunities
                ? "bg-emerald-600 text-white"
                : "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300")
            }
          >
            <TrendingDown className="ml-1 inline" size={16} /> רק מוצרים עם חיסכון
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
          <span>
            {search !== deferredSearch ? "מעדכן תוצאות..." : query.isFetching ? "מרענן תוצאות..." : "החיפוש כולל את כל שדות המוצר והספק"}
          </span>
          <span>{data?.returned ?? 0} תוצאות</span>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_330px]">
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex items-center justify-between border-b border-slate-200 p-5 dark:border-slate-800">
            <div>
              <h2 className="text-xl font-black">השוואת מחירים לפי מוצר</h2>
              <p className="mt-1 text-xs text-slate-500">
                המחיר הזול ביותר מודגש. ניתן לפתוח ניתוח מלא של כל מוצר.
              </p>
            </div>
            <span className="text-xs font-bold text-slate-400">{data?.returned ?? 0} שורות</span>
          </div>

          {query.isLoading ? (
            <div className="p-10 text-center text-sm text-slate-500">מחשב השוואת ספקים...</div>
          ) : query.isError ? (
            <div className="m-5 rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
              לא ניתן לבצע את החיפוש כרגע. נסה שוב בעוד רגע.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1120px] text-right text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900">
                  <tr>
                    <th className="px-4 py-3">מוצר</th>
                    <th className="px-4 py-3">קטגוריה</th>
                    <th className="px-4 py-3">ספק נוכחי</th>
                    <th className="px-4 py-3">מחיר נוכחי</th>
                    <th className="px-4 py-3">ספק זול ביותר</th>
                    <th className="px-4 py-3">מחיר זול ביותר</th>
                    <th className="px-4 py-3">חיסכון</th>
                    <th className="px-4 py-3">מס׳ ספקים</th>
                    <th className="px-4 py-3">פעולה</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {rows.map((row) => (
                    <tr key={row.product_id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50">
                      <td className="px-4 py-4">
                        <Link href={"/dashboard/price-intelligence?product=" + row.product_id} className="font-black hover:text-violet-600">
                          {row.product_name}
                        </Link>
                        <span className="mt-1 block text-xs text-slate-400">
                          {row.sku || "ללא מק״ט"} · {row.comparison_unit || "יחידה"}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-xs text-slate-500">{row.category || "—"}</td>
                      <td className="px-4 py-4">{row.current_supplier || "—"}</td>
                      <td className="px-4 py-4 font-bold">{money(row.current_price, row.currency)}</td>
                      <td className="px-4 py-4 font-bold text-emerald-700">{row.best_supplier || "—"}</td>
                      <td className="px-4 py-4 font-black text-emerald-700">{money(row.best_price, row.currency)}</td>
                      <td className="px-4 py-4">
                        {row.savings_per_unit > 0 ? (
                          <>
                            <strong className="text-emerald-700">{money(row.savings_per_unit, row.currency)}</strong>
                            <span className="mr-1 text-xs text-emerald-600">({row.savings_percent}%)</span>
                          </>
                        ) : (
                          <span className="text-slate-400">אין</span>
                        )}
                      </td>
                      <td className="px-4 py-4">{row.supplier_count}</td>
                      <td className="px-4 py-4">
                        <Link
                          href={"/dashboard/price-intelligence?product=" + row.product_id}
                          className="rounded-lg bg-violet-50 px-3 py-2 text-xs font-black text-violet-700"
                        >
                          פתח
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rows.length && !query.isLoading && (
                <div className="p-10 text-center text-sm text-slate-500">
                  לא נמצאו מוצרים מתאימים לחיפוש.
                </div>
              )}
            </div>
          )}
        </section>

        <aside className="space-y-5">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex items-center gap-2">
              <Award className="text-violet-600" size={19} />
              <h2 className="font-black">תמונת ספקים</h2>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              כיסוי והופעות במחיר הנמוך ביותר, מתוך מוצרים שיש להם לפחות שתי הצעות.
            </p>
            <div className="mt-4 space-y-3">
              {suppliers.map((s) => (
                <div key={s.supplier_id} className="rounded-2xl bg-slate-50 p-3 dark:bg-slate-900">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-black">{s.supplier_name || "ספק #" + s.supplier_id}</span>
                    <span className="text-xs font-bold text-violet-600">{s.score}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-slate-400">כיסוי</span>
                      <strong className="block">{s.coverage_percent}%</strong>
                    </div>
                    <div>
                      <span className="text-slate-400">מחיר נמוך ביותר</span>
                      <strong className="block">{s.win_rate_percent}%</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950/20">
            <div className="text-xs font-bold text-emerald-700">מה חשוב כאן?</div>
            <p className="mt-2 text-sm leading-6 text-emerald-900 dark:text-emerald-100">
              ההשוואה נעשית רק כשמטבע ויחידת ההשוואה תואמים. חיפוש לפי ספק מוצא גם מוצרים שבהם הספק הוא הספק הראשי וגם מוצרים שבהם קיימת לספק הצעה חלופית.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
