import { Check, Circle, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { OrderStatus } from "@/types";

const STAGES: Array<{ key: Exclude<OrderStatus, "cancelled">; label: string }> = [
  { key: "draft", label: "טיוטה" },
  { key: "submitted", label: "הוגשה" },
  { key: "approved", label: "אושרה" },
  { key: "sent", label: "נשלחה לספק" },
  { key: "completed", label: "הושלמה" },
];

export function OrderTimeline({ currentStatus }: { currentStatus: OrderStatus }) {
  if (currentStatus === "cancelled") {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-5 shadow-sm dark:border-red-900/50 dark:bg-red-950/30">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-300">
            <X className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-extrabold text-red-900 dark:text-red-200">ההזמנה בוטלה</p>
            <p className="mt-0.5 text-xs text-red-700 dark:text-red-400">הזמנה זו אינה ממשיכה בתהליך הרכש.</p>
          </div>
        </div>
      </div>
    );
  }

  const activeIndex = Math.max(0, STAGES.findIndex((stage) => stage.key === currentStatus));
  const progress = (activeIndex / (STAGES.length - 1)) * 100;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900 md:p-6" aria-label="תהליך ההזמנה">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-extrabold text-slate-950 dark:text-white">תהליך ההזמנה</p>
          <p className="mt-1 text-xs text-slate-400">התקדמות ההזמנה לאורך מחזור הרכש</p>
        </div>
        <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
          שלב {activeIndex + 1} מתוך {STAGES.length}
        </span>
      </div>

      <div className="hidden md:block">
        <div className="relative px-5">
          <div className="absolute left-5 right-5 top-5 h-1 -translate-y-1/2 rounded-full bg-slate-100 dark:bg-slate-800" />
          <div
            className="absolute right-5 top-5 h-1 -translate-y-1/2 rounded-full bg-indigo-600 transition-[width] duration-500 ease-out"
            style={{ width: `${progress}%` }}
            aria-hidden="true"
          />
          <div className="relative flex justify-between">
            {STAGES.map((stage, index) => {
              const completed = index < activeIndex;
              const current = index === activeIndex;

              return (
                <div key={stage.key} className="flex w-24 flex-col items-center text-center">
                  <div
                    className={cn(
                      "relative flex h-10 w-10 items-center justify-center rounded-full border-2 bg-white text-xs font-bold transition-all duration-300 dark:bg-slate-900",
                      completed && "border-indigo-600 bg-indigo-600 text-white shadow-md shadow-indigo-600/20",
                      current && "border-indigo-600 text-indigo-700 ring-4 ring-indigo-100 dark:bg-indigo-950 dark:text-indigo-300 dark:ring-indigo-950/70",
                      !completed && !current && "border-slate-200 text-slate-400 dark:border-slate-700"
                    )}
                  >
                    {current && <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400/20" aria-hidden="true" />}
                    <span className="relative z-10">
                      {completed ? <Check className="h-4 w-4" /> : current ? <Circle className="h-3 w-3 fill-current" /> : index + 1}
                    </span>
                  </div>
                  <span className={cn("mt-3 text-xs font-bold", current ? "text-indigo-700 dark:text-indigo-300" : completed ? "text-slate-700 dark:text-slate-200" : "text-slate-400")}>{stage.label}</span>
                  <span className="mt-1 text-[10px] text-slate-400">
                    {completed ? "הושלם" : current ? "שלב נוכחי" : "ממתין"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-2 md:hidden">
        {STAGES.map((stage, index) => {
          const completed = index < activeIndex;
          const current = index === activeIndex;

          return (
            <div key={stage.key} className={cn("flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors", current && "bg-indigo-50/70 dark:bg-indigo-950/30")}>
              <div
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold",
                  completed && "border-indigo-600 bg-indigo-600 text-white",
                  current && "border-indigo-600 bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
                  !completed && !current && "border-slate-200 text-slate-400 dark:border-slate-700"
                )}
              >
                {completed ? <Check className="h-4 w-4" /> : index + 1}
              </div>
              <div className="min-w-0">
                <p className={cn("text-sm font-bold", current ? "text-indigo-700 dark:text-indigo-300" : "text-slate-700 dark:text-slate-200")}>{stage.label}</p>
                <p className="text-[11px] text-slate-400">{completed ? "הושלם" : current ? "שלב נוכחי" : "ממתין"}</p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
