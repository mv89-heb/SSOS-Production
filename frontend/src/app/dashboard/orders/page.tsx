"use client";

import Link from "next/link";
import { useDeferredValue, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { orderService } from "@/services/order-service";
import { OrderStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AlertCircle, ArrowLeft, Bell, CheckCircle2, Clock3, Download, PackageCheck, Plus, Search, Send, ShoppingCart, XCircle } from "lucide-react";

const STATUS_FILTERS = [
  { value: "all", label: "הכול" },
  { value: "approved", label: "אושרו" },
  { value: "cancelled", label: "בוטלו" },
  { value: "completed", label: "הושלמו" },
  { value: "draft", label: "טיוטות" },
  { value: "submitted", label: "ממתינות לאישור" },
  { value: "sent", label: "אצל הספק" },
] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number]["value"];
type StatusTone = "amber" | "emerald" | "sky" | "violet" | "red";
type StatusSummaryProps = {
  label: string;
  value: number;
  icon: typeof Clock3;
  tone: StatusTone;
  active: boolean;
  onClick: () => void;
};

const TONE_CLASSES: Record<StatusTone, string> = {
  amber: "bg-amber-50 text-amber-600 dark:bg-amber-950/40",
  emerald: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40",
  sky: "bg-sky-50 text-sky-600 dark:bg-sky-950/40",
  violet: "bg-violet-50 text-violet-600 dark:bg-violet-950/40",
  red: "bg-red-50 text-red-600 dark:bg-red-950/40",
};

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function formatReminder(value: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("he-IL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function StatusSummary({ label, value, icon: Icon, tone, active, onClick }: StatusSummaryProps) {
  return (
    <button type="button" onClick={onClick} className={`text-right rounded-2xl border p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${active ? "border-indigo-300 ring-2 ring-indigo-100 dark:border-indigo-700 dark:ring-indigo-950" : "border-slate-200/80 dark:border-slate-800"} bg-white dark:bg-slate-900`}>
      <div className="flex items-center justify-between gap-3">
        <div><p className="text-xs font-bold text-slate-400">{label}</p><p className="mt-1 text-2xl font-extrabold text-slate-900 dark:text-white">{value}</p></div>
        <div className={`rounded-xl p-2.5 ${TONE_CLASSES[tone]}`}><Icon size={18} /></div>
      </div>
    </button>
  );
}

export default function OrdersPage() {
  const { data: orders } = useQuery({ queryKey: ["orders"], queryFn: () => orderService.getOrders() });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [page, setPage] = useState(0);
  const deferredSearch = useDeferredValue(search.trim());
  const pageSize = 50;
  const { data: searchResult, isLoading, isError, refetch } = useQuery({
    queryKey: ["orders", "search", deferredSearch, status, startDate, endDate, page],
    queryFn: () => orderService.searchOrders({
      q: deferredSearch || undefined,
      status: status === "all" ? undefined : status,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      limit: pageSize,
      offset: page * pageSize,
    }),
    placeholderData: (previousData) => previousData,
  });
  const filteredOrders = useMemo(() => searchResult?.orders ?? [], [searchResult]);
  const count = (value: string) => (orders ?? []).filter((order) => order.status === value).length;
  const hasFilters = Boolean(search.trim()) || status !== "all" || Boolean(startDate) || Boolean(endDate);
  const totalResults = searchResult?.pagination.total ?? 0;
  const hasPreviousPage = page > 0;
  const hasNextPage = Boolean(searchResult?.pagination.has_more);
  const changeStatus = (value: StatusFilter) => { setStatus(value); setPage(0); };
  const clearFilters = () => { setSearch(""); setStartDate(""); setEndDate(""); changeStatus("all"); };
  const handleExport = async () => {
    setIsExporting(true);
    setExportError("");
    try {
      const blob = await orderService.exportOrders({
        q: search.trim() || undefined,
        status: status === "all" ? undefined : status,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `orders-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    } catch {
      setExportError("הייצוא נכשל. אם יש יותר מ־5,000 הזמנות, צמצם את החיפוש או את טווח התאריכים.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">הזמנות רכש</h1>
            {orders && <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">{orders.length} הזמנות</span>}
          </div>
          <p className="mt-1 text-sm text-slate-500">מרכז העבודה לניהול, מעקב ואישור הזמנות.</p>
        </div>
        <Link href="/dashboard/orders/new"><Button className="shadow-sm"><Plus size={16} /> הזמנה חדשה</Button></Link>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <StatusSummary label="ממתינות לאישור" value={count("submitted")} icon={Clock3} tone="amber" active={status === "submitted"} onClick={() => changeStatus("submitted")} />
        <StatusSummary label="אושרו" value={count("approved")} icon={CheckCircle2} tone="emerald" active={status === "approved"} onClick={() => changeStatus("approved")} />
        <StatusSummary label="אצל הספק" value={count("sent")} icon={Send} tone="sky" active={status === "sent"} onClick={() => changeStatus("sent")} />
        <StatusSummary label="הושלמו" value={count("completed")} icon={PackageCheck} tone="violet" active={status === "completed"} onClick={() => changeStatus("completed")} />
        <StatusSummary label="בוטלו" value={count("cancelled")} icon={XCircle} tone="red" active={status === "cancelled"} onClick={() => changeStatus("cancelled")} />
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-100 p-3 dark:border-slate-800">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <Input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="חיפוש חופשי: הזמנה, ספק, מוצר, מק״ט, הערות, מחלקה או פרויקט..." className="h-10 pr-9" />
            </div>
            <Button type="button" variant="secondary" onClick={handleExport} disabled={isExporting || totalResults === 0} loading={isExporting} className="shrink-0">
              <Download size={15} /> ייצוא CSV
            </Button>
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {STATUS_FILTERS.map((filter) => <button key={filter.value} type="button" onClick={() => changeStatus(filter.value)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-bold transition ${status === filter.value ? "bg-indigo-600 text-white shadow-sm" : "bg-slate-50 text-slate-500 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300"}`}>{filter.label}</button>)}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:max-w-md">
            <label className="flex flex-col gap-1 text-xs font-bold text-slate-500">
              מתאריך
              <input type="date" value={startDate} max={endDate || undefined} onChange={(event) => { setStartDate(event.target.value); setPage(0); }} className="h-10 min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:ring-indigo-950" />
            </label>
            <label className="flex flex-col gap-1 text-xs font-bold text-slate-500">
              עד תאריך
              <input type="date" value={endDate} min={startDate || undefined} onChange={(event) => { setEndDate(event.target.value); setPage(0); }} className="h-10 min-w-0 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:ring-indigo-950" />
            </label>
          </div>
          {hasFilters && <div className="mt-2 flex items-center justify-between px-1 text-xs"><span className="text-slate-400">נמצאו {totalResults.toLocaleString("he-IL")} הזמנות</span><button type="button" onClick={clearFilters} className="font-bold text-indigo-600 hover:underline">נקה סינון</button></div>}
          {exportError && <p role="alert" className="mt-2 px-1 text-xs font-semibold text-red-600">{exportError}</p>}
        </div>

        {isError ? (
          <div className="flex flex-col items-center justify-center gap-3 p-12 text-center"><div className="rounded-2xl bg-red-50 p-3 text-red-500 dark:bg-red-950/30"><AlertCircle size={28} /></div><p className="font-bold text-slate-800 dark:text-white">לא הצלחנו לטעון את ההזמנות</p><p className="text-sm text-slate-500">בדוק את החיבור ונסה שוב.</p><Button variant="secondary" onClick={() => refetch()}>נסה שוב</Button></div>
        ) : isLoading ? (
          <div className="space-y-3 p-4">{[1,2,3,4,5].map((row) => <div key={row} className="h-16 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}</div>
        ) : filteredOrders.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-14 text-center"><div className="mb-4 rounded-2xl bg-slate-100 p-4 text-slate-400 dark:bg-slate-800"><ShoppingCart size={28} /></div><h2 className="font-bold text-slate-800 dark:text-white">{hasFilters ? "לא נמצאו הזמנות תואמות" : "אין הזמנות עדיין"}</h2><p className="mt-1 text-sm text-slate-500">{hasFilters ? "נסה לשנות את החיפוש או הסינון." : "צור את ההזמנה הראשונה כדי להתחיל."}</p>{hasFilters ? <Button variant="secondary" className="mt-4" onClick={clearFilters}>נקה סינון</Button> : <Link href="/dashboard/orders/new" className="mt-4"><Button><Plus size={16} /> הזמנה חדשה</Button></Link>}</div>
        ) : (
          <>
            <div className="grid gap-3 p-3 md:hidden">
              {filteredOrders.map((order) => {
                const reminderAt = formatReminder(order.next_reminder_at);
                const reminderDue = !!order.next_reminder_at && new Date(order.next_reminder_at).getTime() <= Date.now() && order.reminder_state !== "complete";
                return (
                  <article key={order.id} className="min-w-0 rounded-xl border border-slate-200 p-4 shadow-sm dark:border-slate-800">
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <div className="min-w-0">
                        <Link href={`/dashboard/orders/${order.id}`} className="break-words font-extrabold text-indigo-600 hover:underline dark:text-indigo-400">{order.order_number}</Link>
                        <p className="mt-1 break-words text-sm font-semibold text-slate-700 dark:text-slate-200">{order.supplier_name}</p>
                      </div>
                      <div className="shrink-0"><OrderStatusBadge status={order.status} /></div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 text-sm dark:border-slate-800">
                      <div className="min-w-0"><p className="text-xs text-slate-500">סה״כ</p><p className="mt-1 break-words font-extrabold text-slate-900 dark:text-white">{order.currency} {order.final_total.toLocaleString("he-IL")}</p></div>
                      <div className="min-w-0"><p className="text-xs text-slate-500">נוצר בתאריך</p><p className="mt-1 text-slate-700 dark:text-slate-200">{formatDate(order.created_at)}</p></div>
                      <div className="col-span-2 min-w-0"><p className="text-xs text-slate-500">תזכורת</p>{order.reminder_state !== "complete" && reminderAt ? <p className={`mt-1 break-words text-xs font-bold ${reminderDue ? "text-amber-700 dark:text-amber-300" : "text-indigo-700 dark:text-indigo-300"}`}>{reminderDue ? "דורשת טיפול" : reminderAt}</p> : <p className="mt-1 text-xs text-slate-400">אין תזכורת</p>}</div>
                    </div>
                    <Link href={`/dashboard/orders/${order.id}`} className="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg bg-indigo-50 px-3 py-2 text-sm font-bold text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-950/70">פתיחת הזמנה <ArrowLeft size={15} /></Link>
                  </article>
                );
              })}
            </div>
            <div dir="rtl" className="hidden w-full min-w-0 max-w-full overflow-x-auto overscroll-x-contain md:block">
              <table dir="rtl" className="w-max min-w-[950px] text-right text-sm">
              <thead className="border-b border-slate-100 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-950/40"><tr>{["מס' הזמנה", "ספק", "סטטוס", "תזכורת", "סה\"כ", "נוצר בתאריך", ""].map((heading, index) => <th key={heading || index} className="px-5 py-3 text-xs font-extrabold text-slate-500">{heading}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredOrders.map((order) => {
                  const reminderAt = formatReminder(order.next_reminder_at);
                  const reminderDue = !!order.next_reminder_at && new Date(order.next_reminder_at).getTime() <= Date.now() && order.reminder_state !== "complete";
                  return (
                    <tr key={order.id} className="group transition-colors hover:bg-indigo-50/40 dark:hover:bg-slate-800/60">
                      <td className="px-5 py-4"><Link href={`/dashboard/orders/${order.id}`} className="font-extrabold text-indigo-600 hover:text-indigo-700 hover:underline dark:text-indigo-400">{order.order_number}</Link></td>
                      <td className="px-5 py-4 font-medium text-slate-700 dark:text-slate-200">{order.supplier_name}</td>
                      <td className="px-5 py-4"><OrderStatusBadge status={order.status} /></td>
                      <td className="px-5 py-4">
                        {order.reminder_state !== "complete" && reminderAt ? (
                          <Link href={`/dashboard/orders/${order.id}`} className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold ${reminderDue ? "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300" : "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"}`}>
                            <Bell size={13} /> {reminderDue ? "דורשת טיפול" : reminderAt}
                          </Link>
                        ) : <span className="text-xs text-slate-400">אין תזכורת</span>}
                      </td>
                      <td className="px-5 py-4 font-bold text-slate-800 dark:text-slate-100">{order.currency} {order.final_total.toLocaleString("he-IL")}</td>
                      <td className="px-5 py-4 text-sm text-slate-500">{formatDate(order.created_at)}</td>
                      <td className="px-5 py-4"><Link href={`/dashboard/orders/${order.id}`} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-bold text-slate-500 opacity-70 transition hover:bg-white hover:text-indigo-600 hover:opacity-100 dark:hover:bg-slate-900">פרטים <ArrowLeft size={13} /></Link></td>
                    </tr>
                  );
                })}
              </tbody>
              </table>
            </div>
            {searchResult && (
              <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3 text-sm dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-slate-500">
                  מציג {totalResults === 0 ? 0 : page * pageSize + 1}–{Math.min((page + 1) * pageSize, totalResults)} מתוך {totalResults.toLocaleString("he-IL")} הזמנות
                </span>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" disabled={!hasPreviousPage} onClick={() => setPage((current) => Math.max(0, current - 1))}>הקודם</Button>
                  <span className="min-w-16 text-center text-xs font-bold text-slate-500">עמוד {page + 1}</span>
                  <Button variant="secondary" disabled={!hasNextPage} onClick={() => setPage((current) => current + 1)}>הבא</Button>
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
