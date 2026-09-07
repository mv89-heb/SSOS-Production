"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useCompleteOrderReminder, useOpenReminders, useSnoozeOrderReminder } from "@/hooks/use-reminders";
import { Bell, CalendarClock, CheckCircle2, Clock3, ShoppingBag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function RemindersPage() {
  const { data: reminders = [], isLoading, isError, refetch } = useOpenReminders();
  const complete = useCompleteOrderReminder();
  const snooze = useSnoozeOrderReminder();
  const busy = complete.isPending || snooze.isPending;
  const ordered = useMemo(() => [...reminders].sort((a, b) => {
    const aTime = a.next_reminder_at ? new Date(a.next_reminder_at).getTime() : Number.MAX_SAFE_INTEGER;
    const bTime = b.next_reminder_at ? new Date(b.next_reminder_at).getTime() : Number.MAX_SAFE_INTEGER;
    return aTime - bTime;
  }), [reminders]);
  const due = ordered.filter((item) => item.next_reminder_at && new Date(item.next_reminder_at).getTime() <= Date.now());
  const upcoming = ordered.filter((item) => item.next_reminder_at && new Date(item.next_reminder_at).getTime() > Date.now());

  return (
    <div className="space-y-8 pb-8">
      <section>
        <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"><Bell className="h-3.5 w-3.5" /> מעקב והמשך טיפול</div>
        <h1 className="page-title">תזכורות</h1>
        <p className="page-subtitle">כאן רואים הזמנות שצריך לחזור אליהן. המערכת משתמשת בכללי הספק כשיש כאלה, ובאין כללים יוצרת תזכורת חד-פעמית.</p>
      </section>

      <Card className="glass-card border-indigo-100 dark:border-indigo-900/50">
        <CardContent className="flex flex-col gap-2 p-4 text-sm text-slate-600 dark:text-slate-300 md:flex-row md:items-center md:gap-4">
          <Bell className="h-5 w-5 shrink-0 text-indigo-600" />
          <p><span className="font-extrabold text-slate-900 dark:text-white">איך זה עובד?</span> מפעילים תזכורת מתוך הזמנה פתוחה. אם לספק יש ימי הזמנה/אספקה, המערכת מחשבת את מועד המעקב הבא. אם אין כללים, ההפעלה יוצרת תזכורת חד-פעמית לעוד שעה, כדי שההזמנה לא תיעלם מהמעקב. אפשר לפתוח את ההזמנה, לדחות או לסמן שטיפלת.</p>
        </CardContent>
      </Card>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <SummaryCard icon={Clock3} label="דורשות טיפול" value={due.length} />
        <SummaryCard icon={CalendarClock} label="תזכורות עתידיות" value={upcoming.length} />
        <SummaryCard icon={CheckCircle2} label="סה״כ במעקב" value={ordered.length} />
      </section>

      <Card className="glass-card">
        <CardHeader className="border-b border-slate-100 dark:border-slate-800"><CardTitle className="text-base font-extrabold text-slate-950 dark:text-white">תזכורות פעילות</CardTitle></CardHeader>
        <CardContent className="pt-3">
          {isLoading ? <div className="space-y-3 py-6">{[1,2,3].map((item) => <div key={item} className="h-20 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}</div>
            : isError ? <div className="py-10 text-center"><p className="text-sm font-semibold text-red-600">לא ניתן לטעון את התזכורות כרגע.</p><button onClick={() => refetch()} className="mt-3 text-xs font-bold text-indigo-600 hover:underline">נסה שוב</button></div>
            : ordered.length === 0 ? <div className="py-14 text-center"><Bell className="mx-auto h-10 w-10 text-slate-300" /><p className="mt-3 text-sm font-bold text-slate-700 dark:text-slate-200">אין כרגע תזכורות פעילות</p><p className="mt-1 text-xs text-slate-400">פתח הזמנה שעדיין בטיפול ולחץ על ״הפעל תזכורת״. גם בלי כללי ספק תיווצר תזכורת חד-פעמית לעוד שעה.</p></div>
            : <div className="divide-y divide-slate-100 dark:divide-slate-800">{ordered.map(({ order, next_reminder_at }) => {
              const isDue = !!next_reminder_at && new Date(next_reminder_at).getTime() <= Date.now();
              const mode = order.reminder_rules_snapshot?.mode === "manual_fallback" ? "ידנית" : "לפי כללי ספק";
              return <div key={order.id} className="flex flex-col gap-4 px-2 py-4 transition hover:bg-slate-50 dark:hover:bg-slate-800/60 md:flex-row md:items-center md:justify-between">
                <Link href={`/dashboard/orders/${order.id}`} className="flex min-w-0 items-center gap-3 md:flex-1">
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${isDue ? "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300" : "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300"}`}><ShoppingBag className="h-5 w-5" /></div>
                  <div className="min-w-0"><div className="truncate text-sm font-extrabold text-slate-900 dark:text-white">{order.order_number}</div><div className="mt-0.5 truncate text-xs text-slate-400">{order.supplier_name}</div><div className="mt-1 text-xs text-slate-400">{mode} · {isDue ? "הגיע מועד המעקב" : `מועד: ${formatDate(next_reminder_at)}`}</div></div>
                </Link>
                <div className="flex flex-wrap items-center gap-2 md:justify-end">
                  <span className={`text-xs font-extrabold ${isDue ? "text-amber-700 dark:text-amber-300" : "text-slate-600 dark:text-slate-300"}`}>{isDue ? "דורש טיפול" : "ממתין"}</span>
                  <Button variant="secondary" className="min-h-9 px-3 py-1.5 text-xs" disabled={busy} onClick={() => snooze.mutate({ orderId: order.id, minutes: 60 })}>+ שעה</Button>
                  <Button className="min-h-9 px-3 py-1.5 text-xs" disabled={busy} onClick={() => complete.mutate(order.id)}>טופל</Button>
                  <Link href={`/dashboard/orders/${order.id}`} className="text-xs font-bold text-indigo-600 hover:underline">פתח הזמנה</Link>
                </div>
              </div>;
            })}</div>}
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value }: { icon: typeof Bell; label: string; value: number }) {
  return <Card className="glass-card"><CardContent className="flex items-center gap-4 p-5"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300"><Icon className="h-5 w-5" /></div><div><div className="text-xs font-semibold text-slate-500">{label}</div><div className="mt-1 text-2xl font-black text-slate-950 dark:text-white">{value}</div></div></CardContent></Card>;
}
