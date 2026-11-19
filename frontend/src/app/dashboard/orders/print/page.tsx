"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Printer } from "lucide-react";
import { orderService } from "@/services/order-service";
import { OrderStatusBadge } from "@/components/ui/badge";
import type { Order } from "@/types";

type PrintableOrder = Order & {
  search_provenance?: { matched_fields: string[]; missing_fields: string[] };
};

const MAX_PRINT_ROWS = 5000;
const PAGE_SIZE = 100;

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("he-IL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export default function OrdersPrintReportPage() {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") || "";
  const status = searchParams.get("status") || "";
  const startDate = searchParams.get("start_date") || "";
  const endDate = searchParams.get("end_date") || "";
  const filtersKey = useMemo(
    () => [q, status, startDate, endDate].join("|"),
    [q, status, startDate, endDate],
  );
  const [orders, setOrders] = useState<PrintableOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadReport() {
      setLoading(true);
      setError("");
      setOrders([]);
      setTotal(0);
      try {
        const params = {
          q: q || undefined,
          status: status || undefined,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        };
        const first = await orderService.searchOrders({
          ...params,
          limit: PAGE_SIZE,
          offset: 0,
        });
        if (first.pagination.total > MAX_PRINT_ROWS) {
          throw new Error("הדוח מכיל יותר מ־5,000 הזמנות. צמצם את החיפוש או את טווח התאריכים.");
        }

        const collected: PrintableOrder[] = [...first.orders];
        let offset = first.orders.length;
        while (offset < first.pagination.total) {
          const next = await orderService.searchOrders({
            ...params,
            limit: PAGE_SIZE,
            offset,
          });
          collected.push(...next.orders);
          offset += next.orders.length;
          if (next.orders.length === 0) break;
        }

        if (!cancelled) {
          if (collected.length !== first.pagination.total) {
            setError("הדוח לא נטען במלואו. רענן את הדף ונסה שוב.");
          } else {
            setOrders(collected);
            setTotal(first.pagination.total);
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "טעינת הדוח נכשלה.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadReport();
    return () => {
      cancelled = true;
    };
  }, [filtersKey, q, status, startDate, endDate]);

  const incompleteCount = orders.filter(
    (order) => (order.search_provenance?.missing_fields.length ?? 0) > 0,
  ).length;

  return (
    <main className="print-report mx-auto w-full max-w-7xl space-y-5 p-4 text-slate-900 dark:text-slate-100 sm:p-6">
      <style jsx global>{`
        @media print {
          @page { size: landscape; margin: 12mm; }
          body * { visibility: hidden !important; }
          .print-report, .print-report * { visibility: visible !important; }
          .print-report {
            position: absolute !important;
            inset: 0 !important;
            width: 100% !important;
            max-width: none !important;
            padding: 0 !important;
            margin: 0 !important;
            color: #111 !important;
            background: #fff !important;
          }
          .print-report .print-hidden { display: none !important; }
          .print-report table { width: 100%; border-collapse: collapse; }
          .print-report th, .print-report td {
            border: 1px solid #bbb !important;
            padding: 5px 6px !important;
            color: #111 !important;
            font-size: 9pt !important;
          }
          .print-report thead { display: table-header-group; }
          .print-report tr { break-inside: avoid; }
          .print-report .status-pill { border: 0 !important; background: transparent !important; color: #111 !important; }
        }
      `}</style>

      <div className="print-hidden flex flex-wrap items-center justify-between gap-3">
        <Link href="/dashboard/orders" className="inline-flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-bold text-indigo-600 hover:bg-indigo-50 dark:text-indigo-300 dark:hover:bg-indigo-950/40">
          <ArrowLeft size={16} /> חזרה להזמנות
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          disabled={loading || !!error || orders.length === 0}
          className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-bold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Printer size={16} /> הדפסה / שמירה כ־PDF
        </button>
      </div>

      <header className="border-b border-slate-200 pb-4 dark:border-slate-700">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">SSOS · דוח רכש</p>
        <h1 className="mt-1 text-2xl font-extrabold">דוח הזמנות רכש</h1>
        <p className="mt-2 text-sm text-slate-500">הופק בתאריך {formatDate(new Date().toISOString())}</p>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          {q && <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-800">חיפוש: {q}</span>}
          {status && <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-800">סטטוס: {status}</span>}
          {startDate && <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-800">מתאריך: {startDate}</span>}
          {endDate && <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-800">עד תאריך: {endDate}</span>}
          {!q && !status && !startDate && !endDate && <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-slate-800">כל ההזמנות</span>}
        </div>
      </header>

      {loading ? (
        <p className="py-10 text-center text-sm font-semibold text-slate-500">טוען את כל תוצאות החיפוש לדוח...</p>
      ) : error ? (
        <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm font-semibold text-amber-900">{error}</div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <p className="font-bold">סה״כ {total.toLocaleString("he-IL")} הזמנות</p>
            {incompleteCount > 0 && <p className="font-semibold text-amber-700">אזהרה: {incompleteCount} הזמנות בדוח עם נתוני מקור חסרים</p>}
          </div>
          <div className="overflow-x-auto">
            <table dir="rtl" className="w-full min-w-[900px] text-right text-xs">
              <thead>
                <tr className="bg-slate-100 dark:bg-slate-800">
                  <th className="px-3 py-2">מס׳ הזמנה</th>
                  <th className="px-3 py-2">ספק</th>
                  <th className="px-3 py-2">סטטוס</th>
                  <th className="px-3 py-2">מחלקה</th>
                  <th className="px-3 py-2">פרויקט</th>
                  <th className="px-3 py-2">תאריך מתוכנן</th>
                  <th className="px-3 py-2">סה״כ</th>
                  <th className="px-3 py-2">תאריך יצירה</th>
                  <th className="px-3 py-2">הערות מקור</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id} className="border-b border-slate-200 dark:border-slate-700">
                    <td className="px-3 py-2 font-bold">{order.order_number}</td>
                    <td className="px-3 py-2">{order.supplier_name}</td>
                    <td className="px-3 py-2"><OrderStatusBadge status={order.status} /></td>
                    <td className="px-3 py-2">{order.department || "—"}</td>
                    <td className="px-3 py-2">{order.project || "—"}</td>
                    <td className="px-3 py-2">{formatDate(order.planned_order_date)}</td>
                    <td className="px-3 py-2 font-bold">{order.currency} {order.final_total.toLocaleString("he-IL")}</td>
                    <td className="px-3 py-2">{formatDate(order.created_at)}</td>
                    <td className="px-3 py-2">
                      {order.search_provenance?.missing_fields.length
                        ? `חסר: ${order.search_provenance.missing_fields.join(", ")}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
