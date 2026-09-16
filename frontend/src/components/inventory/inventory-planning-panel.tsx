"use client";

import { useMemo, useState } from "react";
import { CalendarDays, CheckCircle2, Clock3, Settings2, Sparkles, TriangleAlert, Truck } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { inventoryService, type InventoryPlanningPeriod } from "@/services/inventory-service";

const fmtDate = (value?: string | null) => value ? new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" }).format(new Date(`${value}T12:00:00`)) : "—";

export default function InventoryPlanningPanel() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const countStatus = useQuery({ queryKey: ["inventory", "count-status"], queryFn: inventoryService.getCountStatus, staleTime: 30_000 });
  const periods = useQuery({ queryKey: ["inventory", "planning-periods"], queryFn: inventoryService.getPlanningPeriods, staleTime: 60_000 });
  const upcoming = useMemo(() => (periods.data ?? []).filter((period) => period.active).slice(0, 5), [periods.data]);

  const seedHolidays = async () => {
    if (busy) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await inventoryService.seedHolidayPeriods();
      setMessage(result.created_count ? `נוספו ${result.created_count} תקופות חג לעריכה.` : "תקופות החג כבר קיימות במערכת.");
      await qc.invalidateQueries({ queryKey: ["inventory", "planning-periods"] });
      await qc.invalidateQueries({ queryKey: ["inventory", "recommendations"] });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "טעינת תקופות החג נכשלה.");
    } finally { setBusy(false); }
  };

  const status = countStatus.data;
  return <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
    <div className="border-b border-slate-200 bg-gradient-to-l from-indigo-50 to-white p-5 dark:border-slate-800 dark:from-indigo-950/30 dark:to-slate-950">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div><div className="flex items-center gap-2 text-sm font-black text-indigo-700 dark:text-indigo-300"><CalendarDays size={19}/> ספירת מלאי ותכנון תקופות</div><h2 className="mt-1 text-xl font-black">המלאי נקבע לפי מה שנמצא בפועל</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">אין צורך לדווח על כל לקיחה מהמחסן. כל ספירה יוצרת נקודת אמת חדשה, והרכישות והספירות משמשות לחישוב קצב הצריכה.</p></div><div className="flex flex-wrap gap-2"><a href="/dashboard/inventory/planning" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-white px-4 text-sm font-black text-indigo-700 ring-1 ring-indigo-200"><Settings2 size={17}/> ניהול תקופות</a><button onClick={seedHolidays} disabled={busy} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-black text-white disabled:opacity-50"><Sparkles size={17}/>{busy ? "טוען…" : "הוסף תקופות חגים"}</button></div></div>
    </div>
    <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
      <div className={`rounded-2xl border p-4 ${status?.completed ? "border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/20" : "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20"}`}><div className="flex items-center gap-2 text-xs font-black text-slate-500"><CheckCircle2 size={16}/> השלמת הספירה</div><div className="mt-2 text-2xl font-black">{status?.completion_percent ?? 0}%</div><div className="mt-1 text-xs text-slate-500">{status?.counted_products_last_7_days ?? 0} מתוך {status?.active_products ?? 0} מוצרים</div></div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center gap-2 text-xs font-black text-slate-500"><Clock3 size={16}/> הספירה הבאה</div><div className="mt-2 text-lg font-black">{fmtDate(status?.next_due_date)}</div><div className="mt-1 text-xs text-slate-500">ברירת מחדל: יום ראשון בשעה {status?.count_time ?? "08:00"}</div></div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center gap-2 text-xs font-black text-slate-500"><TriangleAlert size={16}/> מצב</div><div className="mt-2 text-lg font-black">{status?.due ? "הספירה דורשת טיפול" : status?.completed ? "הספירה השבועית הושלמה" : "מתכוננים לספירה"}</div><div className="mt-1 text-xs text-slate-500">המערכת אינה מאפסת את המלאי; היא שומרת Snapshot חדש.</div></div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center gap-2 text-xs font-black text-slate-500"><Truck size={16}/> חגים פעילים</div><div className="mt-2 text-lg font-black">{upcoming.length} תקופות</div><div className="mt-1 text-xs text-slate-500">המכפיל וימי ההזמנה ניתנים להתאמה.</div></div>
    </div>
    {message && <div className="mx-4 mb-4 rounded-xl bg-indigo-50 p-3 text-sm font-bold text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">{message}</div>}
    {upcoming.length > 0 && <div className="border-t border-slate-200 p-4 dark:border-slate-800"><div className="mb-3 text-sm font-black">תקופות מיוחדות קרובות</div><div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">{upcoming.map((period: InventoryPlanningPeriod) => <div key={period.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-800"><div className="flex items-center justify-between gap-2"><span className="font-black">{period.name}</span><span className="rounded-full bg-amber-100 px-2 py-1 text-[11px] font-black text-amber-700">×{period.consumption_multiplier}</span></div><div className="mt-1 text-xs text-slate-500">{fmtDate(period.start_date)} – {fmtDate(period.end_date)}</div>{period.order_days || period.delivery_days ? <div className="mt-2 text-[11px] text-slate-500">הזמנה: {period.order_days || "רגיל"} · אספקה: {period.delivery_days || "רגיל"}</div> : null}</div>)}</div></div>}
    <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500 dark:border-slate-800">בתקופת חג התחזית מגדילה את הצריכה לפי המכפיל שהוגדר, והמערכת יכולה להקדים/לדחות את יום ההזמנה והאספקה לפי ימי הפעילות שהוגדרו.</div>
  </section>;
}
