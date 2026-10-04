"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ExternalLink, Loader2, Sparkles, TriangleAlert } from "lucide-react";
import { geminiPriceCompletionService, type PriceCompletionResult } from "@/services/gemini-price-completion-service";

const money = (value?: number | null, currency = "ILS") => {
  if (value == null) return "—";
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return value.toFixed(2) + " " + currency;
  }
};

export default function PriceCompletionPage() {
  const [status, setStatus] = useState({ total_active: 0, priced: 0, missing_price: 0 });
  const [running, setRunning] = useState(false);
  const [processed, setProcessed] = useState(0);
  const [updated, setUpdated] = useState(0);
  const [results, setResults] = useState<PriceCompletionResult[]>([]);
  const [error, setError] = useState<string>();

  const refresh = async () => setStatus(await geminiPriceCompletionService.status());

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof Error ? e.message : "לא ניתן לטעון את מצב הקטלוג."));
  }, []);

  const completionPercent = useMemo(() => {
    if (!status.total_active) return 100;
    return Math.round((status.priced / status.total_active) * 100);
  }, [status]);

  const runAll = async () => {
    if (running) return;
    setRunning(true);
    setError(undefined);
    setResults([]);
    setProcessed(0);
    setUpdated(0);
    let offset = 0;
    try {
      while (true) {
        const batch = await geminiPriceCompletionService.run(offset, 5);
        setProcessed((value) => value + batch.processed);
        setUpdated((value) => value + batch.updated);
        setResults((value) => [...batch.results, ...value].slice(0, 100));
        if (batch.next_offset == null) break;
        offset = batch.next_offset;
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "השלמת המחירים נכשלה.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-violet-600"><Sparkles size={18} /><span className="text-sm font-semibold">Gemini Price Completion</span></div>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white">השלמת מחירים אוטומטית</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-500">Gemini מחפש מחירים עדכניים באינטרנט באמצעות Google Search, מתאים את האריזה ומכניס את המחיר החסר לקטלוג עם מקור ורמת ביטחון.</p>
          </div>
          <button type="button" onClick={runAll} disabled={running || status.missing_price === 0} className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60">
            {running ? <><Loader2 size={17} className="animate-spin" />Gemini משלים מחירים...</> : <><Sparkles size={17} />השלם את כל המחירים החסרים</>}
          </button>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="text-sm text-slate-500">מוצרים פעילים</div><div className="mt-2 text-3xl font-bold">{status.total_active}</div></div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm dark:border-emerald-900 dark:bg-emerald-950/20"><div className="text-sm text-emerald-700">עם מחיר</div><div className="mt-2 text-3xl font-bold text-emerald-700">{status.priced}</div></div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm dark:border-amber-900 dark:bg-amber-950/20"><div className="text-sm text-amber-700">חסרי מחיר</div><div className="mt-2 text-3xl font-bold text-amber-700">{status.missing_price}</div></div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex items-center justify-between text-sm"><span className="font-semibold">כיסוי מחירים</span><span className="font-bold">{completionPercent}%</span></div>
        <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: completionPercent + "%" }} /></div>
        {running && <p className="mt-3 text-xs text-slate-500">עובדו {processed} מוצרים. המחירים נשמרים לאחר כל מוצר. עודכנו בסבב הנוכחי: {updated}.</p>}
      </section>

      {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/20">{error}</div>}

      {results.length > 0 && <section className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="border-b border-slate-100 p-5 dark:border-slate-800"><h2 className="font-bold">תוצאות אחרונות</h2><p className="mt-1 text-xs text-slate-500">כל מחיר שנמצא נשמר עם מקור ב־Price History.</p></div>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {results.map((row, index) => <div key={row.product_id + "-" + index} className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div><div className="font-semibold">{row.product_name}</div><div className="mt-1 text-xs text-slate-500">{row.match_type || row.reason || "—"} {row.confidence != null ? "· ביטחון " + row.confidence + "%" : ""}</div></div>
            <div className="flex items-center gap-4">
              {row.status === "updated" ? <><div className="text-right"><div className="font-bold text-emerald-700">{money(row.new_price, row.currency)}</div><div className="text-xs text-slate-400">{row.package_description || "מחיר שנמצא באינטרנט"}</div></div><CheckCircle2 className="text-emerald-600" size={20} />{row.sources?.[0] && <a className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline" href={row.sources[0]} target="_blank" rel="noreferrer">מקור <ExternalLink size={13} /></a>}</> : <><TriangleAlert className="text-amber-600" size={20} /><span className="max-w-xl text-sm text-amber-800">{row.reason || "לא נמצא מחיר אמין"}</span></>}
            </div>
          </div>)}
        </div>
      </section>}
    </div>
  );
}
