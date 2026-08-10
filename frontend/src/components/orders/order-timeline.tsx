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
      <div className="rounded-2xl border border-red-200 bg-red-50 p-5 dark:border-red-900/50 dark:bg-red-950/30">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-300">
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

  const activeIndex = STAGES.findIndex((stage) => stage.key === currentStatus);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900 md:p-6">
      <div className="mb-5">
        <p className="text-sm font-extrabold text-slate-950 dark:text-white">תהליך ההזמנה</p>
        <p className="mt-1 text-xs text-slate-400">התקדמות ההזמנה לאורך מחזור הרכש</p>
      </div>

      <div className="hidden md:block">
        <div className="relative px-5">
          <div className="absolute left-5 right-5 top-5 h-0.5 bg-slate-200 dark:bg-slate-700" />
          <div
            className="absolute right-5 top-5 h-0.5 bg-indigo-600 transition-all duration-500"
            style={{ width: `${activeIndex <= 0 ? 0 : (activeIndex / (STAGES.length - 1)) * 100}%` }}
          />
          <div className="relative flex justify-between">
            {STAGES.map((stage, index) => {
              const completed = index < activeIndex;
              const current = index === activeIndex;

              return (
                <div key={stage.key} className="flex w-24 flex-col items-center text-center">
                  <div
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-full border-2 bg-white text-xs font-bold transition-all duration-300 dark:bg-slate-900",
                      completed && "border-indigo-600 bg-indigo-600 text-white shadow-md shadow-indigo-600/20",
                      current && "border-indigo-600 text-indigo-700 ring-4 ring-indigo-100 dark:bg-indigo-950 dark:text-indigo-300 dark:ring-indigo-950/70",
                      !completed && !current && "border-slate-200 text-slate-400 dark:border-slate-700"
                    )}
                  >
                    {completed ? <Check className="h-4 w-4" /> : current ? <Circle className="h-3 w-3 fill-current" /> : index + 1}
                  </div>
                  <span className={cn("mt-3 text-xs font-bold", current ? "text-indigo-700 dark:text-indigo-300" : completed ? "text-slate-700 dark:text-slate-200" : "text-slate-400")}>{stage.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-3 md:hidden">
        {STAGES.map((stage, index) => {
          const completed = index < activeIndex;
          const current = index === activeIndex;

          return (
            <div key={stage.key} className="flex items-center gap-3">
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
              <div>
                <p className={cn("text-sm font-bold", current ? "text-indigo-700 dark:text-indigo-300" : "text-slate-700 dark:text-slate-200")}>{stage.label}</p>
                <p className="text-[11px] text-slate-400">
                  {completed ? "הושלם" : current ? "שלב נוכחי" : "ממתין"}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
