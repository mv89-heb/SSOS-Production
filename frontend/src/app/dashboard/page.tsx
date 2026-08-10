"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { orderService } from "@/services/order-service";
import { useSuppliers, useProducts } from "@/hooks/use-catalog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OrderStatusBadge } from "@/components/ui/badge";
import {
  ShoppingBag,
  Clock3,
  CheckCircle2,
  Users,
  Package,
  ArrowLeft,
  AlertTriangle,
  Plus,
  Upload,
  TrendingUp,
} from "lucide-react";

type StatTone = "violet" | "indigo" | "sky" | "amber" | "emerald";

type DashboardStat = {
  label: string;
  value: number;
  icon: typeof Users;
  tone: StatTone;
  href: string;
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("he-IL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function formatMoney(value: number, currency: string) {
  return new Intl.NumberFormat("he-IL", {
    style: "currency",
    currency: currency || "ILS",
    maximumFractionDigits: 0,
  }).format(value);
}

export default function DashboardPage() {
  const { data: orders, isLoading: ordersLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => orderService.getOrders(),
  });
  const { data: suppliers, isLoading: suppliersLoading } = useSuppliers();
  const { data: products, isLoading: productsLoading } = useProducts();

  const allOrders = orders ?? [];
  const allSuppliers = suppliers ?? [];
  const allProducts = products ?? [];

  const pendingApprovals = allOrders.filter((order) => order.status === "submitted");
  const completedOrders = allOrders.filter((order) => order.status === "completed");
  const lowStockProducts = allProducts.filter((product) => {
    if (product.current_stock === null || product.current_stock === undefined) return false;
    if (product.min_stock === null || product.min_stock === undefined) return false;
    return product.current_stock <= product.min_stock;
  });

  const recentOrders = [...allOrders]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  const recentSuppliers = [...allSuppliers]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  const activeProducts = allProducts.filter((product) => product.active);
  const catalogValue = activeProducts.reduce((sum, product) => sum + product.current_price, 0);

  const stats: DashboardStat[] = [
    {
      label: "ספקים פעילים",
      value: allSuppliers.length,
      icon: Users,
      tone: "violet",
      href: "/dashboard/suppliers",
    },
    {
      label: "מוצרים פעילים",
      value: activeProducts.length,
      icon: Package,
      tone: "indigo",
      href: "/dashboard/catalog",
    },
    {
      label: "סה״כ הזמנות",
      value: allOrders.length,
      icon: ShoppingBag,
      tone: "sky",
      href: "/dashboard/orders",
    },
    {
      label: "ממתינות לאישור",
      value: pendingApprovals.length,
      icon: Clock3,
      tone: pendingApprovals.length > 0 ? "amber" : "emerald",
      href: "/dashboard/orders",
    },
  ];

  return (
    <div className="space-y-8 pb-8">
      <section className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            מרכז שליטה
          </div>
          <h1 className="page-title">לוח בקרה</h1>
          <p className="page-subtitle">תמונת מצב מהירה של הרכש, המלאי והפעילות בארגון.</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Link
            href="/dashboard/catalog"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm transition hover:border-indigo-200 hover:text-indigo-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          >
            <Upload className="h-4 w-4" />
            ייבוא מחירון
          </Link>
          <Link
            href="/dashboard/orders/new"
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-indigo-600/20 transition hover:bg-indigo-700"
          >
            <Plus className="h-4 w-4" />
            הזמנה חדשה
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </section>

      <section className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Link
          href="/dashboard/orders"
          className="group rounded-2xl bg-gradient-to-br from-indigo-600 via-indigo-600 to-violet-700 p-6 text-white shadow-xl shadow-indigo-600/15 transition hover:-translate-y-0.5"
        >
          <div className="flex items-start justify-between">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/15">
              <Clock3 className="h-5 w-5" />
            </div>
            <ArrowLeft className="h-5 w-5 opacity-60 transition group-hover:-translate-x-1" />
          </div>
          <p className="mt-7 text-sm font-semibold text-indigo-100">דורש טיפול</p>
          <p className="mt-1 text-4xl font-black">{pendingApprovals.length}</p>
          <p className="mt-1 text-sm text-indigo-100">
            {pendingApprovals.length === 1 ? "הזמנה ממתינה לאישור" : "הזמנות ממתינות לאישור"}
          </p>
        </Link>

        <Link
          href="/dashboard/catalog"
          className="group rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-amber-900/60 dark:bg-amber-950/30"
        >
          <div className="flex items-start justify-between">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <ArrowLeft className="h-5 w-5 text-amber-500 opacity-60 transition group-hover:-translate-x-1" />
          </div>
          <p className="mt-7 text-sm font-semibold text-amber-800 dark:text-amber-300">מלאי נמוך</p>
          <p className="mt-1 text-4xl font-black text-slate-950 dark:text-white">{lowStockProducts.length}</p>
          <p className="mt-1 text-sm text-amber-700 dark:text-amber-400">מוצרים מתחת לרף המינימום</p>
        </Link>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-start justify-between">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400">
              <TrendingUp className="h-5 w-5" />
            </div>
            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400">נתוני קטלוג</span>
          </div>
          <p className="mt-7 text-sm font-semibold text-slate-500">סכום מחירי הקטלוג הפעיל</p>
          <p className="mt-1 text-3xl font-black text-slate-950 dark:text-white">{formatMoney(catalogValue, "ILS")}</p>
          <p className="mt-1 text-sm text-slate-400">סכום מחירים נוכחיים, לא הוצאה בפועל</p>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card className="glass-card">
          <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
            <div>
              <CardTitle className="text-base font-extrabold text-slate-950 dark:text-white">הזמנות אחרונות</CardTitle>
              <p className="mt-1 text-xs text-slate-400">הפעילות האחרונה במערכת</p>
            </div>
            <Link href="/dashboard/orders" className="text-xs font-bold text-indigo-600 hover:text-indigo-700">לכל ההזמנות</Link>
          </CardHeader>
          <CardContent className="pt-2">
            {ordersLoading ? (
              <DashboardListSkeleton />
            ) : recentOrders.length === 0 ? (
              <EmptyState icon={ShoppingBag} title="אין הזמנות עדיין" href="/dashboard/orders/new" action="צור הזמנה" />
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {recentOrders.map((order) => (
                  <Link
                    key={order.id}
                    href={`/dashboard/orders/${order.id}`}
                    className="flex items-center justify-between gap-4 rounded-xl px-2 py-3.5 transition hover:bg-slate-50 dark:hover:bg-slate-800/60"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold text-slate-900 dark:text-white">{order.order_number}</div>
                      <div className="mt-0.5 truncate text-xs text-slate-400">{order.supplier_name} · {formatDate(order.created_at)}</div>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="hidden text-sm font-bold text-slate-700 sm:inline dark:text-slate-200">
                        {formatMoney(order.final_total, order.currency)}
                      </span>
                      <OrderStatusBadge status={order.status} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
            <div>
              <CardTitle className="text-base font-extrabold text-slate-950 dark:text-white">ספקים אחרונים</CardTitle>
              <p className="mt-1 text-xs text-slate-400">ספקים שנוספו לאחרונה</p>
            </div>
            <Link href="/dashboard/suppliers" className="text-xs font-bold text-indigo-600 hover:text-indigo-700">לכל הספקים</Link>
          </CardHeader>
          <CardContent className="pt-2">
            {suppliersLoading ? (
              <DashboardListSkeleton />
            ) : recentSuppliers.length === 0 ? (
              <EmptyState icon={Users} title="אין ספקים עדיין" href="/dashboard/suppliers" action="ניהול ספקים" />
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {recentSuppliers.map((supplier) => (
                  <Link
                    key={supplier.id}
                    href={`/dashboard/suppliers/${supplier.id}`}
                    className="flex items-center justify-between gap-4 rounded-xl px-2 py-3.5 transition hover:bg-slate-50 dark:hover:bg-slate-800/60"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-extrabold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        {supplier.name.slice(0, 1).toUpperCase()}
                      </div>
                      <span className="truncate text-sm font-bold text-slate-900 dark:text-white">{supplier.name}</span>
                    </div>
                    <span className="shrink-0 text-xs text-slate-400">{formatDate(supplier.created_at)}</span>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <Card className="glass-card">
        <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
          <div>
            <CardTitle className="text-base font-extrabold text-slate-950 dark:text-white">מוצרים מובילים בקטלוג</CardTitle>
            <p className="mt-1 text-xs text-slate-400">מוצגים לפי המחיר הנוכחי הגבוה ביותר — לא לפי תדירות הזמנה</p>
          </div>
          <Link href="/dashboard/catalog" className="text-xs font-bold text-indigo-600 hover:text-indigo-700">קטלוג מלא</Link>
        </CardHeader>
        <CardContent className="pt-3">
          {productsLoading ? (
            <DashboardListSkeleton rows={5} />
          ) : activeProducts.length === 0 ? (
            <EmptyState icon={Package} title="אין מוצרים פעילים" href="/dashboard/catalog" action="פתיחת הקטלוג" />
          ) : (
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
              {[...activeProducts]
                .sort((a, b) => b.current_price - a.current_price)
                .slice(0, 5)
                .map((product) => {
                  const hasStock = product.current_stock !== null && product.min_stock !== null;
                  const isLow = hasStock && product.current_stock! <= product.min_stock!;
                  return (
                    <Link
                      key={product.id}
                      href={`/dashboard/catalog/${product.id}`}
                      className="rounded-xl border border-slate-100 p-4 transition hover:border-indigo-200 hover:bg-indigo-50/40 dark:border-slate-800 dark:hover:border-indigo-900 dark:hover:bg-indigo-950/20"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <Package className="h-4 w-4 text-slate-400" />
                        {isLow && <span className="h-2 w-2 rounded-full bg-amber-500" title="מלאי נמוך" />}
                      </div>
                      <p className="mt-4 truncate text-sm font-bold text-slate-900 dark:text-white">{product.name}</p>
                      <p className="mt-1 text-xs text-slate-400">{product.category || "ללא קטגוריה"}</p>
                      <p className="mt-3 text-sm font-black text-indigo-700 dark:text-indigo-300">{formatMoney(product.current_price, product.currency)}</p>
                    </Link>
                  );
                })}
            </div>
          )}
        </CardContent>
      </Card>

      {completedOrders.length > 0 && (
        <div className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm dark:border-emerald-900/50 dark:bg-emerald-950/30">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <span className="font-semibold text-emerald-900 dark:text-emerald-200">{completedOrders.length} הזמנות הושלמו בהצלחה.</span>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone,
  href,
}: DashboardStat) {
  const toneClasses: Record<StatTone, string> = {
    violet: "bg-violet-50 text-violet-600 dark:bg-violet-950/40 dark:text-violet-300",
    indigo: "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-300",
    sky: "bg-sky-50 text-sky-600 dark:bg-sky-950/40 dark:text-sky-300",
    amber: "bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300",
    emerald: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300",
  };

  return (
    <Link href={href} className="group glass-card glass-card-hover p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold text-slate-400">{label}</p>
          <p className="mt-2 text-3xl font-black tracking-tight text-slate-950 dark:text-white">{value.toLocaleString("he-IL")}</p>
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${toneClasses[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      <div className="mt-5 flex items-center gap-1 text-[11px] font-bold text-slate-400 transition group-hover:text-indigo-600">
        פתיחה
        <ArrowLeft className="h-3 w-3 transition group-hover:-translate-x-0.5" />
      </div>
    </Link>
  );
}

function DashboardListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3 py-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="flex items-center justify-between gap-4 rounded-xl p-2">
          <div className="flex flex-1 items-center gap-3">
            <div className="h-9 w-9 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-2/3 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
              <div className="h-2.5 w-1/3 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
            </div>
          </div>
          <div className="h-6 w-16 animate-pulse rounded-full bg-slate-100 dark:bg-slate-800" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  href,
  action,
}: {
  icon: typeof Package;
  title: string;
  href: string;
  action: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400 dark:bg-slate-800">
        <Icon className="h-5 w-5" />
      </div>
      <p className="mt-3 text-sm font-bold text-slate-700 dark:text-slate-200">{title}</p>
      <Link href={href} className="mt-2 text-xs font-bold text-indigo-600 hover:text-indigo-700">
        {action} ←
      </Link>
    </div>
  );
}
