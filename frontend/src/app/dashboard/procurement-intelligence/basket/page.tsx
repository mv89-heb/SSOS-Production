"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Calculator, Loader2, PackageSearch, Plus, Trash2 } from "lucide-react";

import { catalogService } from "@/services/catalog-service";
import { priceIntelligenceService } from "@/services/price-intelligence-service";

const money = (value: number, currency = "ILS") => {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value || 0));
  } catch {
    return `${Number(value || 0).toFixed(2)} ${currency}`;
  }
};

const number = (value: number) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(Number(value || 0));

type BasketItem = { product_id: number; quantity: number };

export default function ProcurementBasketPage() {
  const products = useQuery({
    queryKey: ["procurement-intelligence", "basket-products"],
    queryFn: () => catalogService.listProducts(undefined, true),
    retry: 1,
  });
  const [items, setItems] = useState<BasketItem[]>([]);
  const [maxSuppliers, setMaxSuppliers] = useState(2);
  const [result, setResult] = useState<Awaited<ReturnType<typeof priceIntelligenceService.optimizeBasket>> | null>(null);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  const catalog = products.data ?? [];
  const available = useMemo(() => catalog.filter((product) => !items.some((item) => item.product_id === product.id)), [catalog, items]);

  const addItem = () => {
    const product = available[0];
    if (!product) return;
    setItems((current) => [...current, { product_id: product.id, quantity: 1 }]);
    setResult(null);
  };

  const updateItem = (index: number, patch: Partial<BasketItem>) => {
    setItems((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
    setResult(null);
  };

  const removeItem = (index: number) => {
    setItems((current) => current.filter((_, itemIndex) => itemIndex !== index));
    setResult(null);
  };

  const analyze = async () => {
    if (!items.length) {
      setError("הוסף לפחות מוצר אחד לסל.");
      return;
    }
    if (items.some((item) => !Number.isInteger(item.product_id) || item.quantity <= 0)) {
      setError("לכל מוצר יש להגדיר כמות גדולה מאפס.");
      return;
    }
    setLoading(true);
    setError(undefined);
    try {
      setResult(await priceIntelligenceService.optimizeBasket(items, maxSuppliers));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "לא ניתן לנתח את סל הרכש כרגע.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <a href="/dashboard/procurement-intelligence" className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-600 hover:underline">
          <ArrowLeft size={16} /> חזרה למרכז מודיעין רכש
        </a>
        <div className="mt-5 flex items-start gap-3">
          <div className="rounded-xl bg-indigo-600 p-2 text-white"><Calculator size={20} /></div>
          <div>
            <h1 className="text-3xl font-black text-slate-900 dark:text-white">אופטימיזציית סל רכש</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
              בחר מוצרים וכמויות וקבל את חלוקת הספקים הזולה ביותר מתוך המחירים הקיימים במערכת. החישוב אינו כולל משלוח, MOQ או תנאי אשראי שלא קיימים בנתונים.
            </p>
          </div>
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 className="font-black">מוצרי הסל</h2><p className="mt-1 text-xs text-slate-500">המחירים נלקחים מהשוואת הספקים הקיימת.</p></div>
          <button type="button" onClick={addItem} disabled={!available.length || products.isLoading} className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-50"><Plus size={16} /> הוסף מוצר</button>
        </div>

        {products.isError ? <div className="p-8 text-center text-sm text-amber-700">לא ניתן לטעון את הקטלוג כרגע.</div> : !items.length ? <div className="p-10 text-center"><PackageSearch className="mx-auto text-slate-300" size={40} /><div className="mt-3 font-bold">הסל עדיין ריק</div><div className="mt-1 text-sm text-slate-500">הוסף מוצרים כדי לחשב חלוקת ספקים.</div></div> : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {items.map((item, index) => {
              const product = catalog.find((row) => row.id === item.product_id);
              return <div key={`${item.product_id}-${index}`} className="grid gap-3 p-5 md:grid-cols-[1fr_150px_auto] md:items-center">
                <select value={item.product_id} onChange={(event) => updateItem(index, { product_id: Number(event.target.value) })} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900">
                  {catalog.map((row) => <option key={row.id} value={row.id}>{row.name} — {money(row.current_price, row.currency || "ILS")}</option>)}
                </select>
                <input type="number" min="0.01" step="0.01" value={item.quantity} onChange={(event) => updateItem(index, { quantity: Number(event.target.value) })} className="rounded-xl border border-slate-200 px-3 py-2.5 text-sm dark:border-slate-700 dark:bg-slate-900" aria-label={`כמות ${product?.name || "מוצר"}`} />
                <button type="button" onClick={() => removeItem(index)} className="inline-flex items-center justify-center rounded-xl border border-red-200 p-2.5 text-red-600 hover:bg-red-50 dark:border-red-900"><Trash2 size={16} /></button>
              </div>;
            })}
          </div>
        )}

        <div className="flex flex-col gap-4 border-t border-slate-100 p-5 dark:border-slate-800 sm:flex-row sm:items-end sm:justify-between">
          <label className="text-sm font-semibold">מקסימום ספקים
            <input type="number" min="1" max="10" value={maxSuppliers} onChange={(event) => setMaxSuppliers(Math.max(1, Math.min(10, Number(event.target.value) || 1)))} className="mr-3 w-24 rounded-xl border border-slate-200 px-3 py-2 dark:border-slate-700 dark:bg-slate-900" />
          </label>
          <button type="button" onClick={analyze} disabled={loading || !items.length} className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-50">{loading && <Loader2 size={16} className="animate-spin" />} {loading ? "מחשב..." : "חשב סל אופטימלי"}</button>
        </div>
      </section>

      {error && <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">{error}</div>}

      {result && <section className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="text-sm text-slate-500">עלות נוכחית</div><div className="mt-2 text-2xl font-black">{money(result.current_cost)}</div></div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="text-sm text-slate-500">עלות אופטימלית</div><div className="mt-2 text-2xl font-black text-emerald-600">{money(result.optimized_cost)}</div></div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm dark:border-emerald-900 dark:bg-emerald-950/20"><div className="text-sm text-emerald-700">חיסכון פוטנציאלי</div><div className="mt-2 text-2xl font-black text-emerald-700">{money(result.savings)}</div></div>
          <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5 shadow-sm dark:border-indigo-900 dark:bg-indigo-950/20"><div className="text-sm text-indigo-700">ספקים בסל</div><div className="mt-2 text-2xl font-black text-indigo-700">{number(result.supplier_count)}</div><div className="text-xs text-indigo-700/70">חיסכון {number(result.savings_percent)}%</div></div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {result.suppliers.map((supplier) => <div key={supplier.supplier_id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><h3 className="font-black">{supplier.supplier_name || `ספק #${supplier.supplier_id}`}</h3><div className="mt-4 space-y-3">{supplier.items.map((item) => <div key={item.product_id} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-900"><span>{catalog.find((row) => row.id === item.product_id)?.name || `מוצר #${item.product_id}`} × {number(item.quantity)}</span><span className="font-bold">{money(item.line_total)}</span></div>)}</div></div>)}
        </div>
      </section>}
    </div>
  );
}
