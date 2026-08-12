"use client";

import { useState } from "react";
import { Bot, CheckCircle2, Loader2, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAutoClassifyProducts } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";

interface ClassificationExample {
  id: number;
  name: string;
  category: string;
  confidence: number;
  source: string;
}

interface ClassificationResult {
  classified: number;
  review_needed: number;
  skipped: number;
  remaining_uncategorized: number;
  examples: ClassificationExample[];
}

export function AutoClassifyButton() {
  const pathname = usePathname();
  const mutation = useAutoClassifyProducts();
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [expanded, setExpanded] = useState(false);

  const isCatalogPage = Boolean(pathname?.match(/(?:^|\/)dashboard\/catalog(?:\/|$)/));
  if (!isCatalogPage) return null;

  const run = () => {
    setResult(null);
    setExpanded(false);
    mutation.mutate({ limit: 1000 }, {
      onSuccess: (response) => {
        setResult({
          classified: response.counts.classified,
          review_needed: response.counts.review_needed,
          skipped: response.counts.skipped,
          remaining_uncategorized: response.remaining_uncategorized,
          examples: response.examples ?? [],
        });
      },
    });
  };

  return (
    <section className="mb-5 rounded-2xl border border-indigo-100 bg-gradient-to-l from-indigo-50 via-white to-white p-4 shadow-sm dark:border-indigo-900/50 dark:from-indigo-950/40 dark:via-slate-900 dark:to-slate-900">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600 dark:bg-indigo-900/50 dark:text-indigo-300">
              <Bot size={19} />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900 dark:text-white">סיווג מוצרים אוטומטי</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">המערכת מזהה קטגוריות לפי שם המוצר והחלטות קודמות. מוצרים שכבר אושרו ידנית נשמרים.</p>
            </div>
          </div>
          <Button onClick={run} disabled={mutation.isPending} className="shrink-0 self-start shadow-sm sm:self-auto">
            {mutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Bot size={15} />}
            {mutation.isPending ? "מסווג..." : "סווג מוצרים אוטומטית"}
          </Button>
        </div>

        {mutation.isError && (
          <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300" role="alert">
            <AlertTriangle size={15} />
            <span>לא ניתן היה להשלים את הסיווג האוטומטי. נסה שוב.</span>
          </div>
        )}

        {result && (
          <div className="rounded-xl border border-slate-200 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-900/70" role="status" aria-live="polite">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <ResultMetric label="סווגו עכשיו" value={result.classified} tone="emerald" />
              <ResultMetric label="דורשים בדיקה" value={result.review_needed} tone="amber" />
              <ResultMetric label="כבר היו מסווגים" value={result.skipped} tone="slate" />
              <ResultMetric label="עדיין ללא קטגוריה" value={result.remaining_uncategorized} tone={result.remaining_uncategorized ? "red" : "emerald"} />
            </div>

            {result.classified === 0 && result.review_needed === 0 && result.remaining_uncategorized === 0 && (
              <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                <CheckCircle2 size={15} />
                כל המוצרים במערכת כבר מסווגים.
              </div>
            )}

            {result.examples.length > 0 && (
              <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                <button type="button" onClick={() => setExpanded((value) => !value)} className="flex w-full items-center justify-between text-right text-xs font-bold text-slate-700 dark:text-slate-200">
                  <span>דוגמאות למוצרים שסווגו ({result.examples.length})</span>
                  {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </button>
                {expanded && (
                  <div className="mt-2 max-h-64 overflow-auto rounded-lg border border-slate-100 dark:border-slate-800">
                    {result.examples.map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2 last:border-b-0 dark:border-slate-800">
                        <span className="min-w-0 truncate text-xs text-slate-700 dark:text-slate-200">{item.name}</span>
                        <span className="shrink-0 rounded-full bg-indigo-50 px-2 py-1 text-[11px] font-bold text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">{item.category}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function ResultMetric({ label, value, tone }: { label: string; value: number; tone: "emerald" | "amber" | "slate" | "red" }) {
  const classes = {
    emerald: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300",
    amber: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300",
    slate: "bg-slate-50 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
    red: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300",
  };
  return (
    <div className={`rounded-lg px-3 py-2 ${classes[tone]}`}>
      <div className="text-lg font-extrabold leading-none">{value}</div>
      <div className="mt-1 text-[11px] font-semibold opacity-80">{label}</div>
    </div>
  );
}
