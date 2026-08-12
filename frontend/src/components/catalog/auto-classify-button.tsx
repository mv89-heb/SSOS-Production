"use client";

import { useState } from "react";
import { Bot, CheckCircle2, Loader2 } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAutoClassifyProducts } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";

export function AutoClassifyButton() {
  const pathname = usePathname();
  const mutation = useAutoClassifyProducts();
  const [message, setMessage] = useState<string | null>(null);

  const isCatalogPage = Boolean(pathname?.match(/(?:^|\/)dashboard\/catalog(?:\/|$)/));
  if (!isCatalogPage) return null;

  const run = () => {
    setMessage(null);
    mutation.mutate({ limit: 1000 }, {
      onSuccess: (result) => {
        setMessage(`סווגו ${result.counts.classified} מוצרים. ${result.counts.review_needed} דורשים בדיקה.`);
      },
      onError: () => setMessage("לא ניתן היה להשלים את הסיווג האוטומטי."),
    });
  };

  return (
    <section className="mb-5 rounded-2xl border border-indigo-100 bg-gradient-to-l from-indigo-50 via-white to-white p-3 shadow-sm dark:border-indigo-900/50 dark:from-indigo-950/40 dark:via-slate-900 dark:to-slate-900">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600 dark:bg-indigo-900/50 dark:text-indigo-300">
            <Bot size={19} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-slate-900 dark:text-white">סיווג מוצרים אוטומטי</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">המוצרים החדשים מסווגים אוטומטית. הפעולה הזו משלימה מוצרים קיימים שעדיין חסר להם סיווג.</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {message && (
            <div className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300" role="status" aria-live="polite">
              <CheckCircle2 size={14} className="text-emerald-600" />
              <span>{message}</span>
            </div>
          )}
          <Button onClick={run} disabled={mutation.isPending} className="shrink-0 shadow-sm">
            {mutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Bot size={15} />}
            {mutation.isPending ? "מסווג..." : "סווג מוצרים אוטומטית"}
          </Button>
        </div>
      </div>
    </section>
  );
}
