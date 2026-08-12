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

  if (!pathname?.startsWith("/dashboard/catalog")) return null;

  const run = () => {
    setMessage(null);
    mutation.mutate(1000, {
      onSuccess: (result) => {
        setMessage(`סווגו ${result.counts.classified} מוצרים. ${result.counts.review_needed} דורשים בדיקה.`);
      },
      onError: () => setMessage("לא ניתן היה להשלים את הסיווג האוטומטי."),
    });
  };

  return (
    <div className="fixed bottom-5 left-5 z-40 flex max-w-[min(92vw,520px)] items-center gap-2 rounded-2xl border border-indigo-100 bg-white/95 p-2 shadow-xl backdrop-blur dark:border-indigo-900/50 dark:bg-slate-900/95">
      <Button onClick={run} disabled={mutation.isPending} size="sm" className="shrink-0">
        {mutation.isPending ? <Loader2 size={15} className="animate-spin" /> : <Bot size={15} />}
        {mutation.isPending ? "מסווג..." : "סווג מוצרים אוטומטית"}
      </Button>
      {message ? (
        <div className="flex items-center gap-1 text-xs text-slate-600 dark:text-slate-300">
          <CheckCircle2 size={14} className="text-emerald-600" />
          <span>{message}</span>
        </div>
      ) : (
        <span className="hidden text-xs text-slate-500 sm:inline">מוצרים חדשים מסווגים אוטומטית; הכפתור משלים מוצרים ישנים.</span>
      )}
    </div>
  );
}
