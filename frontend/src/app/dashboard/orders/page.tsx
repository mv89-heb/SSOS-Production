"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { orderService } from "@/services/order-service";
import { OrderStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AlertCircle, CheckCircle2, Clock3, PackageCheck, Plus, Search, Send, ShoppingCart } from "lucide-react";

const STATUS_FILTERS = [
  { value: "all", label: "הכול" },
  { value: "draft", label: "טיוטות" },
  { value: "submitted", label: "ממתינות לאישור" },
  { value: "approved", label: "אושרו" },
  { value: "sent", label: "אצל הספק" },
  { value: "completed", label: "הושלמו" },
  { value: "cancelled", label: "בוטלו" },
] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number]["value"];

type StatusSummaryProps = {
  label: string;
  value: number;
  icon: typeof Clock3;
  tone: string;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

function StatusSummary({ label, value, icon: Icon, tone }: StatusSummaryProps) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold text-slate-400">{label}</p>
          <p className="mt-1 text-2xl font-extrabold text-slate-900 dark:text-white">{value}</p>
        </div>
        <div className={`rounded-xl p-2.5 ${tone}`}><Icon size={18} /></div>
      </div>
    </div>
  );
}

export default function OrdersPage() {
  const { data: orders, isLoading, isError, refetch } = useQuery({
    queryKey: ["orders"],
    queryFn: () => orderService.getOrders(),
  });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");

  const filteredOrders = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (orders ?? []).filter((order) => {
      const matchesStatus = status === "all" || order.status === status;
      const matchesSearch = !query ||
        order.order_number.toLowerCase().includes(query) ||
        order.supplier_name.toLowerCase().includes(query);
      return matchesStatus && matchesSearch;
    });
  }, [orders, search, status]);

  const count = (value: string) => (orders ?? []).filter((order) => order.status === value).length;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">הזמנות רכש</h1>
            {orders && <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">{orders.length} הזמנות</span>}
          </div>
          <p className="mt-1 text-sm text-slate-500">מרכז העבודה לניהול, מעקב ואישור הזמנות.</p>
        </div>
        <Link href="/dashboard/orders/new">
          <Button className="shadow-sm"><Plus size={16} /> הזמנה חדשה</Button>
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatusSummary label="ממתינות לאישור" value={count("submitted")} icon={Clock3} tone="bg-amber-50 text-amber-600 dark:bg-amber-950/40" />
        <StatusSummary label="אושרו" value={count("approved")} icon={CheckCircle2} tone="bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40" />
        <StatusSummary label="אצל הספק" value={count("sent")} icon={Send} tone="bg-sky-50 text-sky-600 dark:bg-sky-950/40" />
        <StatusSummary label="הושלמו" value={count("completed")} icon={PackageCheck} tone="bg-violet-50 text-violet-600 dark:bg-violet-950/40" />
        <StatusSummary label="טיוטות" value={count("draft")} icon={ShoppingCart} tone="bg-slate-100 text-slate-600 dark:bg-slate-800" />
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="border-b border-slate-100 p-3 dark:border-slate-800">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חיפוש לפי מספר הזמנה או ספק..." className="h-10 pr-9" />
            </div>
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {STATUS_FILTERS.map((filter) => (
                <button
                  key={filter.value}
                  type="button"
                  onClick={() => setStatus(filter.value)}
                  className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-bold transition ${status === filter.value ? "bg-indigo-600 text-white shadow-sm" : "bg-slate-50 text-slate-500 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300"}`}
                >
                  {filter.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {isError ? (
          <div className="flex flex-col items-center justify-center gap-3 p-12 text-center">
            <AlertCircle className="text-red-500" size={30} />
            <p className="font-bold text-slate-800 dark:text-white">לא הצלחנו לטעון את ההזמנות</p>
            <Button variant="secondary" onClick={() => refetch()}>נסה שוב</Button>
          </div>
        ) : isLoading ? (
          <div className="space-y-3 p-4">
            {[1, 2, 3, 4, 5].map((row) => <div key={row} className="h-16 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}
          </div>
        ) : filteredOrders.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-14 text-center">
            <div className="mb-4 rounded-2xl bg-slate-100 p-4 text-slate-400 dark:bg-slate-800"><ShoppingCart size={28} /></div>
            <h2 className="font-bold text-slate-800 dark:text-white">אין הזמנות להצגה</h2>
            <p className="mt-1 text-sm text-slate-500">נסה לשנות את החיפוש או צור הזמנה חדשה.</p>
            <Link href="/dashboard/orders/new" className="mt-4"><Button><Plus size={16} /> הזמנה חדשה</Button></Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-right">
              <thead className="border-b border-slate-100 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-950/40">
                <tr>
                  {['מס\' הזמנה', 'ספק', 'סטטוס', 'סה"כ', 'נוצר בתאריך'].map((heading) => <th key={heading} className="px-5 py-3 text-xs font-extrabold text-slate-500">{heading}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredOrders.map((order) => (
                  <tr key={order.id} className="group transition-colors hover:bg-indigo-50/40 dark:hover:bg-slate-800/60">
                    <td className="px-5 py-4">
                      <Link href={`/dashboard/orders/${order.id}`} className="font-extrabold text-indigo-600 hover:text-indigo-700 hover:underline dark:text-indigo-400">{order.order_number}</Link>
                    </td>
                    <td className="px-5 py-4 font-medium text-slate-700 dark:text-slate-200">{order.supplier_name}</td>
                    <td className="px-5 py-4"><OrderStatusBadge status={order.status} /></td>
                    <td className="px-5 py-4 font-bold text-slate-800 dark:text-slate-100">{order.currency} {order.final_total.toLocaleString("he-IL")}</td>
                    <td className="px-5 py-4 text-sm text-slate-500">{formatDate(order.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
