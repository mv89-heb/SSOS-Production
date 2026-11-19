"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowLeft, Bell, CalendarClock, CheckCircle2, Clock3,
  Package, Plus, RefreshCw, ShoppingBag, Sparkles, Users, Wallet,
} from "lucide-react";
import { orderService } from "@/services/order-service";
import { priceIntelligenceService } from "@/services/price-intelligence-service";
import { catalogService } from "@/services/catalog-service";
import { reminderService } from "@/services/reminder-service";
import { OrderStatusBadge } from "@/components/ui/badge";
import type { Order } from "@/types";

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("he-IL", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function formatMoney(value: number, currency: string) {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency: currency || "ILS", maximumFractionDigits: 0 }).format(value);
  } catch {
    return new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 }).format(value) + " " + (currency || "מטבע לא ידוע");
  }
}

function MetricCard({ label, value, hint, href, icon: Icon, tone = "slate" }: {
  label: string; value: string | number; hint: string; href: string; icon: typeof Users;
  tone?: "slate" | "indigo" | "amber" | "red" | "emerald" | "violet";
}) {
  const tones = {
    slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    indigo: "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300",
    amber: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
    red: "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300",
    emerald: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
    violet: "bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300",
  };
  return (
    <Link href={href} className="group min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md dark:border-slate-800 dark:bg-slate-950 sm:p-5">
      <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-xs font-bold text-slate-500 dark:text-slate-400">{label}</p><p className="mt-2 break-words text-2xl font-black tracking-tight text-slate-950 dark:text-white sm:text-3xl">{typeof value === "number" ? value.toLocaleString("he-IL") : value}</p></div><span className={"flex h-10 w-10 shrink-0 items-center justify-center rounded-xl " + tones[tone]}><Icon size={19} /></span></div>
      <div className="mt-3 flex items-center justify-between gap-2 text-[11px] text-slate-400"><span>{hint}</span><ArrowLeft size={13} className="shrink-0 transition group-hover:-translate-x-1 group-hover:text-indigo-600" /></div>
    </Link>
  );
}

function Section({ title, subtitle, href, linkLabel, children }: {
  title: string; subtitle?: string; href?: string; linkLabel?: string; children: React.ReactNode;
}) {
  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-4 dark:border-slate-800 sm:px-5">
        <div><h2 className="font-black text-slate-900 dark:text-white">{title}</h2>{subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}</div>
        {href && <Link href={href} className="shrink-0 text-xs font-bold text-indigo-600 hover:text-indigo-800 dark:text-indigo-300">{linkLabel || "לצפייה"} ←</Link>}
      </div>
      {children}
    </section>
  );
}

function EmptyRow({ children }: { children: React.ReactNode }) {
  return <div className="px-5 py-8 text-center text-sm text-slate-500">{children}</div>;
}

function OrderRow({ order }: { order: Order }) {
  return (
    <Link href={"/dashboard/orders/" + order.id} className="flex min-w-0 flex-col gap-2 px-4 py-3 transition hover:bg-slate-50 dark:hover:bg-slate-900/70 sm:flex-row sm:items-center sm:justify-between sm:px-5">
      <div className="min-w-0"><div className="truncate text-sm font-bold text-slate-900 dark:text-white">{order.order_number} <span className="font-normal text-slate-400">· {order.supplier_name}</span></div><div className="mt-1 text-xs text-slate-400">{formatDate(order.created_at)}{order.planned_order_date ? " · אספקה מתוכננת: " + formatDate(order.planned_order_date) : ""}</div></div>
      <div className="flex items-center justify-between gap-3 sm:justify-end"><span className="text-sm font-bold text-slate-700 dark:text-slate-200">{formatMoney(Number(order.final_total || 0), order.currency)}</span><OrderStatusBadge status={order.status} /></div>
    </Link>
  );
}

export default function DashboardPage() {
  const ordersQuery = useQuery({ queryKey: ["orders"], queryFn: () => orderService.getOrders(), staleTime: 30000 });
  const suppliersQuery = useQuery({ queryKey: ["dashboard", "active-suppliers"], queryFn: () => catalogService.listSuppliers(true), staleTime: 60000 });
  const productsQuery = useQuery({ queryKey: ["dashboard", "active-products"], queryFn: () => catalogService.listProducts(undefined, true), staleTime: 60000 });
  const remindersQuery = useQuery({ queryKey: ["order-reminders"], queryFn: () => reminderService.getOpen(), staleTime: 30000, refetchInterval: 60000, refetchOnWindowFocus: true });
  const inventoryQuery = useQuery({
    queryKey: ["dashboard", "inventory-recommendations"],
    queryFn: () => priceIntelligenceService.getInventoryRecommendations({ lookback_days: 60, safety_days: 2, limit: 500 }),
    staleTime: 60000, retry: 1,
  });
  const portfolioQuery = useQuery({
    queryKey: ["dashboard", "procurement-portfolio"],
    queryFn: () => priceIntelligenceService.getPortfolioSummary(5),
    staleTime: 60000, retry: 1,
  });

  const orders = ordersQuery.data ?? [];
  const activeSuppliers = suppliersQuery.data ?? [];
  const activeProducts = productsQuery.data ?? [];
  const suppliersLoading = suppliersQuery.isLoading;
  const productsLoading = productsQuery.isLoading;
  const inventory = inventoryQuery.data?.recommendations ?? [];
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const pendingApprovals = orders.filter((order) => order.status === "submitted");
  const openOrders = orders.filter((order) => ["draft", "submitted", "approved", "sent"].includes(order.status));
  const overdueReminders = (remindersQuery.data ?? []).filter((reminder) => {
    if (!reminder.next_reminder_at) return false;
    const dueAt = new Date(reminder.next_reminder_at);
    return !Number.isNaN(dueAt.getTime()) && dueAt.getTime() <= now.getTime();
  });
  const monthOrders = orders.filter((order) => {
    const createdAt = new Date(order.created_at);
    return !Number.isNaN(createdAt.getTime()) && createdAt >= monthStart && order.status !== "cancelled" && order.status !== "draft";
  });
  const committedByCurrency = (() => {
    const totals = new Map<string, number>();
    for (const order of monthOrders) {
      const currency = order.currency || "ILS";
      totals.set(currency, (totals.get(currency) || 0) + Number(order.final_total || 0));
    }
    return [...totals.entries()].sort(([a], [b]) => a.localeCompare(b));
  })();

  const urgentStock = inventory.filter((row) => row.status === "urgent");
  const reorderStock = inventory.filter((row) => row.status === "reorder");
  const insufficientStockData = inventory.filter((row) => row.status === "insufficient_data");
  const recentOrders = [...orders].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 7);
  const recentSuppliers = [...activeSuppliers].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5);
  const opportunities = portfolioQuery.data?.top_opportunities ?? [];
  const operationalLoading = ordersQuery.isLoading || inventoryQuery.isLoading || remindersQuery.isLoading;
  const attentionItems = [
    { key: "approval", count: ordersQuery.isError ? -1 : pendingApprovals.length, label: ordersQuery.isError ? "נתוני הזמנות לא זמינים" : "הזמנות ממתינות לאישור", href: "/dashboard/orders", tone: "amber" as const },
    { key: "reminder", count: remindersQuery.isError ? -1 : overdueReminders.length, label: remindersQuery.isError ? "נתוני תזכורות לא זמינים" : "תזכורות שדורשות טיפול", href: "/dashboard/reminders", tone: "red" as const },
    { key: "urgent", count: inventoryQuery.isError ? -1 : urgentStock.length, label: inventoryQuery.isError ? "נתוני סיכון מלאי לא זמינים" : "מוצרים בסיכון מלאי דחוף", href: "/dashboard/procurement-intelligence", tone: "red" as const },
    { key: "reorder", count: inventoryQuery.isError ? 0 : reorderStock.length, label: "מוצרים שמומלץ להזמין", href: "/dashboard/procurement-intelligence", tone: "amber" as const },
  ].filter((item) => item.count !== 0);

  return (
    <div dir="rtl" className="w-full min-w-0 max-w-full space-y-5 pb-8 sm:space-y-6">
      <header className="flex min-w-0 flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950 sm:p-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0"><div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> מרכז שליטה תפעולי</div><h1 className="page-title">לוח בקרה</h1><p className="page-subtitle">מה דורש טיפול עכשיו, מה מצב הרכש ואיפה קיימות הזדמנויות לשיפור.</p><p className="mt-2 text-xs text-slate-400">עודכן: {new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }).format(now)}</p></div>
        <div className="flex w-full flex-wrap gap-2 lg:w-auto">
          <Link href="/dashboard/procurement-intelligence" className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 hover:border-indigo-300 hover:text-indigo-700 dark:border-slate-700 dark:text-slate-200 sm:flex-none"><Sparkles size={16} /> תמונת מצב רכש</Link>
          <Link href="/dashboard/orders/new" className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-indigo-700 sm:flex-none"><Plus size={17} /> הזמנה חדשה</Link>
          <button type="button" onClick={() => { void ordersQuery.refetch(); void inventoryQuery.refetch(); void portfolioQuery.refetch(); void remindersQuery.refetch(); }} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300" aria-label="רענון נתונים"><RefreshCw size={16} className={operationalLoading ? "animate-spin" : ""} /><span className="sm:hidden">רענון</span></button>
        </div>
      </header>

      {(ordersQuery.isError || inventoryQuery.isError || portfolioQuery.isError || remindersQuery.isError) && <div role="status" className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"><AlertTriangle size={18} className="mt-0.5 shrink-0" /><div><strong>חלק מהנתונים לא נטענו.</strong><p className="mt-1 text-xs">הנתונים הזמינים מוצגים כרגיל. אין לפרש נתון חסר כאפס; אפשר לרענן ולנסות שוב.</p></div></div>}

      <section className="grid min-w-0 grid-cols-2 gap-3 xl:grid-cols-4 sm:gap-4">
        <MetricCard label="הזמנות פתוחות" value={ordersQuery.isLoading ? "…" : ordersQuery.isError ? "לא זמין" : openOrders.length} hint="טיוטה, ממתינה, מאושרת או נשלחה" href="/dashboard/orders" icon={ShoppingBag} tone={ordersQuery.isError ? "slate" : "indigo"} />
        <MetricCard label="ממתינות לאישור" value={ordersQuery.isLoading ? "…" : ordersQuery.isError ? "לא זמין" : pendingApprovals.length} hint="הזמנות שהוגשו לאישור" href="/dashboard/orders" icon={Clock3} tone={ordersQuery.isError ? "slate" : pendingApprovals.length ? "amber" : "emerald"} />
        <MetricCard label="תזכורות באיחור" value={remindersQuery.isLoading ? "…" : remindersQuery.isError ? "לא זמין" : overdueReminders.length} hint="לפי רשימת התזכורות הפעילות ומועד היעד" href="/dashboard/reminders" icon={Bell} tone={remindersQuery.isError ? "slate" : overdueReminders.length ? "red" : "emerald"} />
        <MetricCard label="סיכון מלאי דחוף" value={inventoryQuery.isLoading ? "…" : inventoryQuery.isError ? "לא זמין" : urgentStock.length} hint="לפי המלצות מלאי מבוססות נתונים" href="/dashboard/procurement-intelligence" icon={Package} tone={inventoryQuery.isError ? "slate" : urgentStock.length ? "red" : "emerald"} />
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Section title="מרכז טיפול — מה דורש תשומת לב" subtitle="רק פריטים שיש להם אינדיקציה תפעולית ברורה." href="/dashboard/orders" linkLabel="ניהול הזמנות">
          {operationalLoading ? <div className="space-y-3 p-5"><div className="h-10 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /><div className="h-10 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /></div> : attentionItems.length === 0 ? <EmptyRow><CheckCircle2 className="mx-auto mb-2 text-emerald-500" size={22} />אין כרגע פריטי טיפול לפי הנתונים הזמינים.</EmptyRow> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{attentionItems.map((item) => <Link key={item.key} href={item.href} className="flex items-center justify-between gap-3 px-4 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-900/60 sm:px-5"><div className="flex min-w-0 items-center gap-3"><span className={"flex h-9 w-9 shrink-0 items-center justify-center rounded-xl " + (item.tone === "red" ? "bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300" : "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300")}><AlertTriangle size={17} /></span><span className="text-sm font-bold text-slate-800 dark:text-slate-100">{item.label}</span></div><span className="text-xl font-black tabular-nums text-slate-900 dark:text-white">{item.count < 0 ? "לא זמין" : item.count.toLocaleString("he-IL")}</span></Link>)}</div>}
          {inventoryQuery.isSuccess && insufficientStockData.length > 0 && <div className="border-t border-slate-100 bg-slate-50 px-4 py-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900/50">ל־{insufficientStockData.length.toLocaleString("he-IL")} מוצרים אין עדיין מספיק נתוני ספירה/צריכה להמלצה אמינה. הם לא סווגו כדחופים.</div>}
        </Section>

        <Section title="התחייבויות רכש החודש" subtitle="סכום הזמנות שאינן טיוטה או מבוטלות — לא תשלומים שבוצעו." href="/dashboard/orders" linkLabel="פירוט הזמנות">
          {ordersQuery.isLoading ? <EmptyRow>טוען נתוני הזמנות…</EmptyRow> : ordersQuery.isError ? <EmptyRow>נתוני ההתחייבויות אינם זמינים כרגע; אין לפרש זאת כאפס.</EmptyRow> : committedByCurrency.length === 0 ? <EmptyRow>אין הזמנות מחייבות בחודש הנוכחי.</EmptyRow> : <div className="space-y-3 p-4 sm:p-5">{committedByCurrency.map(([currency, total]) => <div key={currency} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-4 dark:border-slate-800"><div className="flex items-center gap-2 text-sm font-semibold text-slate-600 dark:text-slate-300"><Wallet size={17} /> {currency}</div><div className="text-xl font-black tabular-nums text-slate-900 dark:text-white">{formatMoney(total, currency)}</div></div>)}<p className="text-[11px] leading-5 text-slate-400">החישוב מבוסס על תאריך יצירת ההזמנה והסכום הסופי הרשום בה. מטבעות שונים מוצגים בנפרד, ללא המרה מלאכותית.</p></div>}
        </Section>
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-2">
        <Section title="הזמנות אחרונות" subtitle="מעקב מהיר אחר ההזמנות האחרונות שנוצרו." href="/dashboard/orders" linkLabel="כל ההזמנות">
          {ordersQuery.isLoading ? <EmptyRow>טוען הזמנות…</EmptyRow> : ordersQuery.isError ? <EmptyRow>הזמנות אחרונות אינן זמינות כרגע.</EmptyRow> : recentOrders.length === 0 ? <EmptyRow>אין עדיין הזמנות להצגה.</EmptyRow> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{recentOrders.map((order) => <OrderRow key={order.id} order={order} />)}</div>}
        </Section>
        <Section title="הזדמנויות מחיר" subtitle="הזדמנויות מחושבות מהשוואות ספקים; אינן חיסכון שמומש." href="/dashboard/procurement-intelligence" linkLabel="ניתוח מלא">
          {portfolioQuery.isLoading ? <EmptyRow>טוען השוואות מחירים…</EmptyRow> : portfolioQuery.isError ? <EmptyRow>נתוני השוואת המחירים אינם זמינים כרגע.</EmptyRow> : opportunities.length === 0 ? <EmptyRow>אין כרגע הזדמנויות מחיר מאומתות להצגה.</EmptyRow> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{opportunities.slice(0, 5).map((item) => <div key={item.product_id} className="flex items-center justify-between gap-3 px-4 py-3.5 sm:px-5"><div className="min-w-0"><div className="truncate text-sm font-bold text-slate-800 dark:text-slate-100">{item.product_name}</div><div className="mt-1 text-xs text-slate-400">{item.current_supplier || "ספק נוכחי לא ידוע"} ← {item.best_supplier || "חלופה לא ידועה"}</div></div><div className="shrink-0 text-left"><div className="text-sm font-black text-emerald-700 dark:text-emerald-300">{formatMoney(item.savings_per_unit, item.currency)} ליחידה</div><div className="text-[11px] text-slate-400">{item.savings_percent.toLocaleString("he-IL", { maximumFractionDigits: 1 })}% פוטנציאלי</div></div></div>)}</div>}
        </Section>
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-2">
        <Section title="ספקים שנוספו לאחרונה" subtitle="קיצורי דרך לעבודה מול הספקים הפעילים." href="/dashboard/suppliers" linkLabel="כל הספקים">
          {suppliersLoading ? <EmptyRow>טוען ספקים…</EmptyRow> : recentSuppliers.length === 0 ? <EmptyRow>אין ספקים פעילים להצגה.</EmptyRow> : <div className="divide-y divide-slate-100 dark:divide-slate-800">{recentSuppliers.map((supplier) => <Link key={supplier.id} href={"/dashboard/suppliers/" + supplier.id} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-900/60 sm:px-5"><div className="flex min-w-0 items-center gap-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 font-black text-slate-600 dark:bg-slate-800 dark:text-slate-300">{supplier.name.slice(0, 1)}</span><span className="truncate text-sm font-bold text-slate-800 dark:text-slate-100">{supplier.name}</span></div><span className="shrink-0 text-xs text-slate-400">{formatDate(supplier.created_at)}</span></Link>)}</div>}
        </Section>
        <Section title="איכות נתוני הקטלוג" subtitle="מדדים תיאוריים — אינם משנים מוצרים או מחירים." href="/dashboard/catalog" linkLabel="ניהול קטלוג">
          {productsLoading ? <EmptyRow>טוען קטלוג…</EmptyRow> : <div className="grid grid-cols-2 gap-3 p-4 sm:p-5"><div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900"><div className="text-xs text-slate-500">מוצרים פעילים</div><div className="mt-1 text-2xl font-black">{activeProducts.length.toLocaleString("he-IL")}</div></div><div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900"><div className="text-xs text-slate-500">ספקים פעילים</div><div className="mt-1 text-2xl font-black">{activeSuppliers.length.toLocaleString("he-IL")}</div></div><div className="rounded-xl bg-amber-50 p-4 dark:bg-amber-950/20"><div className="text-xs text-amber-800 dark:text-amber-300">מוצרים ללא מחיר תקין</div><div className="mt-1 text-2xl font-black text-amber-800 dark:text-amber-200">{activeProducts.filter((product) => product.current_price == null || Number(product.current_price) <= 0).length.toLocaleString("he-IL")}</div></div><div className="rounded-xl bg-indigo-50 p-4 dark:bg-indigo-950/30"><div className="text-xs text-indigo-800 dark:text-indigo-300">מוצרים ללא יחידת מידה</div><div className="mt-1 text-2xl font-black text-indigo-800 dark:text-indigo-200">{activeProducts.filter((product) => !String(product.unit || "").trim()).length.toLocaleString("he-IL")}</div></div></div>}
        </Section>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900/50"><div className="flex items-center gap-2"><CalendarClock size={16} /> הנתונים מוצגים לפי המידע שנשמר במערכת; ספירת מלאי חסרה אינה נחשבת לאפס.</div><Link href="/dashboard/inventory" className="font-bold text-indigo-600 hover:text-indigo-800 dark:text-indigo-300">פתיחת ניהול מלאי ←</Link></div>
    </div>
  );
}
