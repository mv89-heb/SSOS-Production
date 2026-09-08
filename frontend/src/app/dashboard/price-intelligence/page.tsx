"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowDown, ArrowUp, Award, BarChart3, BrainCircuit, CheckCircle2,
  Clock3, RefreshCw, Search, ShieldCheck, Sparkles, TrendingDown, TrendingUp,
} from "lucide-react";

import { useProducts } from "@/hooks/use-catalog";
import { priceIntelligenceService } from "@/services/price-intelligence-service";
import type { GeminiInsight } from "@/services/price-intelligence-service";
import type { Product } from "@/types";

const money = (value: number, currency = "ILS") => {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
};

const date = (value?: string | null) => value ? new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" }).format(new Date(value)) : "—";

function Stat({ label, value, hint, icon }: { label: string; value: string; hint?: string; icon: React.ReactNode }) {
  return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
    <div className="flex items-center justify-between text-sm text-slate-500"><span>{label}</span>{icon}</div>
    <div className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">{value}</div>
    {hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
  </div>;
}

function GeminiCard({ insight, model, isLoading, error, onRun }: { insight?: GeminiInsight; model?: string; isLoading: boolean; error?: string; onRun: () => void }) {
  return <section className="overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 via-white to-indigo-50 shadow-sm dark:border-violet-900 dark:from-violet-950/30 dark:via-slate-950 dark:to-indigo-950/20">
    <div className="flex flex-col gap-4 border-b border-violet-100 p-5 dark:border-violet-900/60 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3"><div className="rounded-xl bg-violet-600 p-2 text-white"><BrainCircuit size={20} /></div><div><div className="flex items-center gap-2"><h2 className="font-bold text-violet-950 dark:text-violet-100">Gemini Procurement Advisor</h2><span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700 dark:bg-violet-900/60 dark:text-violet-200">AI</span></div><p className="mt-1 text-sm text-violet-900/70 dark:text-violet-200/70">מפרש את נתוני המחירים ומסביר מה כדאי לעשות — בלי לשנות את נתוני המערכת.</p></div></div>
      <button type="button" disabled={isLoading} onClick={onRun} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60"><Sparkles size={16} />{isLoading ? "Gemini מנתח..." : "נתח עם Gemini"}</button>
    </div>
    <div className="p-5">
      {error && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">{error}</div>}
      {!insight && !error && !isLoading && <div className="flex items-center gap-3 text-sm text-slate-500"><Sparkles size={18} className="text-violet-500" />לחץ על "נתח עם Gemini" כדי לקבל המלצה המבוססת על ההשוואה והיסטוריית המחירים.</div>}
      {isLoading && <div className="space-y-3"><div className="h-5 w-2/3 animate-pulse rounded bg-violet-100" /><div className="h-4 w-full animate-pulse rounded bg-violet-100" /><div className="h-4 w-5/6 animate-pulse rounded bg-violet-100" /></div>}
      {insight && <div className="space-y-5">
        <div className="rounded-xl border border-violet-200 bg-white/80 p-4 dark:border-violet-900 dark:bg-slate-900/60"><div className="text-xs font-semibold text-violet-600">המלצת Gemini</div><div className="mt-1 text-xl font-bold text-slate-900 dark:text-white">{insight.recommendation || "אין המלצה חד-משמעית"}</div><div className="mt-2 flex items-center gap-2 text-xs text-slate-500">רמת ביטחון: {insight.confidence}% {model ? `· ${model}` : ""}</div></div>
        <div className="grid gap-4 md:grid-cols-2"><div><div className="mb-2 flex items-center gap-2 font-semibold"><ShieldCheck size={16} className="text-emerald-600" />למה?</div><ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">{insight.reasons.map((item, i) => <li key={`reason-${i}`} className="flex gap-2"><span>•</span>{item}</li>)}</ul></div><div><div className="mb-2 flex items-center gap-2 font-semibold"><AlertTriangle size={16} className="text-amber-600" />סיכונים / מה לבדוק</div><ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">{insight.risks.map((item, i) => <li key={`risk-${i}`} className="flex gap-2"><span>•</span>{item}</li>)}</ul></div></div>
        <div className="grid gap-4 md:grid-cols-2"><div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900"><div className="text-xs text-slate-500">מגמת מחיר</div><div className="mt-1 text-sm font-medium">{insight.trend}</div></div><div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900"><div className="text-xs text-slate-500">הפעולות המומלצות</div><ul className="mt-1 space-y-1 text-sm font-medium">{insight.actions.map((item, i) => <li key={`action-${i}`}>→ {item}</li>)}</ul></div></div>
      </div>}
    </div>
  </section>;
}

export default function PriceIntelligencePage() {
  const { data: products = [], isLoading: productsLoading, isError: productsError } = useProducts();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState("100");
  const [geminiError, setGeminiError] = useState<string>();
  const [geminiInsight, setGeminiInsight] = useState<GeminiInsight>();
  const [geminiModel, setGeminiModel] = useState<string>();

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return products.filter((p) => !term || p.name.toLowerCase().includes(term) || String(p.sku ?? "").toLowerCase().includes(term));
  }, [products, search]);
  const selected: Product | null = products.find((p) => p.id === selectedId) ?? filtered[0] ?? null;

  const comparison = useQuery({
    queryKey: ["price-intelligence", "comparison", selected?.id],
    queryFn: () => priceIntelligenceService.compareProduct(selected!.id),
    enabled: Boolean(selected?.id), retry: 1,
  });
  const numericQuantity = Number(quantity);
  const savings = useQuery({
    queryKey: ["price-intelligence", "savings", selected?.id, quantity],
    queryFn: () => priceIntelligenceService.calculateSavings(selected!.id, numericQuantity),
    enabled: Boolean(selected?.id) && Number.isFinite(numericQuantity) && numericQuantity > 0 && Boolean(comparison.data), retry: 1,
  });
  const history = useQuery({
    queryKey: ["price-intelligence", "history", selected?.id],
    queryFn: () => priceIntelligenceService.getHistory(selected!.id, undefined),
    enabled: Boolean(selected?.id) && Boolean(comparison.data), retry: 1,
  });
  const gemini = useQuery({
    queryKey: ["price-intelligence", "gemini", selected?.id, quantity],
    queryFn: async () => priceIntelligenceService.getGeminiInsight(selected!.id, numericQuantity),
    enabled: false,
    retry: 0,
  });

  const data = comparison.data;
  const current = data?.current;
  const best = data?.best_offer;
  const avg = data?.offers.length ? data.offers.reduce((sum, row) => sum + row.normalized_price, 0) / data.offers.length : null;
  const spread = current && best ? current.normalized_price - best.normalized_price : 0;
  const lastHistory = history.data?.[0];
  const runGemini = async () => {
    if (!selected || !Number.isFinite(numericQuantity) || numericQuantity <= 0) return;
    setGeminiError(undefined);
    setGeminiInsight(undefined);
    try {
      const result = await gemini.refetch();
      if (result.data) { setGeminiInsight(result.data.insight); setGeminiModel(result.data.model); }
      else setGeminiError("Gemini לא החזיר ניתוח. נסה שוב.");
    } catch (error) { setGeminiError(error instanceof Error ? error.message : "לא ניתן להפעיל את Gemini כרגע."); }
  };

  return <div dir="rtl" className="space-y-6 pb-10">
    <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><div className="mb-2 flex items-center gap-2 text-violet-600"><Sparkles size={18} /><span className="text-sm font-semibold">Price Intelligence 2.0</span></div><h1 className="text-3xl font-bold text-slate-900 dark:text-white">מודיעין מחירים והשוואת ספקים</h1><p className="mt-1 max-w-3xl text-sm text-slate-500">לא רק מי הכי זול: כמה באמת נחסוך, מה מצב השוק בתוך הנתונים שלך, מה השתנה לאחרונה ומה Gemini ממליץ לבדוק לפני ההזמנה.</p></div><div className="relative w-full max-w-sm"><Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חפש מוצר או מק״ט..." className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pr-10 pl-3 text-sm outline-none focus:border-violet-500 dark:border-slate-700 dark:bg-slate-900 dark:text-white" /></div></div>
    </header>

    <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-slate-900 dark:text-white">מוצרים</h2><span className="text-xs text-slate-400">{filtered.length}</span></div><div className="max-h-[720px] space-y-1 overflow-auto">
        {productsLoading && <p className="p-3 text-sm text-slate-400">טוען מוצרים...</p>}{productsError && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">לא ניתן לטעון את הקטלוג.</p>}{!productsLoading && !productsError && filtered.length === 0 && <p className="p-3 text-sm text-slate-400">לא נמצאו מוצרים.</p>}
        {filtered.map((product) => <button key={product.id} type="button" onClick={() => { setSelectedId(product.id); setGeminiInsight(undefined); setGeminiError(undefined); }} className={`w-full rounded-xl p-3 text-right transition ${selected?.id === product.id ? "bg-violet-50 ring-1 ring-violet-200 dark:bg-violet-950/40" : "hover:bg-slate-50 dark:hover:bg-slate-900"}`}><div className="font-medium text-slate-900 dark:text-white">{product.name}</div><div className="mt-1 flex justify-between text-xs text-slate-500"><span>{product.sku || "ללא מק״ט"}</span><span>{money(product.current_price, product.currency)}</span></div></button>)}
      </div></section>

      <section className="space-y-4">
        {!selected && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-slate-500">בחר מוצר כדי לפתוח ניתוח מחירים.</div>}
        {selected && <>
          {comparison.isError && <div className="flex items-start justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800 dark:border-red-900 dark:bg-red-950/20 dark:text-red-200"><div><div className="font-semibold">השוואת הספקים נכשלה</div><div className="mt-1 text-sm">{comparison.error instanceof Error ? comparison.error.message : "לא ניתן לטעון את הנתונים."}</div></div><button type="button" onClick={() => comparison.refetch()} className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-semibold shadow-sm"><RefreshCw size={15} />נסה שוב</button></div>}
          {data && <>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><h2 className="text-xl font-bold text-slate-900 dark:text-white">{selected.name}</h2><p className="text-sm text-slate-500">מק״ט: {selected.sku || "ללא מק״ט"} · ספק נוכחי: {current?.supplier_name || "לא זמין"}</p></div><div className="flex flex-wrap gap-2"><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-900 dark:text-slate-300">יחידת השוואה: {current?.comparison_unit || selected.unit || "יחידה"}</span><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-900 dark:text-slate-300">עדכון היסטוריה: {date(lastHistory?.effective_at)}</span></div></div></div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="מחיר נוכחי" value={current ? money(current.normalized_price, current.currency) : "אין מחיר"} hint={current?.supplier_name || undefined} icon={<BarChart3 size={17} />} /><Stat label="המחיר הזול ביותר" value={best ? money(best.normalized_price, best.currency) : "אין הצעה"} hint={best?.supplier_name || undefined} icon={<Award size={17} className="text-emerald-500" />} /><Stat label="פער אפשרי" value={current && best ? money(Math.max(0, spread), current.currency) : "—"} hint={data.saving_percent ? `${data.saving_percent.toFixed(2)}% מתחת למחיר הנוכחי` : "אין חיסכון מזוהה"} icon={<TrendingDown size={17} className="text-emerald-500" />} /><Stat label="ממוצע הצעות" value={avg !== null ? money(avg, current?.currency || "ILS") : "—"} hint={`${data.offers.length} ספקים ברי-השוואה`} icon={<BarChart3 size={17} className="text-violet-500" />} /></div>

            <GeminiCard insight={geminiInsight} model={geminiModel} isLoading={gemini.isFetching} error={geminiError} onRun={runGemini} />

            <div className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-col gap-3 border-b border-slate-100 p-5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-semibold">השוואת ספקים מלאה</h2><p className="text-xs text-slate-500">הדירוג מתבצע רק כשמטבע ויחידת ההשוואה תואמים. הצעות אחרות נשארות גלויות.</p></div><span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700 dark:bg-violet-950/40 dark:text-violet-200">{data.offers.length + data.incomparable_offers.length} הצעות נבדקו</span></div>
              {comparison.isLoading && <p className="p-5 text-sm text-slate-400">מחשב...</p>}{!comparison.isLoading && data.offers.length === 0 && <div className="p-6 text-center text-sm text-slate-500">אין כרגע הצעות שניתן להשוות.</div>}{data.offers.length > 0 && <div className="overflow-x-auto"><table className="w-full text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">ספק</th><th className="px-5 py-3">מחיר מקורי</th><th className="px-5 py-3">מחיר ליחידת השוואה</th><th className="px-5 py-3">פער מהנוכחי</th><th className="px-5 py-3">סטטוס</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{data.offers.map((offer) => { const diff = current ? current.normalized_price - offer.normalized_price : 0; return <tr key={`${offer.supplier_id}-${offer.primary}`}><td className="px-5 py-4 font-medium">{offer.supplier_name || `#${offer.supplier_id}`}{offer.primary && <span className="mr-2 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">נוכחי</span>}</td><td className="px-5 py-4">{money(offer.price, offer.currency)}<div className="text-xs text-slate-400">{offer.unit || "יחידה"}</div></td><td className="px-5 py-4 font-semibold">{money(offer.normalized_price, offer.currency)}<div className="text-xs text-slate-400">{offer.comparison_unit || "—"}</div></td><td className={`px-5 py-4 font-semibold ${diff > 0 ? "text-emerald-600" : diff < 0 ? "text-red-600" : "text-slate-400"}`}>{current ? `${diff > 0 ? "−" : diff < 0 ? "+" : ""}${money(Math.abs(diff), current.currency)}` : "—"}</td><td className="px-5 py-4">{offer === best ? <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 size={15} />הטוב ביותר</span> : <span className="text-slate-400">זמין להשוואה</span>}</td></tr>; })}</tbody></table></div>}
            </div>

            {data.incomparable_offers.length > 0 && <div className="rounded-2xl border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20"><div className="flex items-start gap-3 border-b border-amber-200 p-5 dark:border-amber-900"><AlertTriangle className="mt-0.5 text-amber-600" size={20} /><div><h2 className="font-semibold text-amber-900 dark:text-amber-200">הצעות שדורשות בדיקה</h2><p className="mt-1 text-xs text-amber-800/80 dark:text-amber-200/70">לא הסתרנו אותן — Gemini יכול לעזור להסביר מה כדאי לבדוק, אבל לא ימציא שערי מטבע או המרות.</p></div></div><div className="divide-y divide-amber-200/70 dark:divide-amber-900">{data.incomparable_offers.map((offer) => <div key={`incomparable-${offer.supplier_id}`} className="flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:justify-between"><div className="font-medium text-amber-950 dark:text-amber-100">{offer.supplier_name || `#${offer.supplier_id}`}</div><div className="text-sm text-amber-900/80 dark:text-amber-200/80">{money(offer.price, offer.currency)} · {offer.incomparable_reason || "נתונים לא תואמים"}</div></div>)}</div></div>}

            <div className="grid gap-4 lg:grid-cols-[1fr_320px]"><div className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-100 p-5 dark:border-slate-800"><div className="flex items-center gap-2"><Clock3 size={18} className="text-violet-500" /><h2 className="font-semibold">היסטוריית מחירים</h2></div><p className="mt-1 text-xs text-slate-500">נתוני עבר משמשים את Gemini לזיהוי מגמות ואנומליות.</p></div>{history.isLoading && <p className="p-5 text-sm text-slate-400">טוען היסטוריה...</p>}{history.data?.length ? <div className="overflow-x-auto"><table className="w-full text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">תאריך</th><th className="px-5 py-3">ספק</th><th className="px-5 py-3">מחיר חדש</th><th className="px-5 py-3">שינוי</th><th className="px-5 py-3">מקור</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{history.data.slice(0, 10).map((row) => <tr key={row.id}><td className="px-5 py-3">{date(row.effective_at)}</td><td className="px-5 py-3">{row.supplier_name || `#${row.supplier_id}`}</td><td className="px-5 py-3 font-semibold">{money(row.new_price, row.currency)}</td><td className={`px-5 py-3 font-semibold ${row.change_percent && row.change_percent > 0 ? "text-red-600" : "text-emerald-600"}`}>{row.change_percent === null ? "—" : `${row.change_percent > 0 ? "+" : ""}${row.change_percent.toFixed(2)}%`}</td><td className="px-5 py-3 text-xs text-slate-400">{row.source_type}</td></tr>)}</tbody></table></div> : <div className="p-6 text-sm text-slate-500">אין עדיין היסטוריית מחירים למוצר.</div>}</div>
              <div className="rounded-2xl border border-indigo-200 bg-indigo-50/60 p-5 dark:border-indigo-900 dark:bg-indigo-950/20"><div className="flex items-center gap-2"><BarChart3 size={18} className="text-indigo-600" /><h2 className="font-semibold">השפעת הכמות</h2></div><label className="mt-4 block text-sm"><span className="mb-1 block text-slate-500">כמות להזמנה</span><input type="number" min="1" step="any" value={quantity} onChange={(e) => { setQuantity(e.target.value); setGeminiInsight(undefined); }} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 dark:border-slate-700 dark:bg-slate-900" /></label>{!Number.isFinite(numericQuantity) || numericQuantity <= 0 ? <p className="mt-3 text-sm text-amber-700">הזן כמות גדולה מאפס.</p> : savings.data && <div className="mt-5 space-y-4"><div><div className="text-xs text-slate-500">עלות נוכחית</div><div className="text-xl font-bold">{money(savings.data.current_cost, current?.currency)}</div></div><div><div className="text-xs text-slate-500">עלות במחיר הטוב ביותר</div><div className="text-xl font-bold">{money(savings.data.best_cost, best?.currency)}</div></div><div className="rounded-xl bg-white p-4 dark:bg-slate-900"><div className="text-xs text-emerald-700">חיסכון בכמות הזו</div><div className="mt-1 flex items-center gap-1 text-xl font-bold text-emerald-700">{savings.data.savings > 0 ? <ArrowDown size={18} /> : <ArrowUp size={18} />}{money(savings.data.savings, current?.currency)}</div><div className="text-xs text-slate-500">{savings.data.savings_percent.toFixed(2)}%</div></div><div className="text-sm font-semibold text-emerald-700">✓ הספק המומלץ: {savings.data.best_supplier_name || "—"}</div></div>}</div>
            </div>
          </>}
        </>}
      </section>
    </div>
  </div>;
}
