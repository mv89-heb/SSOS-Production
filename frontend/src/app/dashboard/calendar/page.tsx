"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Bell, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, ExternalLink,
  Pencil, Plus, RefreshCw, Send, ShoppingCart, X
} from "lucide-react";
import { useRouter } from "next/navigation";
import { orderService } from "@/services/order-service";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Order } from "@/types";

type Holiday = { date: string; hebrew: string; title: string; category?: string; link?: string };
type CalendarDay = { date: Date; key: string; gregorian: string; hebrew: string; holiday?: Holiday; orders: Order[]; reminders: any[] };

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
      date: item.date, hebrew: item.hdate ?? "", title: item.hebrew || item.title, category: item.category, link: item.link,
    }));
  });
}

function orderCalendarDate(order: Order) {
  return order.planned_order_date || (order.created_at ? isoDay(new Date(order.created_at)) : null);
}

function statusLabel(status: Order["status"]) {
  return ({ draft: "טיוטה", submitted: "ממתינה לאישור", approved: "מאושרת", sent: "נשלחה", completed: "הושלמה", cancelled: "בוטלה" })[status];
}

export default function CalendarPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

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

  const lifecycle = useMutation({
    mutationFn: async ({ action, id }: { action: "submit" | "approve" | "sent" | "complete"; id: number }) => {
      if (action === "submit") return orderService.submitOrder(id);
      if (action === "approve") return orderService.approveOrder(id);
      if (action === "sent") return orderService.markSent(id);
      return orderService.markCompleted(id);
    },
    onSuccess: async () => {
      setActionError(null);
      await qc.invalidateQueries({ queryKey: ["calendar-orders"] });
    },
    onError: (error) => setActionError(error instanceof Error ? error.message : "הפעולה נכשלה."),
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
      const matchingOrders = allOrders.filter((order) => orderCalendarDate(order) === key);
      const reminders = allOrders.flatMap((order) => {
        const reminder = parseLocalDate(order.next_reminder_at);
        if (!reminder || isoDay(reminder) !== key || order.reminder_state === "complete") return [];
        return [{ order, due: reminder.getTime() <= Date.now(), time: new Intl.DateTimeFormat("he-IL", { hour: "2-digit", minute: "2-digit" }).format(reminder) }];
      });
      result.push({ date, key, gregorian: new Intl.DateTimeFormat("he-IL", { day: "numeric", month: "short" }).format(date), hebrew: hebrewDate(date), holiday: holidayMap.get(key), orders: matchingOrders, reminders });
    }
    return result;
  }, [cursor, holidays.data, orders.data]);

  const todayKey = isoDay(new Date());
  const monthOrders = (orders.data ?? []).filter((o) => {
    const key = orderCalendarDate(o);
    return key?.startsWith(`${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}`);
  });
  const dueCount = monthOrders.filter((o) => o.reminder_state !== "complete" && o.next_reminder_at && new Date(o.next_reminder_at).getTime() <= Date.now()).length;

  return (
    <div className="space-y-6 pb-8" dir="rtl">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"><CalendarDays className="h-3.5 w-3.5" /> מרכז פעולות רכש</div>
          <h1 className="text-2xl font-black text-slate-950 dark:text-white">לוח רכש — תכנון ופעולות</h1>
          <p className="mt-1 text-sm text-slate-500">בחר יום כדי ליצור הזמנה, לפתוח הזמנה קיימת או לבצע את הפעולה הבאה שלה — בלי לצאת מהלוח.</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => router.push(`/dashboard/orders/new?planned_order_date=${todayKey}`)}><Plus className="h-4 w-4" /> הזמנה להיום</Button>
          <Button variant="secondary" onClick={() => orders.refetch()} disabled={orders.isFetching}><RefreshCw className={`h-4 w-4 ${orders.isFetching ? "animate-spin" : ""}`} /> רענן</Button>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard icon={ShoppingCart} label="הזמנות בחודש" value={monthOrders.length} />
        <StatCard icon={Bell} label="תזכורות" value={monthOrders.filter((o) => o.next_reminder_at).length} />
        <StatCard icon={AlertTriangle} label="דורשות טיפול" value={dueCount} />
        <StatCard icon={CalendarDays} label="ימי חג" value={(holidays.data ?? []).length} />
      </div>

      <Card className="overflow-hidden">
        <CardHeader className="border-b border-slate-100 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="flex items-center gap-3 text-base font-black"><CalendarDays className="h-5 w-5 text-indigo-600" /> {monthTitle(cursor)} <span className="text-xs font-bold text-slate-400">· {new Intl.DateTimeFormat("he-IL-u-ca-hebrew", { month: "long", year: "numeric" }).format(cursor)}</span></CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" className="h-9 px-3" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}><ChevronRight className="h-4 w-4" /> קודם</Button>
              <Button variant="outline" className="h-9 px-3" onClick={() => { const now = new Date(); setCursor(new Date(now.getFullYear(), now.getMonth(), 1)); }}>היום</Button>
              <Button variant="outline" className="h-9 px-3" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>הבא <ChevronLeft className="h-4 w-4" /></Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {orders.isError ? <div className="p-12 text-center text-sm font-bold text-red-600">לא ניתן לטעון את ההזמנות.</div> : (
            <div className="overflow-x-auto">
              <div className="min-w-[820px]">
                <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50 text-center text-xs font-black text-slate-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                  {["ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳", "א׳"].map((d) => <div key={d} className="py-3">{d}</div>)}
                </div>
                <div className="grid grid-cols-7">
                  {days.map((day) => <CalendarCell key={day.key} day={day} today={day.key === todayKey} onClick={() => { setActionError(null); setSelectedDay(day); }} />)}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="text-xs text-slate-400">הזמנה עם תאריך מתוכנן מוצגת ביום המתוכנן; הזמנות ישנות ללא תאריך מתוכנן מוצגות ביום יצירתן.</div>

      {selectedDay && (
        <DayActions
          day={selectedDay}
          actionError={actionError}
          busy={lifecycle.isPending}
          onClose={() => setSelectedDay(null)}
          onCreate={() => router.push(`/dashboard/orders/new?planned_order_date=${selectedDay.key}`)}
          onAction={(action, id) => lifecycle.mutate({ action, id })}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <LegendCard icon={ShoppingCart} title="הזמנה מתוכננת" text="היום שנבחר בעת יצירת ההזמנה." />
        <LegendCard icon={Bell} title="מועד מעקב" text="תזכורת פעילה שמגיעה מהזמנת הרכש." />
        <LegendCard icon={CalendarDays} title="חג / מועד" text="מועדים לועזיים ועבריים נמשכים מ-Hebcal." />
      </div>

      <div className="text-xs text-slate-400">
        מקור מועדי החגים: Hebcal
        {holidays.data?.find((h) => h.link)?.link && <><span> · </span><a href={holidays.data.find((h) => h.link)?.link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-bold text-indigo-500 hover:underline">פרטי המועד <ExternalLink className="h-3 w-3" /></a></>}
      </div>
    </div>
  );
}

function CalendarCell({ day, today, onClick }: { day: CalendarDay; today: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`min-h-[128px] border-b border-l border-slate-100 p-2.5 text-right align-top transition hover:bg-indigo-50/60 dark:border-slate-800 dark:hover:bg-indigo-950/30 ${today ? "bg-indigo-50/70 dark:bg-indigo-950/20" : "bg-white dark:bg-slate-900"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-black ${today ? "bg-indigo-600 text-white" : "text-slate-700 dark:text-slate-200"}`}>{day.date.getDate()}</div>
        <div className="text-left text-[10px] font-semibold text-slate-400">{day.hebrew}</div>
      </div>
      {day.holiday && <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] font-extrabold text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">🎉 {day.holiday.title}</div>}
      <div className="mt-2 space-y-1">
        {day.orders.slice(0, 3).map((order) => <div key={order.id} className="flex items-center gap-1.5 truncate rounded-md bg-sky-50 px-2 py-1 text-[11px] font-bold text-sky-700 dark:bg-sky-950/40 dark:text-sky-300"><ShoppingCart className="h-3 w-3 shrink-0" /> {order.order_number} · {order.supplier_name}</div>)}
        {day.reminders.slice(0, 2).map((item) => <div key={`${item.order.id}-reminder`} className={`flex items-center gap-1.5 truncate rounded-md px-2 py-1 text-[11px] font-bold ${item.due ? "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300" : "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300"}`}><Bell className="h-3 w-3 shrink-0" /> {item.order.order_number} · {item.time}</div>)}
        {!day.orders.length && !day.reminders.length && <div className="mt-5 text-center text-[10px] font-bold text-slate-300">לחץ להוספת פעולה</div>}
      </div>
    </button>
  );
}

function DayActions({ day, onClose, onCreate, onAction, actionError, busy }: { day: CalendarDay; onClose: () => void; onCreate: () => void; onAction: (action: "submit" | "approve" | "sent" | "complete", id: number) => void; actionError: string | null; busy: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-t-3xl bg-white p-5 shadow-2xl dark:bg-slate-950 sm:rounded-3xl">
        <div className="flex items-start justify-between gap-3">
          <div><div className="text-xs font-bold text-slate-400">{day.gregorian}</div><h2 className="mt-1 text-xl font-black">פעולות ליום {day.date.getDate()}</h2><div className="mt-1 text-xs text-slate-500">{day.hebrew}</div></div>
          <button onClick={onClose} className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800"><X size={18}/></button>
        </div>

        <Button onClick={onCreate} className="mt-5 w-full justify-center"><Plus size={17}/> צור הזמנה ליום הזה</Button>

        {day.orders.length > 0 && <div className="mt-5 space-y-3">
          <h3 className="text-sm font-black">הזמנות ביום</h3>
          {day.orders.map((order) => <OrderActionCard key={order.id} order={order} onAction={onAction} busy={busy} />)}
        </div>}

        {day.reminders.length > 0 && <div className="mt-5 rounded-2xl bg-violet-50 p-4 dark:bg-violet-950/20"><div className="flex items-center gap-2 text-sm font-black text-violet-700 dark:text-violet-300"><Bell size={16}/> תזכורות</div>{day.reminders.map((item) => <Link key={`${item.order.id}-r`} href={`/dashboard/orders/${item.order.id}`} className="mt-2 block text-xs font-bold text-violet-700 hover:underline">{item.order.order_number} · {item.time} — פתיחת ההזמנה</Link>)}</div>}

        {actionError && <div className="mt-4 rounded-2xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-300">{actionError}</div>}
      </div>
    </div>
  );
}

function OrderActionCard({ order, onAction, busy }: { order: Order; onAction: (action: "submit" | "approve" | "sent" | "complete", id: number) => void; busy: boolean }) {
  const action = order.status === "draft" ? "submit" : order.status === "submitted" ? "approve" : order.status === "approved" ? "sent" : order.status === "sent" ? "complete" : null;
  const actionText = order.status === "draft" ? "שלח לאישור" : order.status === "submitted" ? "אשר הזמנה" : order.status === "approved" ? "סמן כנשלחה" : order.status === "sent" ? "סמן כהושלמה" : null;
  return <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0"><div className="font-black">{order.order_number}</div><div className="mt-1 text-xs text-slate-500">{order.supplier_name} · {statusLabel(order.status)}</div></div>
      <div className="text-left text-sm font-black">{order.final_total.toLocaleString("he-IL")} {order.currency}</div>
    </div>
    <div className="mt-3 flex flex-wrap gap-2">
      <Link href={`/dashboard/orders/${order.id}`} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 px-3 text-xs font-black dark:border-slate-700"><Pencil size={15}/> פתיחה</Link>
      {action && <button disabled={busy} onClick={() => onAction(action, order.id)} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-indigo-600 px-3 text-xs font-black text-white disabled:opacity-50"><Send size={15}/> {busy ? "מבצע..." : actionText}</button>}
      {order.status === "completed" && <span className="inline-flex items-center gap-1 rounded-xl bg-emerald-50 px-3 text-xs font-black text-emerald-700"><CheckCircle2 size={15}/> הושלמה</span>}
    </div>
  </div>;
}

function StatCard({ icon: Icon, label, value }: { icon: typeof CalendarDays; label: string; value: number }) {
  return <Card><CardContent className="flex items-center gap-3 p-4"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-300"><Icon className="h-5 w-5" /></div><div><div className="text-xs font-bold text-slate-500">{label}</div><div className="mt-0.5 text-xl font-black text-slate-950 dark:text-white">{value}</div></div></CardContent></Card>;
}

function LegendCard({ icon: Icon, title, text }: { icon: typeof CalendarDays; title: string; text: string }) {
  return <Card><CardContent className="flex gap-3 p-4"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"><Icon className="h-5 w-5" /></div><div><div className="text-sm font-black text-slate-900 dark:text-white">{title}</div><p className="mt-1 text-xs text-slate-500">{text}</p></div></CardContent></Card>;
}
