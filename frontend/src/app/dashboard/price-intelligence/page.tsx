"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Award, ArrowDown, ArrowUp, CheckCircle2, RefreshCw, Search, Sparkles } from "lucide-react";

import { useProducts } from "@/hooks/use-catalog";
import { priceIntelligenceService } from "@/services/price-intelligence-service";
import type { Product } from "@/types";

const money = (value: number, currency = "ILS") => {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
};

export default function PriceIntelligencePage() {
  const { data: products = [], isLoading: productsLoading, isError: productsError } = useProducts();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState("100");

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return products.filter((p) =>
      !term || p.name.toLowerCase().includes(term) || String(p.sku ?? "").toLowerCase().includes(term),
    );
  }, [products, search]);

  const selected: Product | null = products.find((p) => p.id === selectedId) ?? filtered[0] ?? null;
  const comparison = useQuery({
    queryKey: ["price-intelligence", "comparison", selected?.id],
    queryFn: () => priceIntelligenceService.compareProduct(selected!.id),
    enabled: Boolean(selected?.id),
    retry: 1,
  });
  const numericQuantity = Number(quantity);
  const savings = useQuery({
    queryKey: ["price-intelligence", "savings", selected?.id, quantity],
    queryFn: () => priceIntelligenceService.calculateSavings(selected!.id, numericQuantity),
    enabled: Boolean(selected?.id) && Number.isFinite(numericQuantity) && numericQuantity > 0 && Boolean(comparison.data),
    retry: 1,
  });

  const data = comparison.data;
  const current = data?.current;
  const best = data?.best_offer;
  const errorMessage = comparison.error instanceof Error ? comparison.error.message : "לא ניתן לטעון את השוואת הספקים.";
  const savingsError = savings.error instanceof Error ? savings.error.message : "לא ניתן לחשב את החיסכון.";

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-600"><Sparkles size={18} /><span className="text-sm font-semibold">Price Intelligence</span></div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white">השוואת ספקים</h1>
            <p className="mt-1 text-sm text-slate-500">השווה מחירים אמיתיים בין ספקים, כולל יחידת השוואה, מטבע וחיסכון לפי הכמות שאתה קונה.</p>
          </div>
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חפש מוצר או מק״ט..." className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pr-10 pl-3 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-white" />
          </div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-slate-900 dark:text-white">מוצרים</h2><span className="text-xs text-slate-400">{filtered.length}</span></div>
          <div className="max-h-[620px] space-y-1 overflow-auto">
            {productsLoading && <p className="p-3 text-sm text-slate-400">טוען מוצרים...</p>}
            {productsError && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">לא ניתן לטעון את הקטלוג.</p>}
            {!productsLoading && !productsError && filtered.length === 0 && <p className="p-3 text-sm text-slate-400">לא נמצאו מוצרים.</p>}
            {filtered.map((product) => (
              <button key={product.id} type="button" onClick={() => setSelectedId(product.id)} className={`w-full rounded-xl p-3 text-right transition ${selected?.id === product.id ? "bg-indigo-50 ring-1 ring-indigo-200 dark:bg-indigo-950/40" : "hover:bg-slate-50 dark:hover:bg-slate-900"}`}>
                <div className="font-medium text-slate-900 dark:text-white">{product.name}</div>
                <div className="mt-1 flex justify-between text-xs text-slate-500"><span>{product.sku || "ללא מק״ט"}</span><span>{money(product.current_price, product.currency)}</span></div>
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          {!selected && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-slate-500">בחר מוצר כדי לראות השוואת ספקים.</div>}
          {selected && (
            <>
              {comparison.isError && (
                <div className="flex items-start justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800 dark:border-red-900 dark:bg-red-950/20 dark:text-red-200">
                  <div><div className="font-semibold">השוואת הספקים נכשלה</div><div className="mt-1 text-sm">{errorMessage}</div></div>
                  <button type="button" onClick={() => comparison.refetch()} className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow-sm"><RefreshCw size={15} />נסה שוב</button>
                </div>
              )}

              {data && (
                <>
                  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><h2 className="text-xl font-bold">{selected.name}</h2><p className="text-sm text-slate-500">מק״ט: {selected.sku || "ללא מק״ט"}</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">יחידת השוואה: {current?.comparison_unit || selected.unit || "יחידה"}</span></div>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950"><div className="text-sm text-slate-500">מחיר נוכחי</div><div className="mt-2 text-2xl font-bold">{current ? money(current.normalized_price, current.currency) : "אין מחיר בסיס"}</div><div className="mt-1 text-xs text-slate-400">{current?.supplier_name || "ספק ראשי לא זמין"}</div></div>
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950/20"><div className="text-sm text-emerald-700">המחיר הטוב ביותר</div><div className="mt-2 text-2xl font-bold text-emerald-700">{best ? money(best.normalized_price, best.currency) : "אין הצעה מתאימה"}</div><div className="mt-1 text-xs text-emerald-700/70">{best?.supplier_name || "—"}</div></div>
                    <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5 dark:border-indigo-900 dark:bg-indigo-950/20"><div className="text-sm text-indigo-700">חיסכון ליחידה</div><div className="mt-2 text-2xl font-bold text-indigo-700">{current && best ? money(data.saving_per_unit, current.currency) : "—"}</div><div className="mt-1 text-xs text-indigo-700/70">{data.saving_percent.toFixed(2)}% מול המחיר הנוכחי</div></div>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
                    <div className="flex items-center justify-between border-b border-slate-100 p-5 dark:border-slate-800"><div><h2 className="font-semibold">השוואת ספקים</h2><p className="text-xs text-slate-500">רק הצעות עם מטבע ויחידת השוואה תואמים מדורגות.</p></div><Award className="text-amber-500" size={20} /></div>
                    {comparison.isLoading && <p className="p-5 text-sm text-slate-400">מחשב...</p>}
                    {!comparison.isLoading && data.offers.length === 0 && <div className="p-6 text-center text-sm text-slate-500">אין כרגע הצעות שניתן להשוות למוצר הזה.</div>}
                    {data.offers.length > 0 && <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.offers.map((offer) => <div key={`${offer.supplier_id}-${offer.primary}`} className="grid grid-cols-[1fr_auto_auto] items-center gap-4 p-4"><div><div className="font-medium">{offer.supplier_name || `#${offer.supplier_id}`} {offer.primary && <span className="mr-2 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">ספק ראשי</span>}</div><div className="text-xs text-slate-400">{offer.comparison_unit || offer.unit || "יחידה"} · {offer.currency}</div></div><div className="font-semibold">{money(offer.normalized_price, offer.currency)}</div><div className={offer === best ? "text-sm font-semibold text-emerald-600" : "text-sm text-slate-400"}>{offer === best ? "הזול ביותר" : ""}</div></div>)}</div>}
                  </div>

                  {data.incomparable_offers.length > 0 && (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20">
                      <div className="flex items-start gap-3 border-b border-amber-200 p-5 dark:border-amber-900"><AlertTriangle className="mt-0.5 text-amber-600" size={20} /><div><h2 className="font-semibold text-amber-900 dark:text-amber-200">הצעות שלא נכנסו לדירוג</h2><p className="mt-1 text-xs text-amber-800/80 dark:text-amber-200/70">הן לא מוסתרות: הסיבה מוצגת כדי שתוכל לתקן את נתוני המחיר או היחידה.</p></div></div>
                      <div className="divide-y divide-amber-200/70 dark:divide-amber-900">{data.incomparable_offers.map((offer) => <div key={`incomparable-${offer.supplier_id}`} className="flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="font-medium text-amber-950 dark:text-amber-100">{offer.supplier_name || `#${offer.supplier_id}`}</div><div className="text-sm text-amber-900/80 dark:text-amber-200/80">{money(offer.normalized_price, offer.currency)} · {offer.incomparable_reason || "נתונים לא תואמים"}</div></div>)}</div>
                    </div>
                  )}

                  <div className="rounded-2xl border border-indigo-200 bg-indigo-50/60 p-5 dark:border-indigo-900 dark:bg-indigo-950/20">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="font-semibold">כמה באמת אפשר לחסוך?</h2><p className="mt-1 text-sm text-slate-500">הכמות מחושבת לפי יחידת ההשוואה שמוצגת למעלה.</p></div><label className="text-sm"><span className="mb-1 block text-slate-500">כמות</span><input type="number" min="1" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="w-32 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label></div>
                    {!Number.isFinite(numericQuantity) || numericQuantity <= 0 ? <p className="mt-4 text-sm text-amber-700">הזן כמות גדולה מאפס.</p> : null}
                    {savings.isError && <p className="mt-4 text-sm text-red-700">{savingsError}</p>}
                    {savings.data && current && best && <div className="mt-5 grid gap-4 sm:grid-cols-3"><div><div className="text-xs text-slate-500">עלות נוכחית</div><div className="text-xl font-bold">{money(savings.data.current_cost, current.currency)}</div></div><div><div className="text-xs text-slate-500">עלות במחיר הטוב ביותר</div><div className="text-xl font-bold">{money(savings.data.best_cost, best.currency)}</div></div><div><div className="text-xs text-emerald-700">חיסכון</div><div className="flex items-center gap-1 text-xl font-bold text-emerald-700">{savings.data.savings > 0 ? <ArrowDown size={18} /> : <ArrowUp size={18} />}{money(savings.data.savings, current.currency)} ({savings.data.savings_percent.toFixed(2)}%)</div></div></div>}
                    {savings.data?.best_supplier_name && <div className="mt-4 flex items-center gap-2 text-sm font-semibold text-emerald-700"><CheckCircle2 size={16} />הספק המומלץ לכמות הזו: {savings.data.best_supplier_name}</div>}
                  </div>
                </>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
