"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { BarChart3, CalendarDays, FileText, Receipt, Wallet } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type SpendDocument = {
  id: number;
  reference: string;
  date: string | null;
  status: string;
  amount: number;
  order_id?: number;
  invoice_id?: number;
};
type SpendGroup = {
  supplier_id: number | null;
  supplier_name: string;
  category: string;
  currency: string;
  total: number;
  count: number;
  documents: SpendDocument[];
};
type SpendBasis = { totals_by_currency: Record<string, number>; by_supplier: SpendGroup[] };
type SpendResponse = {
  success: boolean;
  period: { start_date: string; end_date: string };
  definitions: Record<string, string>;
  ordered: SpendBasis;
  invoiced: SpendBasis;
  paid: SpendBasis;
};

function localDate(value: Date) {
  const offset = value.getTimezoneOffset();
  return new Date(value.getTime() - offset * 60_000).toISOString().slice(0, 10);
}
function monthStart() {
  const now = new Date();
  return localDate(new Date(now.getFullYear(), now.getMonth(), 1));
}
function today() {
  return localDate(new Date());
}
function money(value: number, currency: string) {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${value.toLocaleString("he-IL", { maximumFractionDigits: 2 })} ${currency}`;
  }
}

function SpendCard({ title, description, icon: Icon, basis, empty }: {
  title: string;
  description: string;
  icon: typeof FileText;
  basis?: SpendBasis;
  empty?: boolean;
}) {
  const totals = Object.entries(basis?.totals_by_currency ?? {});
  const groups = basis?.by_supplier ?? [];
  return (
    <Card className="min-w-0">
      <CardHeader className="border-b border-slate-100 dark:border-slate-800">
        <CardTitle className="flex items-center gap-2 text-base"><Icon size={18} />{title}</CardTitle>
        <p className="text-xs leading-5 text-slate-500">{description}</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        {totals.length ? <div className="flex flex-wrap gap-2">{totals.map(([currency, value]) => (
          <div key={currency} className="rounded-xl bg-slate-100 px-3 py-2 dark:bg-slate-800">
            <div className="text-[11px] font-semibold text-slate-500">{currency}</div>
            <div className="text-xl font-black tabular-nums">{money(value, currency)}</div>
          </div>
        ))}</div> : <p className="text-sm text-slate-400">אין נתונים לתקופה שנבחרה</p>}
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {groups.map((group) => (
            <div key={`${group.supplier_id ?? "unknown"}-${group.currency}`} className="py-3 first:pt-0">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-bold">{group.supplier_name}</div>
                  <div className="text-xs text-slate-500">{group.category} · {group.count} רשומות</div>
                </div>
                <div className="shrink-0 text-sm font-black tabular-nums">{money(group.total, group.currency)}</div>
              </div>
              <div className="mt-2 space-y-1">
                {group.documents.map((document) => (
                  <div key={document.id} className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                    <span className="min-w-0 break-words">{document.reference} · {document.date ?? "ללא תאריך"}</span>
                    <span className="shrink-0 tabular-nums">{money(document.amount, group.currency)}</span>
                    {document.order_id && <Link className="text-indigo-600 hover:underline" href={`/dashboard/orders/${document.order_id}`}>להזמנה</Link>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function ProcurementAnalyticsPage() {
  const [startDate, setStartDate] = useState(monthStart);
  const [endDate, setEndDate] = useState(today);
  const [appliedRange, setAppliedRange] = useState({ start: monthStart(), end: today() });
  const query = useQuery({
    queryKey: ["procurement-spend", appliedRange.start, appliedRange.end],
    queryFn: async () => {
      const { data } = await apiClient.get<SpendResponse>("/api/procurement-analytics/spend", {
        params: { start_date: appliedRange.start, end_date: appliedRange.end },
      });
      return data;
    },
  });
  const errorMessage = useMemo(() => {
    const error = query.error as { response?: { data?: { message?: string } }; message?: string } | null;
    return error?.response?.data?.message || error?.message || "לא ניתן לטעון את נתוני הרכש";
  }, [query.error]);

  return (
    <div className="space-y-6 pb-10">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm font-bold text-indigo-600"><BarChart3 size={17} /> ניתוח וקבלת החלטות</div>
          <h1 className="page-title">הוצאות רכש</h1>
          <p className="page-subtitle">הפרדה ברורה בין הזמנות שאושרו, חשבוניות שנרשמו ותשלומים שבוצעו.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="grid gap-1 text-xs font-semibold text-slate-500">מתאריך<input aria-label="מתאריך" type="date" value={startDate} max={endDate} onChange={(event) => setStartDate(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white" /></label>
          <label className="grid gap-1 text-xs font-semibold text-slate-500">עד תאריך<input aria-label="עד תאריך" type="date" value={endDate} min={startDate} max={today()} onChange={(event) => setEndDate(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white" /></label>
          <Button className="self-end" onClick={() => setAppliedRange({ start: startDate, end: endDate })} disabled={!startDate || !endDate || startDate > endDate}>עדכון</Button>
        </div>
      </header>

      {query.isLoading ? <div className="rounded-xl border p-6 text-sm text-slate-500">טוען נתוני רכש...</div> : null}
      {query.isError ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{errorMessage}</div> : null}
      {query.data && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-500"><CalendarDays size={14} />{query.data.period.start_date} – {query.data.period.end_date}</div>
          <div className="grid gap-4 xl:grid-cols-3">
            <SpendCard title="הזמנות שאושרו" description={query.data.definitions.ordered} icon={FileText} basis={query.data.ordered} />
            <SpendCard title="חשבוניות ספק" description={query.data.definitions.invoiced} icon={Receipt} basis={query.data.invoiced} />
            <SpendCard title="תשלומים שבוצעו" description={query.data.definitions.paid} icon={Wallet} basis={query.data.paid} />
          </div>
          <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">{query.data.definitions.currency} הנתונים מוצגים לפי תאריך יצירת ההזמנה, תאריך החשבונית ותאריך התשלום בהתאמה. אין לחבר בין שלושת המדדים, כדי למנוע ספירה כפולה.</p>
        </>
      )}
    </div>
  );
}
