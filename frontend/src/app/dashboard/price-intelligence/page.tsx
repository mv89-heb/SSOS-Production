"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Award, ArrowDown, ArrowUp, Search, Sparkles } from "lucide-react";

import { useProducts } from "@/hooks/use-catalog";
import { priceIntelligenceService } from "@/services/price-intelligence-service";
import type { Product } from "@/types";

const money = (value: number, currency = "ILS") =>
  new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);

export default function PriceIntelligencePage() {
  const { data: products = [], isLoading: productsLoading } = useProducts();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState("100");

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return products.filter((p) => !term || p.name.toLowerCase().includes(term) || String(p.sku ?? "").toLowerCase().includes(term));
  }, [products, search]);

  const selected: Product | null = products.find((p) => p.id === selectedId) ?? filtered[0] ?? null;
  const comparison = useQuery({
    queryKey: ["price-intelligence", "comparison", selected?.id],
    queryFn: () => priceIntelligenceService.compareProduct(selected!.id),
    enabled: Boolean(selected?.id),
  });
  const savings = useQuery({
    queryKey: ["price-intelligence", "savings", selected?.id, quantity],
    queryFn: () => priceIntelligenceService.calculateSavings(selected!.id, Number(quantity)),
    enabled: Boolean(selected?.id) && Number(quantity) > 0,
  });

  const data = comparison.data;
  const current = data?.current;
  const best = data?.best_offer;

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-600"><Sparkles size={18} /><span className="text-sm font-semibold">Price Intelligence</span></div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white">השוואת מחירים וחיסכון</h1>
            <p className="mt-1 text-sm text-slate-500">השווה בין הספקים שלך וראה כמה אפשר לחסוך לפי הכמות שאתה באמת קונה.</p>
          </div>
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חפש מוצר או מק״ט..." className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pr-10 pl-3 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-white" />
          </div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <h2 className="mb-3 font-semibold text-slate-900 dark:text-white">מוצרים</h2>
          <div className="max-h-[620px] space-y-1 overflow-auto">
            {productsLoading && <p className="p-3 text-sm text-slate-400">טוען מוצרים...</p>}
            {!productsLoading && filtered.length === 0 && <p className="p-3 text-sm text-slate-400">לא נמצאו מוצרים.</p>}
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
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950"><div className="text-sm text-slate-500">מחיר נוכחי</div><div className="mt-2 text-2xl font-bold">{current ? money(current.normalized_price, current.currency) : "—"}</div></div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950"><div className="text-sm text-slate-500">המחיר הטוב ביותר</div><div className="mt-2 text-2xl font-bold text-emerald-600">{best ? money(best.normalized_price, best.currency) : "—"}</div></div>
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950/20"><div className="text-sm text-emerald-700">חיסכון ליחידה</div><div className="mt-2 text-2xl font-bold text-emerald-700">{data ? money(data.saving_per_unit, selected.currency) : "—"}</div></div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
                <div className="flex items-center justify-between border-b border-slate-100 p-5 dark:border-slate-800"><div><h2 className="font-semibold">ספקים</h2><p className="text-xs text-slate-500">המחירים מנורמלים ליחידת השוואה.</p></div><Award className="text-amber-500" size={20} /></div>
                {comparison.isLoading && <p className="p-5 text-sm text-slate-400">מחשב...</p>}
                {data && <div className="divide-y divide-slate-100 dark:divide-slate-800">{data.offers.map((offer) => <div key={`${offer.supplier_id}-${offer.primary}`} className="grid grid-cols-[1fr_auto_auto] items-center gap-4 p-4"><div><div className="font-medium">{offer.supplier_name || `#${offer.supplier_id}`} {offer.primary && <span className="mr-2 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">ספק ראשי</span>}</div><div className="text-xs text-slate-400">{offer.comparison_unit || offer.unit || "יחידה"}</div></div><div className="font-semibold">{money(offer.normalized_price, offer.currency)}</div><div className={offer === best ? "text-sm font-semibold text-emerald-600" : "text-sm text-slate-400"}>{offer === best ? "הזול ביותר" : ""}</div></div>)}</div>}
              </div>

              <div className="rounded-2xl border border-indigo-200 bg-indigo-50/60 p-5 dark:border-indigo-900 dark:bg-indigo-950/20">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="font-semibold">כמה אפשר לחסוך?</h2><p className="mt-1 text-sm text-slate-500">הזן כמות להזמנה וקבל חישוב אמיתי.</p></div><label className="text-sm"><span className="mb-1 block text-slate-500">כמות</span><input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="w-32 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" /></label></div>
                {savings.data && <div className="mt-5 grid gap-4 sm:grid-cols-3"><div><div className="text-xs text-slate-500">עלות נוכחית</div><div className="text-xl font-bold">{money(savings.data.current_cost, selected.currency)}</div></div><div><div className="text-xs text-slate-500">עלות במחיר הטוב ביותר</div><div className="text-xl font-bold">{money(savings.data.best_cost, selected.currency)}</div></div><div><div className="text-xs text-emerald-700">חיסכון</div><div className="flex items-center gap-1 text-xl font-bold text-emerald-700">{savings.data.savings > 0 ? <ArrowDown size={18} /> : <ArrowUp size={18} />}{money(savings.data.savings, selected.currency)} ({savings.data.savings_percent.toFixed(2)}%)</div></div></div>}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
