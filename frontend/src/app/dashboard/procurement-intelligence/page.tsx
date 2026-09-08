"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowDown, Award, BarChart3, BrainCircuit, CheckCircle2, RefreshCw, Sparkles, TrendingUp } from "lucide-react";

import { priceIntelligenceService } from "@/services/price-intelligence-service";

const money = (value: number, currency = "ILS") => {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
};

const date = (value?: string | null) => value ? new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" }).format(new Date(value)) : "—";

function StatCard({ label, value, hint, icon }: { label: string; value: string; hint: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center justify-between text-sm text-slate-500"><span>{label}</span>{icon}</div>
      <div className="mt-2 text-2xl font-black text-slate-900 dark:text-white">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  );
}

export default function ProcurementIntelligencePage() {
  const summary = useQuery({ queryKey: ["procurement-intelligence", "summary"], queryFn: () => priceIntelligenceService.getPortfolioSummary(10), retry: 1 });
  const suppliers = useQuery({ queryKey: ["procurement-intelligence", "suppliers"], queryFn: () => priceIntelligenceService.getSupplierScores(8), retry: 1 });
  const [briefing, setBriefing] = useState<Awaited<ReturnType<typeof priceIntelligenceService.getAiBriefing>> | null>(null);
  const [aiError, setAiError] = useState<string>();
  const [aiLoading, setAiLoading] = useState(false);

  const runBriefing = async () => {
    setAiLoading(true);
    setAiError(undefined);
    try {
      setBriefing(await priceIntelligenceService.getAiBriefing());
    } catch (error) {
      setAiError(error instanceof Error ? error.message : "לא ניתן להפעיל את Gemini כרגע.");
    } finally {
      setAiLoading(false);
    }
  };

  const data = summary.data;
  const supplierData = suppliers.data;

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-600"><BarChart3 size={18} /><span className="text-sm font-bold">Procurement Intelligence Center</span></div>
            <h1 className="text-3xl font-black text-slate-900 dark:text-white">מרכז מודיעין רכש</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">תמונה ניהולית אחת של הזדמנויות החיסכון, ספקים תחרותיים, שינויי מחירים והצעדים שכדאי לבדוק. החישובים מבוססים על נתוני הרכש שלך בלבד.</p>
          </div>
          <button type="button" onClick={() => { summary.refetch(); suppliers.refetch(); }} disabled={summary.isFetching || suppliers.isFetching} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold shadow-sm hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900"><RefreshCw size={16} />רענן נתונים</button>
        </div>
      </header>

      {summary.isError && <div className="flex items-center justify-between rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/20 dark:text-red-200"><span>לא ניתן לטעון את תמונת הרכש.</span><button type="button" onClick={() => summary.refetch()} className="font-bold underline">נסה שוב</button></div>}

      {data && <>
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="חיסכון פוטנציאלי" value={money(data.potential_savings)} hint={`${data.potential_savings_percent.toFixed(2)}% מתוך המחיר הנוכחי ליחידה`} icon={<ArrowDown className="text-emerald-500" size={18} />} />
          <StatCard label="מוצרים עם הזדמנות" value={String(data.opportunity_products)} hint={`מתוך ${data.products_analyzed} מוצרים שנותחו`} icon={<Sparkles className="text-violet-500" size={18} />} />
          <StatCard label="חלופות ברות-השוואה" value={String(data.products_with_comparable_alternatives)} hint="לפחות ספק חלופי אחד באותה יחידת השוואה ומטבע" icon={<CheckCircle2 className="text-blue-500" size={18} />} />
          <StatCard label="עלות נוכחית → מיטבית" value={`${money(data.current_unit_total)} → ${money(data.best_unit_total)}`} hint="סכום מחירי יחידה; אינו תחליף לתחזית הוצאה בפועל" icon={<TrendingUp className="text-indigo-500" size={18} />} />
        </section>

        <section className="overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 via-white to-indigo-50 shadow-sm dark:border-violet-900 dark:from-violet-950/30 dark:via-slate-950 dark:to-indigo-950/20">
          <div className="flex flex-col gap-4 border-b border-violet-100 p-5 dark:border-violet-900/60 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3"><div className="rounded-xl bg-violet-600 p-2 text-white"><BrainCircuit size={20} /></div><div><h2 className="font-black text-violet-950 dark:text-violet-100">Gemini Executive Briefing</h2><p className="mt-1 text-sm text-violet-900/70 dark:text-violet-200/70">Gemini מפרש את המספרים ומחזיר נקודות פעולה. הוא לא ממציא נתונים ולא משנה את המערכת.</p></div></div>
            <button type="button" onClick={runBriefing} disabled={aiLoading} className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-violet-700 disabled:opacity-60"><Sparkles size={16} />{aiLoading ? "Gemini מנתח..." : "הפק סיכום מנהלים"}</button>
          </div>
          <div className="p-5">
            {aiError && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">{aiError}</div>}
            {!briefing && !aiError && !aiLoading && <div className="text-sm text-slate-500">לחץ על הכפתור כדי לקבל תמונת מצב ניהולית המבוססת על נתוני המחירים והספקים.</div>}
            {aiLoading && <div className="space-y-3"><div className="h-5 w-2/3 animate-pulse rounded bg-violet-100" /><div className="h-4 w-full animate-pulse rounded bg-violet-100" /><div className="h-4 w-5/6 animate-pulse rounded bg-violet-100" /></div>}
            {briefing && <div className="space-y-5"><div className="rounded-xl border border-violet-200 bg-white/80 p-4 dark:border-violet-900 dark:bg-slate-900/60"><div className="text-xs font-bold text-violet-600">סיכום</div><div className="mt-1 text-lg font-bold text-slate-900 dark:text-white">{briefing.briefing.headline}</div><div className="mt-1 text-xs text-slate-400">{briefing.model}</div></div><div className="grid gap-4 md:grid-cols-3"><div><div className="mb-2 font-bold text-emerald-700">הזדמנויות</div><ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">{briefing.briefing.highlights.map((x, i) => <li key={`h-${i}`}>• {x}</li>)}</ul></div><div><div className="mb-2 font-bold text-amber-700">סיכונים</div><ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">{briefing.briefing.risks.map((x, i) => <li key={`r-${i}`}>• {x}</li>)}</ul></div><div><div className="mb-2 font-bold text-indigo-700">פעולות</div><ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">{briefing.briefing.actions.map((x, i) => <li key={`a-${i}`}>→ {x}</li>)}</ul></div></div></div>}
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex items-center justify-between border-b border-slate-100 p-5 dark:border-slate-800"><div><h2 className="font-black">הזדמנויות חיסכון מובילות</h2><p className="mt-1 text-xs text-slate-500">השוואה ליחידת הבסיס של כל מוצר. אין כאן המרת מטבע.</p></div><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">{data.top_opportunities.length} הזדמנויות</span></div>
            {data.top_opportunities.length === 0 ? <div className="p-6 text-sm text-slate-500">לא זוהו כרגע הזדמנויות חיסכון.</div> : <div className="overflow-x-auto"><table className="w-full text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">מוצר</th><th className="px-5 py-3">ספק נוכחי</th><th className="px-5 py-3">ספק מומלץ לפי מחיר</th><th className="px-5 py-3">חיסכון ליחידה</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{data.top_opportunities.map((row) => <tr key={row.product_id}><td className="px-5 py-4 font-semibold">{row.product_name}<div className="text-xs text-slate-400">{row.sku || "ללא מק״ט"}</div></td><td className="px-5 py-4">{row.current_supplier || "—"}</td><td className="px-5 py-4 text-emerald-700 dark:text-emerald-300">{row.best_supplier || "—"}</td><td className="px-5 py-4 font-black text-emerald-700 dark:text-emerald-300">{money(row.savings_per_unit, row.currency)}<div className="text-xs font-normal">{row.savings_percent.toFixed(2)}%</div></td></tr>)}</tbody></table></div>}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="border-b border-slate-100 p-5 dark:border-slate-800"><div className="flex items-center gap-2"><Award className="text-amber-500" size={18} /><h2 className="font-black">דירוג ספקים לפי מחיר</h2></div><p className="mt-1 text-xs text-slate-500">הציון משקף כיסוי בקטלוג וניצחונות במחיר בלבד — לא איכות או שירות.</p></div>
            {supplierData?.suppliers?.length ? <div className="divide-y divide-slate-100 dark:divide-slate-800">{supplierData.suppliers.map((supplier, index) => <div key={supplier.supplier_id} className="flex items-center gap-3 p-4"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-sm font-black dark:bg-slate-900">{index + 1}</div><div className="min-w-0 flex-1"><div className="truncate font-semibold">{supplier.supplier_name || `ספק #${supplier.supplier_id}`}</div><div className="mt-1 text-xs text-slate-400">כיסוי {supplier.coverage_percent.toFixed(0)}% · ניצחונות {supplier.wins}/{supplier.participation}</div></div><div className="text-left"><div className="font-black text-indigo-600">{supplier.score}</div><div className="text-[10px] text-slate-400">ציון</div></div></div>)}</div> : <div className="p-6 text-sm text-slate-500">אין מספיק נתוני השוואה לדירוג ספקים.</div>}
          </section>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex items-center gap-2 border-b border-slate-100 p-5 dark:border-slate-800"><AlertTriangle className="text-amber-500" size={18} /><div><h2 className="font-black">שינויי המחירים האחרונים</h2><p className="mt-1 text-xs text-slate-500">מעקב אחר אירועי מחיר שנשמרו במערכת.</p></div></div>
          {data.recent_changes.length ? <div className="overflow-x-auto"><table className="w-full text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">תאריך</th><th className="px-5 py-3">ספק</th><th className="px-5 py-3">מחיר חדש</th><th className="px-5 py-3">שינוי</th><th className="px-5 py-3">מקור</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{data.recent_changes.map((row) => <tr key={row.id}><td className="px-5 py-3">{date(row.effective_at)}</td><td className="px-5 py-3">{row.supplier_name || `#${row.supplier_id}`}</td><td className="px-5 py-3 font-semibold">{money(row.new_price, row.currency)}</td><td className={`px-5 py-3 font-bold ${row.change_percent !== null && row.change_percent > 0 ? "text-red-600" : "text-emerald-600"}`}>{row.change_percent === null ? "—" : `${row.change_percent > 0 ? "+" : ""}${row.change_percent.toFixed(2)}%`}</td><td className="px-5 py-3 text-xs text-slate-400">{row.source_type}</td></tr>)}</tbody></table></div> : <div className="p-6 text-sm text-slate-500">אין שינויי מחיר מתועדים.</div>}
        </section>
      </>}
    </div>
  );
}
