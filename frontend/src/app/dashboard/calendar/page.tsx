"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Bell, CalendarDays, ExternalLink, PackageCheck, ShoppingCart, RefreshCw, AlertTriangle } from "lucide-react";
import { orderService } from "@/services/order-service";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Holiday = { date: string; hebrew: string; title: string; category?: string; link?: string };
type CalendarDay = { date: Date; key: string; gregorian: string; hebrew: string; holiday?: Holiday; orders: any[]; reminders: any[] };

const HEBREW_MONTHS: Record<string, string> = {
  Tishrei: "תשרי", Cheshvan: "חשוון", Kislev: "כסלו", Tevet: "טבת", Shevat: "שבט",
  Adar: "אדר", "Adar I": "אדר א׳", "Adar II": "אדר ב׳", Nisan: "ניסן", Iyar: "אייר",
  Sivan: "סיוון", Tammuz: "תמוז", Av: "אב", Elul: "אלול",
};

function isoDay(date: Date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function parseLocalDate(value: string | null | undefined) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function hebrewDate(date: Date) {
  const parts = new Intl.DateTimeFormat("he-IL-u-ca-hebrew", { day: "numeric", month: "long", year: "numeric" }).formatToParts(date);
  const day = parts.find((p) => p.type === "day")?.value ?? "";
  const monthRaw = parts.find((p) => p.type === "month")?.value ?? "";
  const year = parts.find((p) => p.type === "year")?.value ?? "";
  const month = Object.entries(HEBREW_MONTHS).find(([en, he]) => monthRaw === en || monthRaw === he)?.[1] ?? monthRaw;
  return `${day} ${month} ${year}`;
}

function monthTitle(date: Date) {
  return new Intl.DateTimeFormat("he-IL", { month: "long", year: "numeric" }).format(date);
}

function fetchHolidays(date: Date): Promise<Holiday[]> {
  const start = new Date(date.getFullYear(), date.getMonth(), 1);
  const end = new Date(date.getFullYear(), date.getMonth() + 1, 0);
  const url = new URL("https://www.hebcal.com/hebcal");
  url.searchParams.set("v", "1");
  url.searchParams.set("cfg", "json");
  url.searchParams.set("start", isoDay(start));
  url.searchParams.set("end", isoDay(end));
  url.searchParams.set("lg", "he");
  url.searchParams.set("maj", "on");
  url.searchParams.set("min", "on");
  url.searchParams.set("mod", "on");
  url.searchParams.set("nx", "on");
  url.searchParams.set("mf", "on");
  url.searchParams.set("ss", "on");
  url.searchParams.set("hdp", "on");
  return fetch(url.toString(), { cache: "no-store" }).then(async (response) => {
    if (!response.ok) throw new Error("holiday_fetch_failed");
    const data = await response.json();
    return (data.items ?? []).filter((item: any) => item.date && item.title).map((item: any) => ({
      date: item.date,
      hebrew: item.hdate ?? "",
      title: item.hebrew || item.title,
      category: item.category,
      link: item.link,
    }));
  });
}

function CalendarCell({ day, today }: { day: CalendarDay; today: boolean }) {
  const importantReminder = day.reminders.some((r) => r.due);
  return (
    <div className={`min-h-[128px] border-b border-l border-slate-100 p-2.5 dark:border-slate-800 ${today ? "bg-indigo-50/70 dark:bg-indigo-950/20" : "bg-white dark:bg-slate-900"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-black ${today ? "bg-indigo-600 text-white" : "text-slate-700 dark:text-slate-200"}`}>
          {day.date.getDate()}
        </div>
        <div className="text-left text-[10px] font-semibold text-slate-400">{day.hebrew}</div>
      </div>

      {day.holiday && (
        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] font-extrabold text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300" title={day.holiday.hebrew}>
          🎉 {day.holiday.title}
        </div>
      )}

      <div className="mt-2 space-y-1">
        {day.orders.slice(0, 3).map((order) => (
          <Link key={order.id} href={`/dashboard/orders/${order.id}`} className="flex items-center gap-1.5 truncate rounded-md bg-sky-50 px-2 py-1 text-[11px] font-bold text-sky-700 hover:bg-sky-100 dark:bg-sky-950/40 dark:text-sky-300">
            <ShoppingCart className="h-3 w-3 shrink-0" /> {order.order_number} · {order.supplier_name}
          </Link>
        ))}
        {day.reminders.slice(0, 3).map((item) => (
          <Link key={`${item.order.id}-reminder`} href={`/dashboard/orders/${item.order.id}`} className={`flex items-center gap-1.5 truncate rounded-md px-2 py-1 text-[11px] font-bold ${item.due || importantReminder ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" : "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300"}`}>
            <Bell className="h-3 w-3 shrink-0" /> {item.order.order_number} · {item.time}
          </Link>
        ))}
        {day.orders.length + day.reminders.length > 6 && <div className="px-2 text-[10px] font-bold text-slate-400">+ עוד {day.orders.length + day.reminders.length - 6}</div>}
      </div>
    </div>
  );
}

export default function CalendarPage() {
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const orders = useQuery({
    queryKey: ["calendar-orders"],
    queryFn: () => orderService.getOrders(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const holidays = useQuery({
    queryKey: ["calendar-holidays", cursor.getFullYear(), cursor.getMonth() + 1],
    queryFn: () => fetchHolidays(cursor),
    staleTime: 6 * 60 * 60 * 1000,
  });

  const days = useMemo<CalendarDay[]>(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const last = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
    const startOffset = (first.getDay() + 6) % 7;
    const total = Math.ceil((startOffset + last.getDate()) / 7) * 7;
    const holidayMap = new Map((holidays.data ?? []).map((h) => [h.date, h]));
    const allOrders = orders.data ?? [];
    const result: CalendarDay[] = [];

    for (let i = 0; i < total; i++) {
      const date = new Date(cursor.getFullYear(), cursor.getMonth(), 1 - startOffset + i);
      const key = isoDay(date);
      const matchingOrders = allOrders.filter((order: any) => {
        const created = parseLocalDate(order.created_at);
        return created ? isoDay(created) === key : false;
      });
      const reminders = allOrders.flatMap((order: any) => {
        const reminder = parseLocalDate(order.next_reminder_at);
        if (!reminder || isoDay(reminder) !== key || order.reminder_state === "complete") return [];
        return [{ order, due: reminder.getTime() <= Date.now(), time: new Intl.DateTimeFormat("he-IL", { hour: "2-digit", minute: "2-digit" }).format(reminder) }];
      });
      result.push({
        date,
        key,
        gregorian: new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "short" }).format(date),
        hebrew: hebrewDate(date),
        holiday: holidayMap.get(key),
        orders: matchingOrders,
        reminders,
      });
    }
    return result;
  }, [cursor, holidays.data, orders.data]);

  const todayKey = isoDay(new Date());
  const monthOrders = (orders.data ?? []).filter((o: any) => {
    const d = parseLocalDate(o.next_reminder_at);
    return d && d.getFullYear() === cursor.getFullYear() && d.getMonth() === cursor.getMonth();
  });
  const dueCount = monthOrders.filter((o: any) => parseLocalDate(o.next_reminder_at)!.getTime() <= Date.now() && o.reminder_state !== "complete").length;
  const holidayCount = (holidays.data ?? []).length;

  return (
    <div className="space-y-6 pb-8" dir="rtl">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
            <CalendarDays className="h-3.5 w-3.5" /> לוח רכש חי
          </div>
          <h1 className="text-2xl font-black text-slate-950 dark:text-white">לוח שנה לועזי · עברי · חגים · הזמנות</h1>
          <p className="mt-1 text-sm text-slate-500">כל ההזמנות, מועדי המעקב והחגים במקום אחד. הנתונים מתרעננים אוטומטית כל דקה.</p>
        </div>
        <Button variant="secondary" onClick={() => orders.refetch()} disabled={orders.isFetching}>
          <RefreshCw className={`h-4 w-4 ${orders.isFetching ? "animate-spin" : ""}`} /> רענן עכשיו
        </Button>
      </section>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard icon={ShoppingCart} label="הזמנות במערכת" value={orders.data?.length ?? 0} />
        <StatCard icon={Bell} label="תזכורות בחודש" value={monthOrders.length} />
        <StatCard icon={AlertTriangle} label="תזכורות שדורשות טיפול" value={dueCount} />
        <StatCard icon={CalendarDays} label="מועדי חג בלוח" value={holidayCount} />
      </div>

      <Card className="overflow-hidden">
        <CardHeader className="border-b border-slate-100 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="flex items-center gap-3 text-base font-black">
              <CalendarDays className="h-5 w-5 text-indigo-600" />
              {monthTitle(cursor)}
              <span className="text-xs font-bold text-slate-400">· {new Intl.DateTimeFormat("he-IL-u-ca-hebrew", { month: "long", year: "numeric" }).format(cursor)}</span>
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" className="h-9 px-3" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}><ChevronRight className="h-4 w-4" /> קודם</Button>
              <Button variant="outline" className="h-9 px-3" onClick={() => { const now = new Date(); setCursor(new Date(now.getFullYear(), now.getMonth(), 1)); }}>היום</Button>
              <Button variant="outline" className="h-9 px-3" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>הבא <ChevronLeft className="h-4 w-4" /></Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {orders.isError ? <div className="p-12 text-center text-sm font-bold text-red-600">לא ניתן לטעון את ההזמנות. נסה לרענן.</div> : holidays.isError ? <div className="p-12 text-center text-sm text-amber-700">החגים לא נטענו כרגע. ההזמנות והתזכורות עדיין מוצגות.</div> : (
            <div className="overflow-x-auto">
              <div className="min-w-[980px]">
                <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50 text-center text-xs font-black text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                  {["ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳", "א׳"].map((d) => <div key={d} className="py-3">{d}</div>)}
                </div>
                <div className="grid grid-cols-7">
                  {days.map((day) => <CalendarCell key={day.key} day={day} today={day.key === todayKey} />)}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <LegendCard tone="sky" icon={ShoppingCart} title="הזמנה שנוצרה" text="מסומנת ביום שבו ההזמנה נוצרה." />
        <LegendCard tone="violet" icon={Bell} title="מועד מעקב" text="נלקח ישירות ממועד התזכורת הפעילה של ההזמנה." />
        <LegendCard tone="amber" icon={CalendarDays} title="חג / מועד" text="מועדים לועזיים ועבריים נמשכים מלוח Hebcal לחודש הנבחר." />
      </div>

      <div className="text-xs text-slate-400">
        <span>מקור מועדי החגים: Hebcal</span>
        {holidays.data?.some((h) => h.link) && <span> · </span>}
        {holidays.data?.find((h) => h.link)?.link && <a href={holidays.data.find((h) => h.link)?.link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-bold text-indigo-500 hover:underline">פרטי המועד <ExternalLink className="h-3 w-3" /></a>}
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value }: { icon: typeof CalendarDays; label: string; value: number }) {
  return <Card><CardContent className="flex items-center gap-3 p-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-300"><Icon className="h-5 w-5" /></div><div><div className="text-xs font-bold text-slate-500">{label}</div><div className="mt-0.5 text-xl font-black text-slate-950 dark:text-white">{value}</div></div></CardContent></Card>;
}

function LegendCard({ tone, icon: Icon, title, text: body }: { tone: "sky" | "violet" | "amber"; icon: typeof CalendarDays; title: string; text: string }) {
  const classes = { sky: "bg-sky-50 text-sky-700 dark:bg-sky-950/30 dark:text-sky-300", violet: "bg-violet-50 text-violet-700 dark:bg-violet-950/30 dark:text-violet-300", amber: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300" };
  return <Card><CardContent className="flex gap-3 p-4"><div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${classes[tone]}`}><Icon className="h-5 w-5" /></div><div><div className="text-sm font-black text-slate-900 dark:text-white">{title}</div><p className="mt-1 text-xs text-slate-500">{body}</p></div></CardContent></Card>;
}
