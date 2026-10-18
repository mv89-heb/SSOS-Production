"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Award, BarChart3, Search, TrendingDown, Sparkles, ArrowUpDown, Download, ChevronDown, ChevronUp } from "lucide-react";
import { apiClient } from "@/services/api-client";

const money = (value: number | null | undefined, currency = "ILS") =>
  value == null ? "—" : new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);

type Row = {
  product_id: number;
  master_product_id?: number | null;
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
  const tableScrollRef = useRef<HTMLDivElement>(null);
  const [opportunities, setOpportunities] = useState(false);
  const [category, setCategory] = useState("all");
  const [sortBy, setSortBy] = useState<"savings" | "name" | "price" | "percent">("savings");
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
  // Strip common natural-language intent words before searching catalog fields.
  const searchTerm = useMemo(() => {
    const intentWords = new Set(["איפה", "כדאי", "לי", "בבקשה", "לקנות", "לרכוש", "מומלץ", "תראה", "הצג", "מצא", "חפש", "השווה", "השוואה", "המלץ", "המלצה", "הכי", "זול", "זולים", "זולות", "מחיר", "מחירים", "ספק", "ספקים", "לפי", "קטגוריה", "קטגוריית", "מוצר", "מוצרים", "מוצרי", "רכישה", "לרכישה", "מה", "של", "את", "עם", "בין", "בקטגוריה", "בקטגוריית"]);
    return search.replace(/[.,?!]/g, " ").split(/\s+/).filter((word) => word && !intentWords.has(word.toLowerCase())).join(" ").trim();
  }, [search]);
  const deferredSearch = useDeferredValue(searchTerm);

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
  const categories = useMemo(() => Array.from(new Set(rows.map((row) => row.category?.trim()).filter((value): value is string => Boolean(value)))).sort((a, b) => a.localeCompare(b, "he")), [rows]);
  const visibleRows = useMemo(() => {
    const filtered = rows.filter((row) => category === "all" || row.category === category);
    return [...filtered].sort((a, b) => {
      if (sortBy === "name") return a.product_name.localeCompare(b.product_name, "he");
      if (sortBy === "price") return (a.best_price ?? Number.POSITIVE_INFINITY) - (b.best_price ?? Number.POSITIVE_INFINITY);
      if (sortBy === "percent") return b.savings_percent - a.savings_percent;
      return b.savings_per_unit - a.savings_per_unit;
    });
  }, [rows, category, sortBy]);
  const suppliers = useMemo(() => data?.supplier_scores?.suppliers ?? [], [data]);
  const recommendedSupplier = useMemo(() => {
    const counts = new Map<string, { name: string; wins: number; savings: number }>();
    visibleRows.forEach((row) => {
      if (!row.best_supplier) return;
      const current = counts.get(row.best_supplier) ?? { name: row.best_supplier, wins: 0, savings: 0 };
      current.wins += 1;
      current.savings += Math.max(0, row.savings_per_unit);
      counts.set(row.best_supplier, current);
    });
    return [...counts.values()].sort((a, b) => b.wins - a.wins || b.savings - a.savings)[0] ?? null;
  }, [visibleRows]);
  const chartRows = [...visibleRows].filter((row) => row.savings_per_unit > 0).sort((a, b) => b.savings_per_unit - a.savings_per_unit).slice(0, 6);
  const maxSaving = Math.max(1, ...chartRows.map((row) => row.savings_per_unit));
  const rowKey = (row: Row) => `${row.product_id}::${row.currency}::${row.comparison_unit || "unit"}`;
  const quantityFor = (row: Row) => {
    const parsed = Number(quantities[rowKey(row)] ?? "1");
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  };
  const basketSavings = visibleRows.reduce((sum, row) => sum + (row.supplier_count >= 2 ? Math.max(0, row.savings_per_unit) * quantityFor(row) : 0), 0);
  const basketRowsWithQuantity = visibleRows.filter((row) => quantityFor(row) > 0);
  const splitSuppliers = new Set(basketRowsWithQuantity.map((row) => row.best_supplier).filter((name): name is string => Boolean(name)));
  const exportCsv = () => {
    const headers = ["מוצר", "קטגוריה", "יחידת השוואה", "מטבע", "ספק במחיר הגבוה", "מחיר גבוה", "ספק זול", "מחיר זול", "פער ליחידה", "כמות לתכנון", "חיסכון משוער לפי הכמות", "מספר ספקים"];
    const escapeCsv = (value: unknown) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const lines = visibleRows.map((row) => [
      row.product_name, row.category, row.comparison_unit, row.currency, row.current_supplier,
      row.current_price, row.best_supplier, row.best_price, row.savings_per_unit, quantityFor(row),
      row.supplier_count >= 2 ? row.savings_per_unit * quantityFor(row) : 0, row.supplier_count,
    ].map(escapeCsv).join(","));
    const csv = "\uFEFF" + [headers.map(escapeCsv).join(","), ...lines].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ssos-price-comparison.csv";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div dir="rtl" className="space-y-5 pb-12">
      <header className="rounded-3xl bg-gradient-to-l from-violet-700 via-indigo-700 to-blue-600 p-6 text-white shadow-sm sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-bold text-indigo-100">
              <BarChart3 size={18} /> רכש והשוואת ספקים
            </div>
            <h1 className="mt-2 text-3xl font-black sm:text-4xl">לוח השוואת ספקים וחיסכון</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-indigo-100">
              השוואה בין מחירים של אותו מוצר אצל ספקים שונים, עם פער המחיר ליחידת השוואה והספק הזול ביותר.
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

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {[
          ["מוצרים / קבוצות מחיר", data?.summary?.products_analyzed ?? 0],
          ["עם חלופות תואמות", data?.summary?.products_with_comparable_alternatives ?? 0],
          ["הזדמנויות חיסכון", data?.summary?.opportunity_products ?? 0],
          ["סכום פערים ליחידה", money(data?.summary?.potential_savings)],
          ["חיסכון משוער לפי הכמויות", money(basketSavings)],
          ["ספקים בסל מפוצל", splitSuppliers.size],
        ].map(([label, value]) => (
          <div
            key={String(label)}
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950"
          >
            <div className="text-xs font-bold text-slate-500">{label}</div>
            <div className="mt-2 text-xl font-black">{value}</div>
          </div>
        ))}
      </section>
      <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
        חשוב: "סכום פערים ליחידה" הוא סכום פערי המחיר ליחידה בין ההצעה הגבוהה לנמוכה בכל קבוצת השוואה — לא חיסכון כולל בפועל. אומדן הכמויות מחושב לפי הכמויות שהזנת לכל שורה; הוא עדיין אינו כולל משלוח, מינימום הזמנה, זמינות או תנאי תשלום.
      </p>

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
          <label className="flex min-w-48 items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-700">
            <span className="shrink-0 text-xs font-bold text-slate-500">קטגוריה</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="סינון לפי קטגוריה" className="min-w-0 flex-1 bg-transparent py-1 text-sm outline-none">
              <option value="all">כל הקטגוריות</option>
              {categories.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="flex min-w-48 items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-700">
            <ArrowUpDown size={16} className="text-slate-400" />
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)} aria-label="מיון תוצאות" className="min-w-0 flex-1 bg-transparent py-1 text-sm outline-none">
              <option value="savings">מיון לפי פער חיסכון</option>
              <option value="percent">מיון לפי אחוז חיסכון</option>
              <option value="price">מיון לפי המחיר הנמוך</option>
              <option value="name">מיון לפי שם מוצר</option>
            </select>
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
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs leading-5 text-slate-500">אפשר להזין כמות לכל מוצר, לפתוח את כל הצעות הספקים ולייצא את התוצאות לאחר הסינון.</div>
          <button type="button" onClick={exportCsv} disabled={!visibleRows.length} className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-black text-emerald-800 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
            <Download size={16} /> ייצוא CSV לפי הסינון
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
          <span>
            {search !== deferredSearch ? "מעדכן תוצאות..." : query.isFetching ? "מרענן תוצאות..." : "החיפוש כולל את כל שדות המוצר והספק"}
          </span>
          <span>{visibleRows.length} תוצאות לאחר סינון</span>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-3xl border border-violet-200 bg-white p-5 shadow-sm dark:border-violet-900 dark:bg-slate-950">
          <div className="flex items-center gap-2"><Sparkles size={19} className="text-violet-600" /><h2 className="font-black">ספקים עם הכי הרבה זכיות במחיר נמוך</h2></div>
          {recommendedSupplier ? <>
            <div className="mt-3 text-xl font-black text-violet-700 dark:text-violet-300">{recommendedSupplier.name}</div>
            <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
              הספק מופיע כהצעה הזולה ביותר ב-{recommendedSupplier.wins} מתוך {visibleRows.length} המוצרים המסוננים.
              זו המלצה לפי מספר זכיות במחיר הנמוך, ולא לפי סל משוקלל בכמויות או עלויות משלוח.
            </p>
            <div className="mt-3 text-xs text-slate-500">סכום פערי המחיר ליחידה במוצרים הרלוונטיים: {money(recommendedSupplier.savings)}</div>
          </> : <p className="mt-3 text-sm text-slate-500">אין מספיק הצעות תואמות כדי להמליץ על ספק. נסה להסיר סינון או להשלים הצעות מחיר.</p>}
        </div>
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex items-center gap-2"><BarChart3 size={19} className="text-indigo-600" /><h2 className="font-black">פערי החיסכון הבולטים</h2></div>
          {chartRows.length ? <div className="mt-4 space-y-3">
            {chartRows.map((row) => <div key={row.product_id}>
              <div className="mb-1 flex items-center justify-between gap-3 text-xs"><span className="truncate font-bold">{row.product_name}</span><span className="shrink-0 font-black text-emerald-700">{money(row.savings_per_unit, row.currency)}</span></div>
              <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-emerald-500" style={{ width: String(Math.min(100, Math.max(0, row.savings_per_unit / maxSaving * 100))) + "%" }} /></div>
              <div className="mt-1 text-[11px] text-slate-400">{row.best_supplier ? "הספק הזול: " + row.best_supplier : "אין ספק מומלץ"}</div>
            </div>)}
          </div> : <p className="mt-3 text-sm text-slate-500">לא נמצאו פערי מחיר חיוביים בתוצאות המסוננות.</p>}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_330px]">
        <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex items-center justify-between border-b border-slate-200 p-5 dark:border-slate-800">
            <div>
              <h2 className="text-xl font-black">השוואת מחירים לפי מוצר</h2>
              <p className="mt-1 text-xs text-slate-500">
                הפער מוצג רק בין הצעות מאושרות באותו מטבע ובאותה יחידת השוואה. במוצרי קטלוג אחיד, המחיר הגבוה משמש בסיס להצגת פער המחיר.
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
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                <span>ניתן לגלול אופקית כדי לראות את כל העמודות</span>
                <div className="flex shrink-0 gap-2">
                  <button type="button" onClick={() => tableScrollRef.current?.scrollBy({ left: -480, behavior: "smooth" })} className="rounded-lg border border-slate-300 px-3 py-1.5 font-bold hover:bg-white dark:border-slate-700 dark:hover:bg-slate-800" aria-label="גלילה שמאלה">← שמאלה</button>
                  <button type="button" onClick={() => tableScrollRef.current?.scrollBy({ left: 480, behavior: "smooth" })} className="rounded-lg border border-slate-300 px-3 py-1.5 font-bold hover:bg-white dark:border-slate-700 dark:hover:bg-slate-800" aria-label="גלילה ימינה">ימינה →</button>
                </div>
              </div>
              <div ref={tableScrollRef} dir="ltr" tabIndex={0} aria-label="טבלת השוואת מחירים, גלילה אופקית" className="overflow-x-auto overscroll-x-contain" style={{ scrollbarGutter: "stable", WebkitOverflowScrolling: "touch" }}>
              <table dir="rtl" className="w-full min-w-[1450px] text-right text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900">
                  <tr>
                    <th className="px-4 py-3">מוצר</th>
                    <th className="px-4 py-3">קטגוריה</th>
                    <th className="px-4 py-3">הספק היקר בקבוצה</th>
                    <th className="px-4 py-3">המחיר הגבוה בקבוצה</th>
                    <th className="px-4 py-3">ספק זול ביותר</th>
                    <th className="px-4 py-3">מחיר זול ביותר</th>
                    <th className="px-4 py-3">פער ליחידה</th>
                    <th className="px-4 py-3">כמות לתכנון</th>
                    <th className="px-4 py-3">חיסכון משוער</th>
                    <th className="px-4 py-3">ספקים</th>
                    <th className="px-4 py-3">הצעות</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {visibleRows.map((row) => (
                    <tr key={row.product_id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50">
                      <td className="px-4 py-4">
                        <Link href={row.master_product_id ? "/dashboard/catalog/master-products" : "/dashboard/price-intelligence?product=" + row.product_id} className="font-black hover:text-violet-600">
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
                      <td className="px-4 py-4">
                        <input
                          type="number"
                          min="0"
                          step="any"
                          inputMode="decimal"
                          aria-label={`כמות לתכנון עבור ${row.product_name}`}
                          value={quantities[rowKey(row)] ?? "1"}
                          onChange={(event) => setQuantities((previous) => ({ ...previous, [rowKey(row)]: event.target.value }))}
                          className="w-24 rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm font-bold outline-none focus:border-violet-500 dark:border-slate-700 dark:bg-slate-900"
                        />
                        <div className="mt-1 text-[10px] text-slate-400">{row.comparison_unit || "יחידה"}</div>
                      </td>
                      <td className="px-4 py-4">
                        {row.supplier_count >= 2 && quantityFor(row) > 0
                          ? <><strong className="text-emerald-700">{money(row.savings_per_unit * quantityFor(row), row.currency)}</strong><span className="mt-1 block text-[10px] text-slate-400">אומדן לפי הכמות</span></>
                          : <span className="text-slate-400">—</span>}
                      </td>
                      <td className="px-4 py-4">{row.supplier_count}</td>
                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button type="button" onClick={() => setExpandedRows((previous) => ({ ...previous, [rowKey(row)]: !previous[rowKey(row)] }))} className="inline-flex items-center gap-1 rounded-lg bg-violet-50 px-3 py-2 text-xs font-black text-violet-700 dark:bg-violet-950/40 dark:text-violet-200">
                            {expandedRows[rowKey(row)] ? <ChevronUp size={14} /> : <ChevronDown size={14} />} {expandedRows[rowKey(row)] ? "הסתר" : "כל ההצעות"}
                          </button>
                          <Link href={row.master_product_id ? "/dashboard/catalog/master-products" : "/dashboard/price-intelligence?product=" + row.product_id} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-black dark:border-slate-700">
                            פתח
                          </Link>
                        </div>
                      </td>
                    </tr>
                    {expandedRows[rowKey(row)] && (
                      <tr className="bg-violet-50/60 dark:bg-violet-950/20">
                        <td colSpan={12} className="px-4 py-4">
                          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                            <div className="font-black">כל הצעות המחיר — {row.product_name}</div>
                            <div className="text-xs text-slate-500">השוואה: {row.comparison_unit || "יחידה"} · {row.currency}</div>
                          </div>
                          {row.offers?.length ? (
                            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                              {[...row.offers].sort((a, b) => a.price - b.price).map((offer, index) => (
                                <div key={`${offer.supplier_id}::${offer.currency}::${offer.unit}`} className={`rounded-xl border p-3 ${index === 0 ? "border-emerald-300 bg-white dark:border-emerald-800 dark:bg-slate-950" : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"}`}>
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="font-bold">{offer.supplier_name || `ספק #${offer.supplier_id}`}</div>
                                    {index === 0 && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-black text-emerald-800">הזול ביותר</span>}
                                  </div>
                                  <div className="mt-2 text-xl font-black">{money(offer.price, offer.currency)}</div>
                                  <div className="mt-1 text-xs text-slate-500">לפי {offer.unit || row.comparison_unit || "יחידה"}</div>
                                </div>
                              ))}
                            </div>
                          ) : <p className="text-sm text-slate-500">אין פירוט הצעות זמין לשורה זו.</p>}
                        </td>
                      </tr>
                    )}
                  ))}
                </tbody>
              </table>
              {!visibleRows.length && !query.isLoading && (
                <div className="p-10 text-center text-sm text-slate-500">
                  לא נמצאו מחירים תואמים להשוואה. ודא שמוצרי הספקים משויכים לאותו מוצר בקטלוג האחיד.
                </div>
              )}
              </div>
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
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800" aria-label={`שיעור זכייה במחיר הנמוך: ${s.win_rate_percent}%`}>
                    <div className="h-full rounded-full bg-violet-500" style={{ width: String(Math.min(100, Math.max(0, s.win_rate_percent))) + "%" }} />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950/20">
            <div className="text-xs font-bold text-emerald-700">מה חשוב כאן?</div>
            <p className="mt-2 text-sm leading-6 text-emerald-900 dark:text-emerald-100">
              ההשוואה נשענת על מוצרים ששויכו ואושרו בקטלוג האחיד. היא מציגה פער בין המחיר הגבוה לנמוך באותו מטבע ובאותה יחידת השוואה; פער ליחידה אינו תחזית לחיסכון כולל ללא כמויות רכש.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
