"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Activity, AlertTriangle, BarChart3, Boxes, CalendarDays, CheckCircle2,
  ChevronLeft, CircleDollarSign, Clock3, FileText, Package, RefreshCw, ShoppingCart,
  Truck, Wallet,
} from "lucide-react";
import { apiClient } from "@/services/api-client";
import { catalogService } from "@/services/catalog-service";
import { inventoryService } from "@/services/inventory-service";
import { orderService } from "@/services/order-service";
import { priceIntelligenceService } from "@/services/price-intelligence-service";
import { reminderService } from "@/services/reminder-service";

type SpendDocument = { id: number; reference: string; date: string | null; status: string; amount: number };
type SpendGroup = { supplier_id: number | null; supplier_name: string; category: string; currency: string; total: number; count: number; documents: SpendDocument[] };
type SpendBasis = { totals_by_currency: Record<string, number>; by_supplier: SpendGroup[] };
type SpendResponse = {
  success: boolean;
  period: { start_date: string; end_date: string };
  definitions: Record<string, string>;
  ordered: SpendBasis;
  invoiced: SpendBasis;
  paid: SpendBasis;
  supplier_reliability: Array<{
    supplier_id: number | null; supplier_name: string; category: string; completed_orders: number;
    delivery_sample_size: number; late_orders: number; late_rate_percent: number | null;
    shortage_sample_size: number; short_orders: number; shortage_rate_percent: number | null;
  }>;
};

const localDate = (date: Date) => {
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 10);
};
const dateMonthsAgo = (months: number) => {
  const now = new Date();
  return localDate(new Date(now.getFullYear(), now.getMonth() - months, 1));
};
const today = () => localDate(new Date());
const number = (value: number | null | undefined) =>
  new Intl.NumberFormat("he-IL", { maximumFractionDigits: 1 }).format(Number(value ?? 0));
const money = (value: number, currency: string) => {
  try { return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 0 }).format(value); }
  catch { return `${number(value)} ${currency}`; }
};

function Panel({ title, subtitle, action, children }: {
  title: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-4 dark:border-slate-800 sm:px-5">
        <div><h2 className="font-black text-slate-900 dark:text-white">{title}</h2>{subtitle && <p className="mt-1 text-xs leading-5 text-slate-500">{subtitle}</p>}</div>
        {action}
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  );
}

function Metric({ label, value, note, icon: Icon, state = "normal" }: {
  label: string; value: string; note: string; icon: typeof BarChart3; state?: "normal" | "warning" | "good";
}) {
  const color = state === "warning" ? "text-amber-600 bg-amber-50 dark:bg-amber-950/30" : state === "good" ? "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30" : "text-indigo-600 bg-indigo-50 dark:bg-indigo-950/30";
  return <div className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
    <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-slate-500">{label}</span><span className={`rounded-xl p-2 ${color}`}><Icon size={17}/></span></div>
    <div className="mt-3 break-words text-2xl font-black tabular-nums text-slate-900 dark:text-white">{value}</div>
    <div className="mt-1 text-[11px] leading-5 text-slate-500">{note}</div>
  </div>;
}

function Bars({ rows, onSelect, selected }: {
  rows: Array<{ label: string; value: number; hint?: string; id?: string }>;
  onSelect?: (id: string) => void; selected?: string | null;
}) {
  const max = Math.max(1, ...rows.map((row) => row.value));
  if (!rows.length) return <Empty text="אין נתונים זמינים להצגה בגרף הזה." />;
  return <div className="space-y-3">{rows.map((row, index) => {
    const id = row.id ?? row.label;
    return <button type="button" key={id} onClick={() => onSelect?.(id)} className={`block w-full rounded-xl p-1 text-right ${selected === id ? "bg-indigo-50 ring-1 ring-indigo-200 dark:bg-indigo-950/30 dark:ring-indigo-900" : "hover:bg-slate-50 dark:hover:bg-slate-900"}`}>
      <div className="mb-1 flex items-center justify-between gap-3 text-xs"><span className="min-w-0 truncate font-bold text-slate-700 dark:text-slate-200">{row.label}</span><span className="shrink-0 tabular-nums text-slate-500">{row.hint ?? number(row.value)}</span></div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(0, row.value) / max * 100}%`, opacity: 1 - index * 0.025 }}/></div>
    </button>;
  })}</div>;
}

function Donut({ rows }: { rows: Array<{ label: string; value: number }> }) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  if (!rows.length || total <= 0) return <Empty text="אין נתונים זמינים להצגת חלוקה." />;
  const palette = ["#4f46e5", "#0891b2", "#059669", "#d97706", "#7c3aed", "#db2777", "#64748b", "#0f766e"];
  let cursor = 0;
  const gradient = rows.map((row, index) => {
    const start = cursor; cursor += row.value / total * 100;
    return `${palette[index % palette.length]} ${start}% ${cursor}%`;
  }).join(", ");
  return <div className="flex flex-col items-center gap-5 sm:flex-row sm:justify-around">
    <div className="relative h-40 w-40 shrink-0 rounded-full" style={{ background: `conic-gradient(${gradient})` }}>
      <div className="absolute inset-7 flex flex-col items-center justify-center rounded-full bg-white text-center dark:bg-slate-950"><span className="text-2xl font-black tabular-nums">{number(total)}</span><span className="text-[10px] text-slate-500">סה״כ</span></div>
    </div>
    <div className="w-full space-y-2">{rows.map((row, index) => <div key={row.label} className="flex items-center justify-between gap-3 text-xs"><span className="flex min-w-0 items-center gap-2"><i className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: palette[index % palette.length] }}/><span className="truncate text-slate-600 dark:text-slate-300">{row.label}</span></span><b className="tabular-nums">{number(row.value)} · {Math.round(row.value / total * 100)}%</b></div>)}</div>
  </div>;
}

function Trend({ rows, currency }: { rows: Array<{ label: string; value: number }>; currency: string }) {
  if (!rows.length || rows.every((row) => row.value === 0)) return <Empty text="אין סכומי הזמנות בפועל בתקופה שנבחרה." />;
  const width = 620, height = 190, padX = 34, padY = 22;
  const max = Math.max(1, ...rows.map((row) => row.value));
  const points = rows.map((row, index) => ({
    x: padX + (rows.length === 1 ? 0 : index * (width - padX * 2) / (rows.length - 1)),
    y: height - padY - row.value / max * (height - padY * 2),
  }));
  const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
  return <div className="min-w-0">
    <div className="mb-2 text-xs text-slate-500">סכומי הזמנות לפי חודש · {currency}</div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="מגמת הוצאות חודשית" className="h-auto w-full overflow-visible">
      {[0, 1, 2, 3].map((tick) => <line key={tick} x1={padX} x2={width-padX} y1={padY + tick * (height-padY*2)/3} y2={padY + tick * (height-padY*2)/3} stroke="currentColor" opacity=".10" strokeDasharray="4 4"/>)}
      <polyline points={polyline} fill="none" stroke="#4f46e5" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/>
      {points.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r="4" fill="#4f46e5"><title>{rows[index].label}: {money(rows[index].value, currency)}</title></circle>)}
      {rows.map((row, index) => <text key={row.label} x={points[index].x} y={height-2} fontSize="11" textAnchor="middle" fill="currentColor" opacity=".7">{row.label}</text>)}
    </svg>
    <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">{rows.map((row) => <div key={row.label} className="rounded-lg bg-slate-50 px-2 py-1.5 text-xs dark:bg-slate-900"><span className="text-slate-500">{row.label}</span><b className="mr-2 tabular-nums">{money(row.value, currency)}</b></div>)}</div>
  </div>;
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-xl border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-800">{text}</div>;
}

export default function AnalyticsCenterPage() {
  const [startDate, setStartDate] = useState(dateMonthsAgo(5));
  const [endDate, setEndDate] = useState(today());
  const [applied, setApplied] = useState({ start: dateMonthsAgo(5), end: today() });
  const [currency, setCurrency] = useState("ILS");
  const [selectedSupplier, setSelectedSupplier] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<"overview" | "orders" | "inventory" | "suppliers">("overview");

  const spend = useQuery({
    queryKey: ["analytics-center", "spend", applied.start, applied.end],
    queryFn: async () => (await apiClient.get<SpendResponse>("/api/procurement-analytics/spend", { params: { start_date: applied.start, end_date: applied.end } })).data,
    retry: 1,
  });
  const orders = useQuery({
    queryKey: ["analytics-center", "orders"],
    queryFn: async () => {
      const first = await orderService.searchOrders({ limit: 100, offset: 0 });
      const allOrders = [...first.orders];
      const total = first.pagination.total;
      while (allOrders.length < total && allOrders.length < 5000) {
        const next = await orderService.searchOrders({ limit: 100, offset: allOrders.length });
        if (!next.orders.length) break;
        allOrders.push(...next.orders);
      }
      return { orders: allOrders, total, complete: allOrders.length >= total };
    },
    retry: 1,
  });
  const catalog = useQuery({ queryKey: ["analytics-center", "catalog"], queryFn: () => catalogService.listProducts(undefined, true), retry: 1 });
  const suppliers = useQuery({ queryKey: ["analytics-center", "suppliers"], queryFn: () => catalogService.listSuppliers(true), retry: 1 });
  const inventory = useQuery({ queryKey: ["analytics-center", "inventory"], queryFn: () => inventoryService.getSummary(), retry: 1 });
  const recommendations = useQuery({ queryKey: ["analytics-center", "inventory-recommendations"], queryFn: () => inventoryService.getRecommendations({ lookback_days: 60, safety_days: 2, limit: 2000 }), retry: 1 });
  const profiles = useQuery({ queryKey: ["analytics-center", "consumption-profiles"], queryFn: () => inventoryService.getConsumptionProfiles(), retry: 1 });
  const portfolio = useQuery({ queryKey: ["analytics-center", "price-portfolio"], queryFn: () => priceIntelligenceService.getPortfolioSummary(20), retry: 1 });
  const supplierScores = useQuery({ queryKey: ["analytics-center", "supplier-price-scores"], queryFn: () => priceIntelligenceService.getSupplierScores(50), retry: 1 });
  const readiness = useQuery({ queryKey: ["analytics-center", "data-readiness"], queryFn: () => priceIntelligenceService.getDataReadiness(), retry: 1 });
  const reminders = useQuery({ queryKey: ["analytics-center", "open-reminders"], queryFn: () => reminderService.getOpen(), retry: 1, refetchInterval: 60_000 });

  const budgets = useQuery({
    queryKey: ["analytics-center", "budgets"],
    queryFn: async () => (await apiClient.get<{ success: boolean; budgets: Array<{ id: number; scope_type: string; scope_value: string; period_type: string; period_start: string; amount: number; currency: string; spent_amount: number; remaining_amount: number; active: boolean }> }>("/api/procurement-budgets")).data.budgets,
    retry: 1,
  });
  const documents = useQuery({
    queryKey: ["analytics-center", "documents"],
    queryFn: async () => (await apiClient.get<{ success: boolean; analyses: Array<{ id: number; filename: string; document_type: string | null; status: string; created_at: string }> }>("/api/document-intelligence", { params: { limit: 200 } })).data.analyses,
    retry: 1,
  });
  const audit = useQuery({
    queryKey: ["analytics-center", "audit"],
    queryFn: async () => (await apiClient.get<{ success: boolean; logs: Array<{ id: number; action: string; title: string | null; created_at: string }> }>("/api/audit", { params: { limit: 500, offset: 0 } })).data.logs,
    retry: 1,
  });

  const orderRows = orders.data?.orders ?? [];
  const productRows = catalog.data ?? [];
  const supplierRows = suppliers.data ?? [];
  const inventoryRows = recommendations.data ?? [];
  const spendData = spend.data;
  const currencyOptions = useMemo(() => Object.keys(spendData?.ordered.totals_by_currency ?? {}), [spendData]);
  const activeCurrency = currencyOptions.includes(currency) ? currency : currencyOptions[0] ?? currency;
  const orderedGroups = (spendData?.ordered.by_supplier ?? []).filter((group) => group.currency === activeCurrency);
  const monthlySpend = useMemo(() => {
    const totals = new Map<string, number>();
    const cursor = new Date(`${applied.start}T12:00:00`);
    const end = new Date(`${applied.end}T12:00:00`);
    while (cursor <= end && totals.size < 24) {
      const key = `${cursor.getFullYear()}-${String(cursor.getMonth()+1).padStart(2,"0")}`;
      totals.set(key, 0);
      cursor.setMonth(cursor.getMonth()+1);
    }
    for (const group of spendData?.ordered.by_supplier ?? []) {
      if (group.currency !== activeCurrency) continue;
      for (const document of group.documents) {
        if (!document.date) continue;
        const key = document.date.slice(0, 7);
        if (totals.has(key)) totals.set(key, (totals.get(key) ?? 0) + Number(document.amount ?? 0));
      }
    }
    return Array.from(totals, ([key, value]) => ({ label: key.slice(5) + "/" + key.slice(2,4), value }));
  }, [spendData, applied, activeCurrency]);

  const statusRows = useMemo(() => {
    const labels: Record<string, string> = { draft: "טיוטה", submitted: "הוגשה", approved: "אושרה", sent: "נשלחה", completed: "הושלמה", cancelled: "בוטלה", rejected: "נדחתה" };
    const counts = new Map<string, number>();
    for (const order of orderRows) counts.set(order.status, (counts.get(order.status) ?? 0) + 1);
    return Array.from(counts, ([key, value]) => ({ label: labels[key] ?? key, value, id: key }));
  }, [orderRows]);
  const categoryRows = useMemo(() => {
    const counts = new Map<string, number>();
    for (const product of productRows) {
      const category = product.category?.trim() || "ללא קטגוריה";
      counts.set(category, (counts.get(category) ?? 0) + 1);
    }
    return Array.from(counts, ([label, value]) => ({ label, value })).sort((a,b)=>b.value-a.value).slice(0,8);
  }, [productRows]);
  const riskRows = useMemo(() => {
    const labels: Record<string,string> = { urgent: "דחוף", reorder: "נדרשת הזמנה", healthy: "תקין", insufficient_data: "חסר מידע" };
    const counts = new Map<string,number>();
    for (const row of inventoryRows) counts.set(row.status, (counts.get(row.status) ?? 0) + 1);
    return Array.from(counts, ([key,value])=>({label:labels[key] ?? key,value,id:key}));
  }, [inventoryRows]);
  const selectedSupplierGroup = orderedGroups.find((group) => String(group.supplier_id ?? group.supplier_name) === selectedSupplier);
  const totalOrders = orders.data?.total ?? 0;
  const openOrders = orderRows.filter((row) => ["draft","submitted","approved","sent"].includes(row.status)).length;
  const orderCurrencies = Object.entries(spendData?.ordered.totals_by_currency ?? {});
  const profileRows = (profiles.data ?? []).filter((row) => row.active).slice(0, 10);
  const readinessData = readiness.data;
  const budgetRows = budgets.data ?? [];
  const budgetCurrencies = Array.from(new Set(budgetRows.map((row) => row.currency))).sort();
  const documentStatusRows = useMemo(() => {
    const labels: Record<string, string> = { UPLOADED: "הועלה", PROCESSING: "בעיבוד", ANALYZED: "נותח", PARTIALLY_APPLIED: "יושם חלקית", AI_UNAVAILABLE: "AI לא זמין", FAILED: "נכשל", APPLIED: "יושם" };
    const counts = new Map<string, number>();
    for (const row of documents.data ?? []) counts.set(row.status, (counts.get(row.status) ?? 0) + 1);
    return Array.from(counts, ([key, value]) => ({ label: labels[key] ?? key, value, id: key }));
  }, [documents.data]);
  const auditActionRows = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of audit.data ?? []) counts.set(row.action || "ללא סוג פעולה", (counts.get(row.action || "ללא סוג פעולה") ?? 0) + 1);
    return Array.from(counts, ([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value).slice(0, 8);
  }, [audit.data]);
  const extraQueries = [budgets, documents, audit];
  const baseQueries = [spend, orders, catalog, suppliers, inventory, recommendations, profiles, portfolio, supplierScores, readiness, reminders];
  const loadedCount = [...baseQueries, ...extraQueries].filter((query) => query.isSuccess).length;
  const failedCount = [...baseQueries, ...extraQueries].filter((query) => query.isError).length;
  const loading = [...baseQueries, ...extraQueries].some((query) => query.isLoading);

  const refresh = () => [...baseQueries, ...extraQueries].forEach((query) => void query.refetch());

  return (
    <div dir="rtl" className="min-w-0 space-y-6 pb-10">
      <header className="rounded-2xl border border-indigo-200 bg-gradient-to-l from-indigo-50 via-white to-sky-50 p-5 shadow-sm dark:border-indigo-900 dark:from-indigo-950/30 dark:via-slate-950 dark:to-sky-950/20 sm:p-7">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0"><div className="mb-2 flex items-center gap-2 text-sm font-bold text-indigo-600"><Activity size={17}/> מרכז אנליטיקה · SSOS</div>
            <h1 className="text-3xl font-black text-slate-900 dark:text-white">תמונת מצב כוללת</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-300">ניתוח משולב של רכש, הזמנות, מלאי, צריכה, ספקים ומחירים. כל מדד מוצג לפי מקור הנתונים שלו, ללא חיבור מטבעות או ערבוב תחזית עם ביצוע בפועל.</p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="grid gap-1 text-xs font-semibold text-slate-500">מתאריך<input aria-label="מתאריך" type="date" value={startDate} max={endDate} onChange={(event)=>setStartDate(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"/></label>
            <label className="grid gap-1 text-xs font-semibold text-slate-500">עד תאריך<input aria-label="עד תאריך" type="date" value={endDate} min={startDate} max={today()} onChange={(event)=>setEndDate(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"/></label>
            <button type="button" disabled={!startDate || !endDate || startDate>endDate} onClick={()=>setApplied({start:startDate,end:endDate})} className="min-h-10 rounded-xl bg-indigo-600 px-4 text-sm font-bold text-white disabled:opacity-50">החל טווח</button>
            <button type="button" onClick={refresh} disabled={loading} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"><RefreshCw size={15} className={loading?"animate-spin":""}/> רענן</button>
          </div>
        </div>
      </header>

      <nav aria-label="ניווט אנליטיקה" className="flex flex-wrap gap-2">
        {([{id:"overview",label:"תמונת מצב"},{id:"orders",label:"רכש והזמנות"},{id:"inventory",label:"מלאי וצריכה"},{id:"suppliers",label:"ספקים ומחירים"}] as const).map((tab)=><button key={tab.id} type="button" onClick={()=>setDetailTab(tab.id)} className={`rounded-xl px-4 py-2 text-sm font-bold ${detailTab===tab.id?"bg-indigo-600 text-white":"border border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"}`}>{tab.label}</button>)}
      </nav>

      {failedCount > 0 && <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200"><AlertTriangle className="ml-2 inline" size={16}/>חלק מהמקורות לא נטענו ({loadedCount}/11 זמינים). הנתונים הזמינים מוצגים בנפרד; כשל בטעינה אינו מוצג כאפס.</div>}

      {detailTab === "overview" && <>
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="הזמנות במערכת" value={orders.isSuccess?number(totalOrders):"—"} note={orders.isSuccess?`${number(openOrders)} פתוחות בתהליכי עבודה${orders.data.complete?"":` · מוצגות ${number(orderRows.length)} מתוך ${number(totalOrders)}`}`:"מקור ההזמנות לא זמין"} icon={ShoppingCart}/>
          <Metric label="מוצרים פעילים" value={catalog.isSuccess?number(productRows.length):"—"} note="מתוך הקטלוג הפעיל" icon={Package}/>
          <Metric label="ספקים פעילים" value={suppliers.isSuccess?number(supplierRows.length):"—"} note="ספקים בארגון הנוכחי" icon={Truck}/>
          <Metric label="מוצרים במעקב מלאי" value={recommendations.isSuccess?number(inventoryRows.length):"—"} note="תחזית מלאי אינה ספירה פיזית" icon={Boxes}/><Metric label="מוצרים במלאי נמוך" value={inventory.isSuccess?number(inventory.data.stats.low_stock):"—"} note="לפי סיכום המלאי, לא לפי תחזית בלבד" icon={AlertTriangle} state={inventory.isSuccess && inventory.data.stats.low_stock>0?"warning":"normal"}/><Metric label="תנועות מלאי מתועדות" value={inventory.isSuccess?number(inventory.data.stats.movement_count):"—"} note="תנועות שנרשמו במערכת" icon={Activity}/><Metric label="מסמכים שנותחו" value={readiness.isSuccess?number(readinessData?.documents.analyses):"—"} note="מסמכי רכש שעברו ניתוח במערכת" icon={FileText}/><Metric label="תצפיות מחיר" value={readiness.isSuccess?number(readinessData?.price_intelligence.observation_rows):"—"} note="היסטוריית מחירים שנקלטה בפועל" icon={CircleDollarSign}/><Metric label="תזכורות פתוחות" value={reminders.isSuccess?number(reminders.data.length):"—"} note="מעקב אחר הזמנות שדורשות טיפול" icon={Clock3} state={reminders.isSuccess&&reminders.data.length>0?"warning":"normal"}/>
          {orderCurrencies.map(([code,value])=><Metric key={code} label={`הזמנות שאושרו · ${code}`} value={money(value,code)} note="לפי תאריך יצירת הזמנה" icon={CircleDollarSign}/>)}
          <Metric label="חשבוניות ספק" value={spend.isSuccess?Object.entries(spendData?.invoiced.totals_by_currency??{}).map(([code,value])=>money(value,code)).join(" · ")||"אין נתונים":"—"} note="לא מחובר לסכום ההזמנות" icon={Wallet}/>
          <Metric label="תשלומים שבוצעו" value={spend.isSuccess?Object.entries(spendData?.paid.totals_by_currency??{}).map(([code,value])=>money(value,code)).join(" · ")||"אין נתונים":"—"} note="תשלומים שנרשמו בפועל" icon={CheckCircle2}/>
        </section>
        <section className="grid min-w-0 gap-4 xl:grid-cols-2">
          <Panel title="הוצאות רכש לפי ספק" subtitle="הזמנות שאושרו, נשלחו והושלמו בלבד. יש לבחור מטבע אחד בכל פעם." action={<select aria-label="מטבע להצגה" value={activeCurrency} onChange={(event)=>setCurrency(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900">{(currencyOptions.length?currencyOptions:["ILS"]).map((code)=><option key={code} value={code}>{code}</option>)}</select>}>
            {spend.isError?<Empty text="מקור נתוני ההוצאות לא זמין כרגע."/>:<Bars rows={orderedGroups.map((group)=>({label:group.supplier_name,value:group.total,hint:money(group.total,activeCurrency),id:String(group.supplier_id??group.supplier_name)})).sort((a,b)=>b.value-a.value).slice(0,8)} onSelect={setSelectedSupplier} selected={selectedSupplier}/>}
            {selectedSupplierGroup&&<div className="mt-4 rounded-xl bg-indigo-50 p-3 text-xs dark:bg-indigo-950/30"><b>{selectedSupplierGroup.supplier_name}</b> · {selectedSupplierGroup.count} הזמנות · {money(selectedSupplierGroup.total,activeCurrency)}<div className="mt-2 space-y-1">{selectedSupplierGroup.documents.slice(0,8).map((doc)=><div key={doc.id} className="flex justify-between gap-2"><span>{doc.reference} · {doc.date??"ללא תאריך"}</span><b>{money(doc.amount,activeCurrency)}</b></div>)}</div></div>}
            <div className="mt-3 text-left"><Link href="/dashboard/procurement-analytics" className="text-xs font-bold text-indigo-600 hover:underline">לניתוח הוצאות מפורט <ChevronLeft className="inline" size={14}/></Link></div>
          </Panel>
          <Panel title="מגמת הוצאות חודשית" subtitle="מבוסס על הזמנות מאושרות לפי תאריך יצירה; מטבעות אינם מחוברים.">
            {spend.isError?<Empty text="מקור נתוני ההוצאות לא זמין כרגע."/>:<Trend rows={monthlySpend} currency={activeCurrency}/>}
          </Panel>
          <Panel title="התפלגות סטטוס הזמנות" subtitle="כל ההזמנות הזמינות בארגון, לפי סטטוס נוכחי.">{orders.isError?<Empty text="נתוני ההזמנות לא זמינים כרגע."/>:<Donut rows={statusRows}/>}<div className="mt-3 text-left"><Link href="/dashboard/orders" className="text-xs font-bold text-indigo-600 hover:underline">לכל ההזמנות <ChevronLeft className="inline" size={14}/></Link></div></Panel>
          <Panel title="התפלגות מוצרים לפי קטגוריה" subtitle="קטגוריות בקטלוג הפעיל; מוצגים שמונת הגדולים.">{catalog.isError?<Empty text="נתוני הקטלוג לא זמינים כרגע."/>:<Donut rows={categoryRows}/>}<div className="mt-3 text-left"><Link href="/dashboard/catalog" className="text-xs font-bold text-indigo-600 hover:underline">לניהול הקטלוג <ChevronLeft className="inline" size={14}/></Link></div></Panel>
        </section>
      </>}

      {detailTab === "orders" && <section className="grid min-w-0 gap-4 xl:grid-cols-2">
        <Panel title="הזמנות לפי סטטוס" subtitle="חלוקה לפי מצב ההזמנה במערכת.">{orders.isError?<Empty text="נתוני ההזמנות לא זמינים כרגע."/>:<Bars rows={statusRows}/>}</Panel>
        <Panel title="הוצאות לפי ספק" subtitle="סכומים מופרדים לפי מטבע.">{spend.isError?<Empty text="מקור נתוני ההוצאות לא זמין כרגע."/>:orderCurrencies.length?orderCurrencies.map(([code,value])=><div key={code} className="mb-3 flex items-center justify-between rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><span className="text-sm font-bold">{code}</span><b className="text-lg">{money(value,code)}</b></div>):<Empty text="אין סכומי הזמנות בתקופה."/>}</Panel>
        <Panel title="חשבוניות ותשלומים" subtitle="מקורות נפרדים שאינם מתווספים לסכום ההזמנות."><div className="grid gap-3 sm:grid-cols-2">{[["חשבוניות",spendData?.invoiced.totals_by_currency??{}],["תשלומים",spendData?.paid.totals_by_currency??{}]].map(([label,values])=><div key={String(label)} className="rounded-xl border p-3 dark:border-slate-800"><h3 className="mb-2 font-bold">{String(label)}</h3>{Object.entries(values as Record<string,number>).map(([code,value])=><div key={code} className="flex justify-between text-sm"><span>{code}</span><b>{money(value,code)}</b></div>)}</div>)}</div></Panel>
        <Panel title="אמינות ספקים" subtitle="מדדים המבוססים על הזמנות שהושלמו ומדגם קבלות מתועד.">{spend.isError?<Empty text="מקור נתוני אמינות הספקים לא זמין כרגע."/>:spendData?.supplier_reliability?.length?<div className="space-y-3">{spendData.supplier_reliability.map((row)=><div key={row.supplier_id??row.supplier_name} className="rounded-xl border p-3 dark:border-slate-800"><div className="flex justify-between gap-2"><b>{row.supplier_name}</b><span className="text-xs text-slate-500">{row.completed_orders} הזמנות</span></div><div className="mt-2 grid grid-cols-2 gap-2 text-xs"><span>איחורים: <b>{row.late_rate_percent==null?"אין מדגם":`${row.late_rate_percent}%`}</b> ({row.late_orders}/{row.delivery_sample_size})</span><span>חוסרים: <b>{row.shortage_rate_percent==null?"אין מדגם":`${row.shortage_rate_percent}%`}</b> ({row.short_orders}/{row.shortage_sample_size})</span></div></div>)}</div>:<Empty text="אין מספיק נתוני קבלות והשלמות לחישוב אמינות."/>}</Panel>
      </section>}

      {detailTab === "inventory" && <section className="grid min-w-0 gap-4 xl:grid-cols-2">
        <Panel title="מצב מלאי ותחזית" subtitle="המלצות מבוססות היסטוריית ספירות; חסר מידע מוצג בנפרד.">{recommendations.isError?<Empty text="נתוני תכנון המלאי לא זמינים."/>:<Donut rows={riskRows}/>}<div className="mt-3 text-left"><Link href="/dashboard/inventory" className="text-xs font-bold text-indigo-600 hover:underline">למסך המלאי <ChevronLeft className="inline" size={14}/></Link></div></Panel>
        <Panel title="פרופילי צריכה ותגבור" subtitle="הצריכה השבועית המשוקללת מחושבת מפרופילים פעילים.">{profiles.isError?<Empty text="פרופילי הצריכה לא זמינים."/>:profileRows.length?<div className="space-y-3">{profileRows.map((row)=><div key={row.id} className="rounded-xl border p-3 dark:border-slate-800"><div className="flex flex-wrap justify-between gap-2"><b>{row.name}</b><span className="text-xs text-slate-500">{row.mapping_status==="mapped"?"מקושר למוצרים":"ממתין לקישור"}</span></div><div className="mt-2 grid grid-cols-3 gap-2 text-xs"><div><span className="block text-slate-500">רגיל</span><b>{number(row.regular_weekly_consumption)}</b></div><div><span className="block text-slate-500">תגבור</span><b>{number(row.reinforced_weekly_consumption)}</b></div><div><span className="block text-slate-500">משוקלל</span><b>{number(row.weighted_weekly_consumption)}</b></div></div></div>)}</div>:<Empty text="לא הוגדרו פרופילי צריכה פעילים."/>}<div className="mt-3 text-left"><Link href="/dashboard/inventory" className="text-xs font-bold text-indigo-600 hover:underline">לניהול מלאי וצריכה <ChevronLeft className="inline" size={14}/></Link></div></Panel>
        <Panel title="קטגוריות מוצרים" subtitle="מספר מוצרים בכל קטגוריה.">{catalog.isError?<Empty text="נתוני הקטלוג לא זמינים כרגע."/>:<Bars rows={categoryRows}/>}</Panel>
        <Panel title="איכות נתוני מלאי" subtitle="מדדי כיסוי וזמינות מתוך שירות מוכנות הנתונים.">{readiness.isError?<Empty text="מדדי איכות הנתונים לא זמינים."/>:<div className="space-y-3 text-sm">{[["מוצרים עם מחיר",readinessData?.products.priced,readinessData?.products.active],["מוצרים עם קטגוריה",readinessData?.products.categorized,readinessData?.products.active],["מוצרים עם כללי מלאי",readinessData?.products.with_stock_rules,readinessData?.products.active],["מוצרים מכוסים בהצעות ספק",readinessData?.supplier_offers.products_covered,readinessData?.products.active]].map(([label,value,total])=><div key={String(label)}><div className="mb-1 flex justify-between gap-2 text-xs"><span>{String(label)}</span><b>{number(Number(value??0))}/{number(Number(total??0))}</b></div><div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"><div className="h-full rounded-full bg-sky-600" style={{width:`${Number(total)>0?Number(value??0)/Number(total)*100:0}%`}}/></div></div>)}</div>}</Panel>
      </section>}

      {detailTab === "suppliers" && <section className="grid min-w-0 gap-4 xl:grid-cols-2">
        <Panel title="כיסוי והשוואת מחירים" subtitle="הצעות ספקים ומוצרים עם חלופות תחרותיות.">{supplierScores.isError?<Empty text="נתוני השוואת מחירים לא זמינים."/>:<><div className="mb-4 grid grid-cols-2 gap-3"><Metric label="מוצרים שנבדקו" value={number(supplierScores.data?.products_analyzed)} note="בניתוח חלופות מחיר" icon={Package}/><Metric label="מוצרים עם חלופה" value={number(portfolio.data?.opportunity_products)} note="נמצאה הצעה זולה יותר" icon={CircleDollarSign}/></div><Bars rows={(supplierScores.data?.suppliers??[]).slice(0,10).map((row)=>({label:row.supplier_name??`ספק ${row.supplier_id}`,value:row.score,hint:`ציון ${number(row.score)} · זכיות ${row.wins}`}))}/></>}</Panel>
        <Panel title="הזדמנויות מחיר" subtitle="פערי מחיר ליחידה לפי הצעות ברות השוואה; אינם חיסכון מובטח.">{portfolio.isError?<Empty text="נתוני הזדמנויות מחיר לא זמינים."/>:(portfolio.data?.top_opportunities??[]).length?<div className="space-y-2">{(portfolio.data?.top_opportunities??[]).slice(0,12).map((row)=><div key={row.product_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3 text-xs dark:border-slate-800"><span className="min-w-0 font-bold">{row.product_name}<small className="mr-2 block font-normal text-slate-500">{row.current_supplier??"ספק נוכחי לא ידוע"} ← {row.best_supplier??"חלופה"}</small></span><b className="shrink-0 text-emerald-700 dark:text-emerald-400">{money(row.savings_per_unit,row.currency)} ליחידה</b></div>)}</div>:<Empty text="אין כרגע הזדמנויות מחיר מאומתות."/>}</Panel>
        <Panel title="אמינות ספקים" subtitle="איחורים וחוסרים לפי מדגם קבלות בפועל.">{spend.isError?<Empty text="מקור נתוני אמינות הספקים לא זמין כרגע."/>:spendData?.supplier_reliability?.length?<Bars rows={spendData.supplier_reliability.filter((row)=>row.late_rate_percent!=null).map((row)=>({label:row.supplier_name,value:Number(row.late_rate_percent),hint:`${number(row.late_rate_percent)}% איחורים · מדגם ${row.delivery_sample_size}`}))}/>:<Empty text="אין מדגם מספק לחישוב אמינות ספקים."/>}</Panel>
        <Panel title="שלמות נתוני ספקים ומחירים" subtitle="המדדים משקפים את הרשומות הקיימות בלבד.">{readiness.isError?<Empty text="מדדי שלמות הנתונים לא זמינים."/>:<div className="grid grid-cols-2 gap-3 text-sm"><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><span className="text-xs text-slate-500">הצעות ספק פעילות</span><b className="mt-1 block text-xl">{number(readinessData?.supplier_offers.active)}</b></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><span className="text-xs text-slate-500">ספקים עם הצעות</span><b className="mt-1 block text-xl">{number(readinessData?.supplier_offers.suppliers_covered)}</b></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><span className="text-xs text-slate-500">היסטוריית מחירים</span><b className="mt-1 block text-xl">{number(readinessData?.price_intelligence.history_rows)}</b></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><span className="text-xs text-slate-500">תצפיות מחיר</span><b className="mt-1 block text-xl">{number(readinessData?.price_intelligence.observation_rows)}</b></div></div>}</Panel>
      </section>}

      <section className="grid min-w-0 gap-4 xl:grid-cols-3">
        <Panel title="ביצוע תקציבי רכש" subtitle="התחייבויות מהזמנות שהוגשו, אושרו, נשלחו או הושלמו. אין חיבור בין מטבעות.">
          {budgets.isError ? <Empty text="נתוני התקציבים אינם זמינים בהרשאות המשתמש או כרגע."/> : budgetCurrencies.length ? <div className="space-y-5">{budgetCurrencies.map((code) => <div key={code}><h3 className="mb-2 text-xs font-black text-slate-500">{code} · התחייבות מתוך תקציב</h3><Bars rows={budgetRows.filter((row) => row.currency === code).map((row) => ({ label: `${row.scope_type === "department" ? "מחלקה" : "פרויקט"} · ${row.scope_value}`, value: Math.max(0, Number(row.spent_amount ?? 0)), hint: `${money(Number(row.spent_amount ?? 0), code)} / ${money(Number(row.amount ?? 0), code)}` }))}/></div>)}</div> : <Empty text="לא הוגדרו תקציבים פעילים."/>}
          <div className="mt-3 text-left"><Link href="/dashboard/settings/procurement-budgets" className="text-xs font-bold text-indigo-600 hover:underline">לניהול תקציבים <ChevronLeft className="inline" size={14}/></Link></div>
        </Panel>
        <Panel title="מסמכים וקליטה" subtitle="מספר מסמכים לפי סטטוס עיבוד מתוך 200 הרשומות האחרונות.">
          {documents.isError ? <Empty text="נתוני המסמכים אינם זמינים בהרשאות המשתמש או כרגע."/> : <Donut rows={documentStatusRows}/>}
          <div className="mt-3 text-left"><Link href="/dashboard/document-intelligence" className="text-xs font-bold text-indigo-600 hover:underline">למסמכים וקליטה <ChevronLeft className="inline" size={14}/></Link></div>
        </Panel>
        <Panel title="פעילות מערכת וביקורת" subtitle="התפלגות סוגי פעולות מתוך עד 500 אירועי הביקורת האחרונים.">
          {audit.isError ? <Empty text="נתוני הביקורת אינם זמינים בהרשאות המשתמש או כרגע."/> : <Bars rows={auditActionRows}/>}
          <div className="mt-3 text-left"><Link href="/dashboard/audit" className="text-xs font-bold text-indigo-600 hover:underline">להיסטוריית פעולות <ChevronLeft className="inline" size={14}/></Link></div>
        </Panel>
      </section>

      <Panel title="כניסה לניתוח מודולים" subtitle="מעבר מהתמונה הכוללת למסכי העבודה והנתונים המפורטים.">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {label:"הזמנות רכש",href:"/dashboard/orders",icon:ShoppingCart},
            {label:"ספקים",href:"/dashboard/suppliers",icon:Truck},
            {label:"מוצרים ומחירים",href:"/dashboard/catalog",icon:Package},
            {label:"מלאי וספירות",href:"/dashboard/inventory",icon:Boxes},
            {label:"השוואת מחירים",href:"/dashboard/price-intelligence",icon:CircleDollarSign},
            {label:"מסמכים וקליטה",href:"/dashboard/document-intelligence",icon:Wallet},
            {label:"הוצאות רכש",href:"/dashboard/procurement-analytics",icon:BarChart3},
            {label:"תמונת מצב רכש",href:"/dashboard/procurement-intelligence",icon:Activity},
            {label:"תקציבי רכש",href:"/dashboard/settings/procurement-budgets",icon:Wallet},
            {label:"יומן ותזכורות",href:"/dashboard/calendar",icon:CalendarDays},
            {label:"היסטוריית פעולות",href:"/dashboard/audit",icon:Clock3},
          ].map((item)=>{const Icon=item.icon;return <Link key={item.href} href={item.href} className="flex min-h-12 items-center justify-between gap-3 rounded-xl border border-slate-200 px-3 py-3 text-sm font-bold text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-indigo-950/30"><span className="flex items-center gap-2"><Icon size={17} className="text-indigo-600"/>{item.label}</span><ChevronLeft size={16} className="text-slate-400"/></Link>})}
        </div>
      </Panel>

      <Panel title="טבלת נתונים לייצוא" subtitle="נתוני המקור שמאחורי הגרפים. ניתן לייצא את הטבלה ל־Excel או לשמור את המסך כ־PDF באמצעות סרגל הייצוא.">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-right text-xs">
            <thead><tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800"><th className="px-3 py-2">תחום</th><th className="px-3 py-2">פריט</th><th className="px-3 py-2">נתון</th><th className="px-3 py-2">יחידה / מטבע</th></tr></thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {orderedGroups.map((row)=><tr key={`spend-${row.supplier_id}-${row.currency}`}><td className="px-3 py-2">הוצאות רכש</td><td className="px-3 py-2 font-semibold">{row.supplier_name}</td><td className="px-3 py-2 tabular-nums">{number(row.total)}</td><td className="px-3 py-2">{row.currency}</td></tr>)}
              {statusRows.map((row)=><tr key={`status-${row.id}`}><td className="px-3 py-2">הזמנות</td><td className="px-3 py-2 font-semibold">{row.label}</td><td className="px-3 py-2 tabular-nums">{number(row.value)}</td><td className="px-3 py-2">הזמנות</td></tr>)}
              {categoryRows.map((row)=><tr key={`category-${row.label}`}><td className="px-3 py-2">קטלוג</td><td className="px-3 py-2 font-semibold">{row.label}</td><td className="px-3 py-2 tabular-nums">{number(row.value)}</td><td className="px-3 py-2">מוצרים</td></tr>)}
              {riskRows.map((row)=><tr key={`risk-${row.id}`}><td className="px-3 py-2">מלאי</td><td className="px-3 py-2 font-semibold">{row.label}</td><td className="px-3 py-2 tabular-nums">{number(row.value)}</td><td className="px-3 py-2">מוצרים</td></tr>)}
              {profileRows.map((row)=><tr key={`profile-${row.id}`}><td className="px-3 py-2">צריכה</td><td className="px-3 py-2 font-semibold">{row.name}</td><td className="px-3 py-2 tabular-nums">{number(row.weighted_weekly_consumption)}</td><td className="px-3 py-2">צריכה שבועית משוקללת</td></tr>)}
            </tbody>
          </table>
        </div>
      </Panel>

      <footer className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-950">
        <span><CalendarDays className="ml-1 inline" size={14}/> תקופת הוצאות: {applied.start} עד {applied.end}</span>
        <span>{loadedCount}/14 מקורות נטענו בהצלחה · {failedCount? "חלק מהמדדים אינם זמינים":"המקורות הזמינים נטענו"}</span>
      </footer>
    </div>
  );
}
