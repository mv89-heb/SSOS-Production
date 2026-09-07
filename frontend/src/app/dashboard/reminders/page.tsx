"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bell, CalendarClock, CheckCircle2, Clock3, ShoppingBag } from "lucide-react";
import { orderService } from "@/services/order-service";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("he-IL", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function RemindersPage() {
  const { data: orders, isLoading, isError } = useQuery({
    queryKey: ["orders"],
    queryFn: () => orderService.getOrders(),
  });

  const reminders = useMemo(() => {
    return (orders ?? [])
      .filter((order) => order.next_reminder_at)
      .sort(
        (a, b) =>
          new Date(a.next_reminder_at!).getTime() -
          new Date(b.next_reminder_at!).getTime(),
      );
  }, [orders]);

  const due = reminders.filter(
    (order) => new Date(order.next_reminder_at!).getTime() <= Date.now(),
  );
  const upcoming = reminders.filter(
    (order) => new Date(order.next_reminder_at!).getTime() > Date.now(),
  );

  return (
    <div className="space-y-8 pb-8">
      <section>
        <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
          <Bell className="h-3.5 w-3.5" />
          מעקב והמשך טיפול
        </div>
        <h1 className="page-title">תזכורות</h1>
        <p className="page-subtitle">ריכוז הזמנות עם תזכורת למעקב, אישור או המשך טיפול.</p>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <SummaryCard icon={Clock3} label="דורשות טיפול" value={due.length} />
        <SummaryCard icon={CalendarClock} label="תזכורות עתידיות" value={upcoming.length} />
        <SummaryCard icon={CheckCircle2} label="סה״כ במעקב" value={reminders.length} />
      </section>

      <Card className="glass-card">
        <CardHeader className="border-b border-slate-100 dark:border-slate-800">
          <CardTitle className="text-base font-extrabold text-slate-950 dark:text-white">תזכורות פעילות</CardTitle>
        </CardHeader>
        <CardContent className="pt-3">
          {isLoading ? (
            <div className="space-y-3 py-6">
              {[1, 2, 3].map((item) => <div key={item} className="h-16 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}
            </div>
          ) : isError ? (
            <div className="py-10 text-center text-sm font-semibold text-red-600">לא ניתן לטעון את ההזמנות כרגע.</div>
          ) : reminders.length === 0 ? (
            <div className="py-14 text-center">
              <Bell className="mx-auto h-10 w-10 text-slate-300" />
              <p className="mt-3 text-sm font-bold text-slate-700 dark:text-slate-200">אין כרגע תזכורות פעילות</p>
              <p className="mt-1 text-xs text-slate-400">כאשר להזמנה תהיה תזכורת, היא תופיע כאן.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {reminders.map((order) => {
                const isDue = new Date(order.next_reminder_at!).getTime() <= Date.now();
                return (
                  <Link
                    key={order.id}
                    href={`/dashboard/orders/${order.id}`}
                    className="flex items-center justify-between gap-4 rounded-xl px-2 py-4 transition hover:bg-slate-50 dark:hover:bg-slate-800/60"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${isDue ? "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300" : "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300"}`}>
                        <ShoppingBag className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-extrabold text-slate-900 dark:text-white">{order.order_number}</div>
                        <div className="mt-0.5 truncate text-xs text-slate-400">{order.supplier_name}</div>
                      </div>
                    </div>
                    <div className="shrink-0 text-left">
                      <div className={`text-xs font-extrabold ${isDue ? "text-amber-700 dark:text-amber-300" : "text-slate-600 dark:text-slate-300"}`}>
                        {isDue ? "דורש טיפול" : "תזכורת הבאה"}
                      </div>
                      <div className="mt-1 text-xs text-slate-400">{formatDate(order.next_reminder_at)}</div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value }: { icon: typeof Bell; label: string; value: number }) {
  return (
    <Card className="glass-card">
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-500">{label}</div>
          <div className="mt-1 text-2xl font-black text-slate-950 dark:text-white">{value}</div>
        </div>
      </CardContent>
    </Card>
  );
}
