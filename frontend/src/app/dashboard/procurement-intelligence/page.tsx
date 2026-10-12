"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  ClipboardCheck,
  PackageSearch,
  RefreshCw,
  Search,
  ShoppingCart,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Truck,
  WalletCards,
  XCircle,
} from "lucide-react";

import { catalogService } from "@/services/catalog-service";
import { orderService } from "@/services/order-service";
import { priceIntelligenceService } from "@/services/price-intelligence-service";
import { ProductSortToggle } from "@/components/catalog/product-sort-toggle";
import { sortByHebrewName, type ProductSortDirection } from "@/lib/product-sorting";

const money = (value: number | null | undefined, currency = "ILS") => {
  const amount = Number(value ?? 0);
  try {
    return new Intl.NumberFormat("he-IL", {
      style: "currency",
      currency: currency || "ILS",
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency || "ILS"}`;
  }
};

const number = (value: number | null | undefined) =>
  new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(Number(value ?? 0));

function StatCard({ label, value, hint, icon, tone = "slate" }: {
  label: string;
  value: string;
  hint: string;
  icon: ReactNode;
  tone?: "slate" | "red" | "amber" | "emerald" | "blue" | "violet";
}) {
  const tones = {
    slate: "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950",
    red: "border-red-200 bg-red-50/60 dark:border-red-900 dark:bg-red-950/20",
    amber: "border-amber-200 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/20",
    emerald: "border-emerald-200 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/20",
    blue: "border-blue-200 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/20",
    violet: "border-violet-200 bg-violet-50/60 dark:border-violet-900 dark:bg-violet-950/20",
  };
  return (
    <div className={`rounded-2xl border p-5 shadow-sm ${tones[tone]}`}>
      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>{label}</span>
        {icon}
      </div>
      <div className="mt-2 text-2xl font-black text-slate-900 dark:text-white">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{hint}</div>
    </div>
  );
}

function Section({ title, hint, action, children }: {
  title: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-col gap-2 border-b border-slate-100 p-5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-black text-slate-900 dark:text-white">{title}</h2>
          {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function ProgressBar({ value, max, label, suffix = "" }: { value: number; max: number; label: string; suffix?: string }) {
  const percent = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3 text-xs">
        <span className="truncate font-semibold text-slate-700 dark:text-slate-200">{label}</span>
        <span className="shrink-0 text-slate-500">{number(value)}{suffix}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function ProcurementIntelligencePage() {
  const summary = useQuery({
    queryKey: ["procurement-intelligence", "summary"],
    queryFn: () => priceIntelligenceService.getPortfolioSummary(50),
    retry: 1,
  });
  const suppliers = useQuery({
    queryKey: ["procurement-intelligence", "suppliers"],
    queryFn: () => priceIntelligenceService.getSupplierScores(50),
    retry: 1,
  });
  const products = useQuery({
    queryKey: ["procurement-intelligence", "catalog-products"],
    queryFn: () => catalogService.listProducts(undefined, true),
    retry: 1,
  });
  const supplierCatalog = useQuery({
    queryKey: ["procurement-intelligence", "catalog-suppliers"],
    queryFn: () => catalogService.listSuppliers(true),
    retry: 1,
  });
  const inventory = useQuery({
    queryKey: ["procurement-intelligence", "inventory-recommendations"],
    queryFn: () => priceIntelligenceService.getInventoryRecommendations({ lookback_days: 60, safety_days: 2, limit: 500 }),
    retry: 1,
  });
  const orders = useQuery({
    queryKey: ["procurement-intelligence", "orders"],
    queryFn: () => orderService.getOrders(),
    retry: 1,
  });
  const readiness = useQuery({
    queryKey: ["procurement-intelligence", "data-readiness"],
    queryFn: () => priceIntelligenceService.getDataReadiness(),
    retry: 1,
  });

  const [productSearch, setProductSearch] = useState("");
  const [sortDirection, setSortDirection] = useState<ProductSortDirection>("asc");
  const [showAllActions, setShowAllActions] = useState(false);
  const [showAllOpportunities, setShowAllOpportunities] = useState(false);
  const [showAllSuppliers, setShowAllSuppliers] = useState(false);
  const [showAllProducts, setShowAllProducts] = useState(false);
  const [productDataFilter, setProductDataFilter] = useState<"all" | "missing-price" | "missing-category" | "missing-unit" | "stock-rules">("all");
  const [briefing, setBriefing] = useState<Awaited<ReturnType<typeof priceIntelligenceService.getAiBriefing>> | null>(null);
  const [aiError, setAiError] = useState<string>();
  const [aiLoading, setAiLoading] = useState(false);

  const refresh = () => {
    void summary.refetch();
    void suppliers.refetch();
    void products.refetch();
    void supplierCatalog.refetch();
    void readiness.refetch();
    void orders.refetch();
    void inventory.refetch();
  };

  const runBriefing = async () => {
    setAiLoading(true);
    setAiError(undefined);
    try {
      setBriefing(await priceIntelligenceService.getAiBriefing());
    } catch (error) {
      setAiError(error instanceof Error ? error.message : "לא ניתן להפעיל את Gemini כרגע.");
    } finally {
      setAiLoading(false);
    }
  };

  const data = summary.data;
  const supplierData = suppliers.data;
  const productRows = products.data ?? [];
  const supplierNames = useMemo(
    () => new Map((supplierCatalog.data ?? []).map((supplier) => [supplier.id, supplier.name])),
    [supplierCatalog.data],
  );
  const readinessData = readiness.data;
  const orderRows = orders.data ?? [];
  const inventoryRows = inventory.data?.recommendations ?? [];
  const urgentStock = inventoryRows.filter((row) => row.status === "urgent");
  const reorderStock = inventoryRows.filter((row) => row.status === "reorder");
  const actionRows = sortByHebrewName([...urgentStock, ...reorderStock], (row) => productRows.find((product) => product.id === row.product_id)?.name ?? "", sortDirection);

  const productById = useMemo(() => new Map(productRows.map((product) => [product.id, product])), [productRows]);
  const opportunityByProduct = useMemo(
    () => new Map((data?.top_opportunities ?? []).map((row) => [row.product_id, row])),
    [data?.top_opportunities],
  );

  const purchaseBasket = useMemo(() => {
    return actionRows
      .filter((row) => row.recommended_order > 0 && productById.has(row.product_id))
      .map((row) => {
        const product = productById.get(row.product_id)!;
        const opportunity = opportunityByProduct.get(row.product_id);
        const unitPrice = opportunity?.best_price ?? Number(product.current_price ?? 0);
        const currency = opportunity?.currency ?? product.currency ?? "ILS";
        const currentUnitPrice = Number(product.current_price ?? 0);
        const savingsPerUnit = opportunity?.savings_per_unit ?? 0;
        return {
          ...row,
          supplierName: opportunity?.best_supplier ?? supplierNames.get(product.supplier_id) ?? null,
          quantity: Math.ceil(row.recommended_order),
          unitPrice,
          currentUnitPrice,
          savingsPerUnit,
          estimatedCost: Math.ceil(row.recommended_order) * unitPrice,
          estimatedSavings: Math.ceil(row.recommended_order) * savingsPerUnit,
          currency,
        };
      })
      .filter((row) => row.quantity > 0)
      .sort((a, b) => b.estimatedCost - a.estimatedCost);
  }, [actionRows, opportunityByProduct, productById, supplierNames]);

  const basketTotal = purchaseBasket.reduce((sum, row) => sum + row.estimatedCost, 0);
  const basketSavings = purchaseBasket.reduce((sum, row) => sum + row.estimatedSavings, 0);

  const categoryRows = useMemo(() => {
    const map = new Map<string, { count: number; stock: number }>();
    for (const product of productRows) {
      const category = product.category || "ללא קטגוריה";
      const current = map.get(category) ?? { count: 0, stock: 0 };
      current.count += 1;
      current.stock += Number(product.current_stock ?? 0);
      map.set(category, current);
    }
    return Array.from(map.entries())
      .map(([category, value]) => ({ category, ...value }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [productRows]);

  const filteredProducts = useMemo(() => {
    const q = productSearch.trim().toLocaleLowerCase("he-IL");
    const matches = (!q ? productRows : productRows.filter((product) =>
      [product.name, product.sku, product.barcode, product.category, supplierNames.get(product.supplier_id)]
        .some((value) => String(value ?? "").toLocaleLowerCase("he-IL").includes(q)),
    )).filter((product) => {
      if (productDataFilter === "missing-price") return Number(product.current_price ?? 0) <= 0;
      if (productDataFilter === "missing-category") return !String(product.category ?? "").trim();
      if (productDataFilter === "missing-unit") return !String(product.unit ?? "").trim();
      if (productDataFilter === "stock-rules") return product.min_stock != null || product.recommended_stock != null;
      return true;
    });
    return sortByHebrewName(matches, (product) => product.name, sortDirection);
  }, [productRows, productSearch, supplierNames, sortDirection, productDataFilter]);

  const coverageReady = inventoryRows.filter((row) => row.data_ready && row.coverage_days != null);
  const averageCoverage = coverageReady.length
    ? coverageReady.reduce((sum, row) => sum + Number(row.coverage_days ?? 0), 0) / coverageReady.length
    : null;
  const insufficientInventoryData = inventoryRows.filter((row) => row.status === "insufficient_data").length;
  const visibleProducts = filteredProducts.slice(0, showAllProducts ? filteredProducts.length : 50);
  const completedOrders = orderRows.filter((order) => order.status === "completed");
  const openOrders = orderRows.filter((order) => ["draft", "submitted", "approved", "sent"].includes(order.status));
  const realizedSpend = completedOrders.reduce((sum, order) => sum + Number(order.final_total ?? 0), 0);
  const ordersWithValue = orderRows.filter((order) => Number(order.final_total ?? 0) > 0).length;
  const recentOrders = [...orderRows].sort((a, b) => String(b.updated_at || b.created_at).localeCompare(String(a.updated_at || a.created_at))).slice(0, 8);
  const loading = summary.isLoading || suppliers.isLoading || products.isLoading || supplierCatalog.isLoading || readiness.isLoading || inventory.isLoading || orders.isLoading;
  const error = summary.isError || suppliers.isError || products.isError || supplierCatalog.isError || readiness.isError || inventory.isError || orders.isError;

  return (
    <div dir="rtl" className="space-y-6 pb-10">
      <header className="rounded-2xl border border-indigo-200 bg-gradient-to-br from-indigo-50 via-white to-violet-50 p-6 shadow-sm dark:border-indigo-900 dark:from-indigo-950/30 dark:via-slate-950 dark:to-violet-950/20">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-600">
              <BrainCircuit size={18} />
              <span className="text-sm font-bold">Decision Center</span>
            </div>
            <h1 className="text-3xl font-black text-slate-900 dark:text-white">מרכז החלטות רכש</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600 dark:text-slate-300">
              לא עוד דוח נתונים. המסך מתרגם מלאי, צריכה, ספקים ומחירים ל־<strong>מה דורש טיפול עכשיו</strong>,
              <strong> מה כדאי להזמין</strong> ו־<strong>איפה קיימת הזדמנות לחיסכון</strong>.
            </p>
          </div>
          <button type="button" onClick={refresh} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold shadow-sm hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900">
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            רענן נתונים
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
          חלק מהמקורות לא נטענו. הנתונים הזמינים מוצגים, אך אין להסיק מסקנה מהיעדר נתון.
        </div>
      )}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
        <StatCard label="דורש טיפול" value={number(actionRows.length)} hint={`${number(urgentStock.length)} דחופים · ${number(reorderStock.length)} להזמנה`} icon={<AlertTriangle className="text-red-500" size={18} />} tone={actionRows.length ? "red" : "emerald"} />
        <StatCard label="סל רכש מומלץ" value={money(basketTotal)} hint={`${number(purchaseBasket.length)} מוצרים · לפני התאמות ידניות`} icon={<ShoppingCart className="text-indigo-500" size={18} />} tone="blue" />
        <StatCard label="חיסכון פוטנציאלי" value={money(data?.potential_savings)} hint={`${number(data?.opportunity_products)} מוצרים עם חלופה זולה יותר`} icon={<TrendingDown className="text-emerald-500" size={18} />} tone="emerald" />
        <StatCard label="כיסוי מלאי ממוצע" value={averageCoverage == null ? "—" : `${number(averageCoverage)} ימים`} hint={`${number(coverageReady.length)} מוצרים עם נתוני צריכה מספיקים`} icon={<PackageSearch className="text-violet-500" size={18} />} tone="violet" />
        <StatCard label="נתוני מלאי חסרים" value={number(insufficientInventoryData)} hint="נדרשות לפחות שתי ספירות כדי לחשב צריכה" icon={<XCircle className="text-amber-500" size={18} />} tone="amber" />
        <StatCard label="מוצרים פעילים" value={number(readinessData?.products.active)} hint={`${number(readinessData?.products.categorized)} עם קטגוריה`} icon={<PackageSearch className="text-blue-500" size={18} />} tone="blue" />
        <StatCard label="מוצרים עם מחיר" value={number(readinessData?.products.priced)} hint={`${number((readinessData?.products.active ?? 0) - (readinessData?.products.priced ?? 0))} ללא מחיר`} icon={<WalletCards className="text-emerald-500" size={18} />} tone="emerald" />
        <StatCard label="ספקים פעילים" value={number(readinessData?.suppliers.active)} hint={`${number(readinessData?.supplier_offers.suppliers_covered)} משתתפים בהשוואת מחירים`} icon={<Truck className="text-violet-500" size={18} />} tone="violet" />
      </section>

      <Section title="📦 פעילות הזמנות והוצאה בפועל" hint="הנתונים מבוססים על הזמנות שנשמרו בפועל במערכת.">
        <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-slate-200 p-4"><div className="text-xs text-slate-500">כל ההזמנות</div><div className="mt-1 text-2xl font-black">{number(orderRows.length)}</div><div className="mt-1 text-xs text-slate-500">{number(ordersWithValue)} עם סכום</div></div>
          <div className="rounded-xl border border-slate-200 p-4"><div className="text-xs text-slate-500">בתהליך</div><div className="mt-1 text-2xl font-black text-indigo-600">{number(openOrders.length)}</div></div>
          <div className="rounded-xl border border-slate-200 p-4"><div className="text-xs text-slate-500">הושלמו</div><div className="mt-1 text-2xl font-black">{number(completedOrders.length)}</div></div>
          <div className="rounded-xl border border-slate-200 p-4"><div className="text-xs text-slate-500">הוצאה ממומשת</div><div className="mt-1 text-2xl font-black">{realizedSpend > 0 ? money(realizedSpend) : "אין נתון"}</div><div className="mt-1 text-xs text-slate-500">{realizedSpend > 0 ? "מסכום הזמנות שהושלמו" : "אין כרגע הזמנות שהושלמו עם סכום חיובי"}</div></div>
        </div>
        {recentOrders.length ? <div className="overflow-x-auto border-t border-slate-100"><table className="w-full min-w-[760px] text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-5 py-3">מס׳ הזמנה</th><th className="px-5 py-3">ספק</th><th className="px-5 py-3">תאריך</th><th className="px-5 py-3">סטטוס</th><th className="px-5 py-3">פריטים</th><th className="px-5 py-3">סכום</th></tr></thead><tbody className="divide-y">{recentOrders.map((order) => <tr key={order.id}><td className="px-5 py-3 font-bold">{order.order_number}</td><td className="px-5 py-3">{order.supplier_name || "—"}</td><td className="px-5 py-3">{order.planned_order_date || (order.created_at ? new Intl.DateTimeFormat("he-IL").format(new Date(order.created_at)) : "—")}</td><td className="px-5 py-3">{({ draft: "טיוטה", submitted: "ממתינה לאישור", approved: "אושרה", sent: "נשלחה לספק", completed: "הושלמה", cancelled: "בוטלה" } as Record<string, string>)[order.status] || order.status}</td><td className="px-5 py-3">{number(order.items?.length ?? 0)}</td><td className="px-5 py-3 font-bold">{Number(order.final_total ?? 0) > 0 ? money(order.final_total, order.currency || "ILS") : "ללא סכום"}</td></tr>)}</tbody></table></div> : <div className="p-8 text-center text-sm text-slate-500">אין הזמנות להצגה.</div>}
        <div className="border-t p-4"><a href="/dashboard/orders" className="text-sm font-bold text-indigo-600">לכל הזמנות הרכש ←</a></div>
      </Section>

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Section title="🔴 מה דורש טיפול עכשיו" hint="המערכת ממיינת לפי דחיפות ולא לפי סדר אלפביתי." action={<a href="/dashboard/inventory" className="text-sm font-bold text-indigo-600">תכנון מלאי ←</a>}>
          {actionRows.length ? (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {(showAllActions ? actionRows : actionRows.slice(0, 8)).map((row) => {
                const opportunity = opportunityByProduct.get(row.product_id);
                return (
                  <div key={row.product_id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
                    <div className={`h-3 w-3 shrink-0 rounded-full ${row.status === "urgent" ? "bg-red-500" : "bg-amber-500"}`} />
                    <div className="min-w-0 flex-1">
                      <div className="font-bold">{row.product_name}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        מלאי {number(row.current_stock)} · צריכה יומית {number(row.average_daily_usage)} · כיסוי {row.coverage_days == null ? "לא ידוע" : `${number(row.coverage_days)} ימים`}
                      </div>
                    </div>
                    <div className="text-sm font-black">
                      {row.recommended_order > 0 ? `להזמין ${number(Math.ceil(row.recommended_order))}` : row.status === "urgent" ? "חסר מלאי" : "לבדיקה"}
                    </div>
                    <div className="text-xs text-slate-500 sm:w-44">
                      {opportunity?.best_supplier ? `ספק עדיף: ${opportunity.best_supplier}` : row.supplier_schedule.supplier_name ? `ספק: ${row.supplier_schedule.supplier_name}` : "אין ספק פעיל מזוהה"}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-10 text-center text-sm text-slate-500"><CheckCircle2 className="mx-auto text-emerald-500" size={32} /><div className="mt-3 font-bold">אין כרגע פריטי מלאי שסומנו לפעולה</div><div className="mt-1">זה לא אומר שאין צורך בספירה; רק שאין המלצת רכש מבוססת נתונים.</div></div>
          )}
          {actionRows.length > 8 && <button type="button" onClick={() => setShowAllActions((value) => !value)} className="w-full border-t border-slate-100 p-3 text-sm font-bold text-indigo-600 dark:border-slate-800">{showAllActions ? "הצג פחות" : `הצג את כל ${number(actionRows.length)} הפריטים`}</button>}
        </Section>

        <Section title="🛒 סל הרכש המומלץ" hint="כמות מומלצת לפי מנוע המלאי; המחיר נלקח מהמחיר הטוב ביותר הידוע כשקיימת השוואה.">
          {purchaseBasket.length ? (
            <>
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {purchaseBasket.slice(0, 7).map((row) => (
                  <div key={row.product_id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0"><div className="truncate font-bold">{row.product_name}</div><div className="mt-1 text-xs text-slate-500">{row.quantity} יח׳ × {money(row.unitPrice, row.currency)} · {row.supplierName || "ללא ספק"}</div></div>
                      <div className="shrink-0 text-left font-black">{money(row.estimatedCost, row.currency)}</div>
                    </div>
                    {row.estimatedSavings > 0 && <div className="mt-2 text-xs font-bold text-emerald-600">חיסכון משוער מול המחיר הנוכחי: {money(row.estimatedSavings, row.currency)}</div>}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3 border-t border-slate-100 p-4 dark:border-slate-800">
                <div><div className="text-xs text-slate-500">עלות סל</div><div className="text-xl font-black">{money(basketTotal)}</div></div>
                <div><div className="text-xs text-slate-500">חיסכון מזוהה בתוך הסל</div><div className="text-xl font-black text-emerald-600">{money(basketSavings)}</div></div>
              </div>
              <div className="border-t border-slate-100 p-4 dark:border-slate-800"><a href="/dashboard/orders" className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-indigo-700">פתח הזמנות רכש <ArrowLeft size={15} /></a></div>
            </>
          ) : (
            <div className="p-10 text-center text-sm text-slate-500"><ShoppingCart className="mx-auto text-slate-300" size={32} /><div className="mt-3 font-bold">אין כרגע סל רכש מחושב</div><div className="mt-1">המערכת לא תייצר כמות הזמנה בלי נתוני ספירה וצריכה מספיקים.</div></div>
          )}
        </Section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section title="💰 איפה יש כסף על השולחן" hint="השוואות מחיר אמיתיות בלבד, לפי יחידת השוואה ומטבע תואמים.">
          {data?.top_opportunities?.length ? (
            <div className="space-y-4 p-5">
              {data.top_opportunities.slice(0, showAllOpportunities ? data.top_opportunities.length : 15).map((row) => (
                <div key={row.product_id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0"><div className="truncate font-bold">{row.product_name}</div><div className="mt-1 text-xs text-slate-500">{row.current_supplier || "ללא ספק נוכחי"} → {row.best_supplier || "ללא ספק חלופי"}</div></div>
                    <div className="shrink-0 text-left"><div className="font-black text-emerald-600">{money(row.savings_per_unit, row.currency)}</div><div className="text-xs text-slate-500">{number(row.savings_percent)}% ליחידה</div></div>
                  </div>
                  <div className="mt-3"><ProgressBar value={row.savings_percent} max={Math.max(10, Number(row.savings_percent))} label="פער המחיר" suffix="%" /></div>
                </div>
              ))}
              {data.top_opportunities.length > 15 && <button type="button" onClick={() => setShowAllOpportunities((value) => !value)} className="w-full rounded-xl border border-slate-200 p-3 text-sm font-bold text-indigo-600 dark:border-slate-800">{showAllOpportunities ? "הצג פחות הזדמנויות" : `הצג את כל ${number(data.top_opportunities.length)} ההזדמנויות`}</button>}
              <a href="/dashboard/price-intelligence/overview" className="inline-flex items-center gap-2 text-sm font-bold text-indigo-600">פתח את כל השוואות הספקים <ArrowLeft size={15} /></a>
            </div>
          ) : (
            <div className="p-10 text-center text-sm text-slate-500">אין כרגע הזדמנויות חיסכון שניתנות להשוואה.</div>
          )}
        </Section>

        <Section title="📊 תמונת מלאי ויזואלית" hint="הגרפים מציגים נתונים קיימים בלבד; אין השלמה של נתונים חסרים.">
          <div className="space-y-5 p-5">
            <div>
              <div className="mb-3 flex items-center justify-between"><span className="text-sm font-bold">היקף מוצרים לפי קטגוריה</span><span className="text-xs text-slate-500">{number(productRows.length)} מוצרים</span></div>
              <div className="space-y-3">
                {categoryRows.map((row) => <ProgressBar key={row.category} value={row.count} max={categoryRows[0]?.count || 1} label={row.category} />)}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-red-50 p-4 dark:bg-red-950/20"><div className="text-xs text-red-700 dark:text-red-300">דחוף</div><div className="mt-1 text-2xl font-black text-red-700 dark:text-red-300">{number(urgentStock.length)}</div></div>
              <div className="rounded-xl bg-amber-50 p-4 dark:bg-amber-950/20"><div className="text-xs text-amber-700 dark:text-amber-300">להזמנה</div><div className="mt-1 text-2xl font-black text-amber-700 dark:text-amber-300">{number(reorderStock.length)}</div></div>
              <div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900"><div className="text-xs text-slate-500">חסר מידע</div><div className="mt-1 text-2xl font-black">{number(insufficientInventoryData)}</div></div>
            </div>
          </div>
        </Section>
      </div>

      <Section title="🚚 ספקים — איפה יש כיסוי ואיפה יש תלות" hint="הדירוג כאן מתייחס לתחרותיות מחיר וכיסוי בלבד, לא לאיכות שירות.">
        {supplierData?.suppliers?.length ? (
          <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
            {supplierData.suppliers.slice(0, showAllSuppliers ? supplierData.suppliers.length : 12).map((supplier) => (
              <div key={supplier.supplier_id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
                <div className="flex items-center justify-between gap-3"><div className="truncate font-bold">{supplier.supplier_name || `ספק #${supplier.supplier_id}`}</div><div className="text-lg font-black text-indigo-600">{number(supplier.score)}</div></div>
                <div className="mt-3 space-y-2">
                  <ProgressBar value={supplier.coverage_percent} max={100} label="כיסוי מוצרים" suffix="%" />
                  <ProgressBar value={supplier.win_rate_percent} max={100} label="ניצחונות מחיר" suffix="%" />
                </div>
                <div className="mt-3 flex justify-between text-xs text-slate-500"><span>{supplier.wins} ניצחונות</span><span>{supplier.participation} השוואות</span></div>
              </div>
            ))}
          </div>
          {supplierData.suppliers.length > 12 && <div className="border-t border-slate-100 p-4 dark:border-slate-800"><button type="button" onClick={() => setShowAllSuppliers((value) => !value)} className="text-sm font-bold text-indigo-600">{showAllSuppliers ? "הצג 12 ספקים מובילים" : `הצג את כל ${number(supplierData.suppliers.length)} הספקים`}</button></div>}
        ) : <div className="p-10 text-center text-sm text-slate-500">אין מספיק הצעות ספקים להשוואה.</div>}
      </Section>

      <Section title="🧾 תנועות מחיר אחרונות" hint="שינויי מחיר מתועדים מהיסטוריית המערכת; הנתונים מוצגים לפי תאריך המקור, ללא תחזיות.">
        {data?.recent_changes?.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">מוצר</th><th className="px-5 py-3">ספק</th><th className="px-5 py-3">מחיר קודם</th><th className="px-5 py-3">מחיר חדש</th><th className="px-5 py-3">שינוי</th><th className="px-5 py-3">תאריך</th><th className="px-5 py-3">מקור</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{data.recent_changes.slice(0, 20).map((change) => <tr key={change.id}><td className="px-5 py-3 font-semibold">{productById.get(change.product_id)?.name || `מוצר #${change.product_id}`}</td><td className="px-5 py-3">{change.supplier_name || supplierNames.get(change.supplier_id) || "—"}</td><td className="px-5 py-3">{change.old_price == null ? "—" : money(change.old_price, change.currency)}</td><td className="px-5 py-3 font-bold">{money(change.new_price, change.currency)}</td><td className={`px-5 py-3 font-bold ${change.change_percent == null ? "text-slate-500" : change.change_percent > 0 ? "text-red-600" : change.change_percent < 0 ? "text-emerald-600" : "text-slate-500"}`}>{change.change_percent == null ? "—" : `${change.change_percent > 0 ? "+" : ""}${number(change.change_percent)}%`}</td><td className="px-5 py-3">{change.effective_at ? new Intl.DateTimeFormat("he-IL").format(new Date(change.effective_at)) : "—"}</td><td className="px-5 py-3">{change.source_type || "רישום מחיר"}</td></tr>)}</tbody></table></div> : <div className="p-8 text-center text-sm text-slate-500">אין עדיין שינויי מחיר מתועדים להצגה.</div>}
      </Section>

      <Section title="🧭 מה המערכת יודעת — ומה עדיין חסר" hint="החלק הזה חשוב כדי שלא נקבל החלטות על בסיס נתון שלא קיים.">
        {readinessData && (
          <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["קטלוג", readinessData.readiness.catalog, `${number(readinessData.products.active)} פעילים`],
              ["השוואת ספקים", readinessData.readiness.supplier_comparison, `${number(readinessData.supplier_offers.active)} הצעות`],
              ["היסטוריית מחירים", readinessData.readiness.historical_prices, `${number(readinessData.price_intelligence.history_rows + readinessData.price_intelligence.observation_rows)} רשומות`],
              ["הוצאה ממומשת", readinessData.readiness.realized_spend, `${number(readinessData.orders.with_realized_value)} הזמנות עם ערך`],
              ["סיכון מלאי", readinessData.readiness.stock_risk, `${number(readinessData.products.with_stock_rules)} עם כללי מלאי`],
            ].map(([label, ready, hint]) => (
              <div key={String(label)} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
                <div className="flex items-center gap-2 text-sm font-bold">{ready ? <CheckCircle2 className="text-emerald-500" size={17} /> : <AlertTriangle className="text-amber-500" size={17} />}{String(label)}</div>
                <div className={`mt-2 text-lg font-black ${ready ? "text-emerald-600" : "text-amber-600"}`}>{ready ? "זמין" : "חסר מקור נתונים"}</div>
                <div className="mt-1 text-xs text-slate-500">{String(hint)}</div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="🔎 חיפוש מוצר לצלילה מהירה" hint="רק כשצריך לעבור מהחלטה לפריט ספציפי.">
        <div className="border-b border-slate-100 p-5 dark:border-slate-800">
          <div className="mb-3 flex justify-end"><ProductSortToggle direction={sortDirection} onToggle={() => setSortDirection((current) => current === "asc" ? "desc" : "asc")} /></div>
          <div className="relative"><Search className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} /><input value={productSearch} onChange={(event) => setProductSearch(event.target.value)} placeholder="מוצר, מק״ט, ברקוד, קטגוריה או ספק..." className="w-full rounded-xl border border-slate-200 bg-white py-3 pr-10 pl-3 text-sm outline-none focus:border-indigo-400 dark:border-slate-700 dark:bg-slate-900" /></div>
        </div>
        <div dir="rtl" className="w-full min-w-0 max-w-full overflow-x-auto overscroll-x-contain">
          <table dir="rtl" className="w-max min-w-[950px] text-right text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">מוצר</th><th className="px-5 py-3">ספק</th><th className="px-5 py-3">מחיר</th><th className="px-5 py-3">מלאי</th><th className="px-5 py-3">סטטוס</th></tr></thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {filteredProducts.map((product) => {
                const recommendation = inventoryRows.find((row) => row.product_id === product.id);
                return <tr key={product.id}><td className="px-5 py-4 font-semibold">{product.name}<div className="text-xs font-normal text-slate-400">{product.sku || product.barcode || "ללא מזהה"}</div></td><td className="px-5 py-4">{supplierNames.get(product.supplier_id) || "—"}</td><td className="px-5 py-4 font-black">{Number(product.current_price ?? 0) > 0 ? money(product.current_price, product.currency || "ILS") : "ללא מחיר"}</td><td className="px-5 py-4">{product.current_stock == null ? "—" : number(product.current_stock)}</td><td className="px-5 py-4">{recommendation?.status === "urgent" ? <span className="font-bold text-red-600">דחוף</span> : recommendation?.status === "reorder" ? <span className="font-bold text-amber-600">להזמין</span> : recommendation?.status === "healthy" ? <span className="font-bold text-emerald-600">תקין</span> : <span className="text-slate-400">אין מספיק נתונים</span>}</td></tr>;
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <section className="overflow-hidden rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 via-white to-indigo-50 shadow-sm dark:border-violet-900 dark:from-violet-950/30 dark:via-slate-950 dark:to-indigo-950/20">
        <div className="flex flex-col gap-4 border-b border-violet-100 p-5 dark:border-violet-900/60 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3"><div className="rounded-xl bg-violet-600 p-2 text-white"><Sparkles size={20} /></div><div><h2 className="font-black text-violet-950 dark:text-violet-100">Gemini — סיכום מנהלים</h2><p className="mt-1 text-sm text-violet-900/70 dark:text-violet-200/70">שכבת הסבר בלבד על הנתונים הדטרמיניסטיים של המערכת.</p></div></div>
          <button type="button" onClick={runBriefing} disabled={aiLoading || !data} className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-violet-700 disabled:opacity-60"><BrainCircuit size={16} />{aiLoading ? "Gemini מנתח..." : "הפק סיכום"}</button>
        </div>
        <div className="p-5">
          {aiError && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{aiError}</div>}
          {!briefing && !aiError && <div className="text-sm text-slate-500">לחיצה על "הפק סיכום" תציג הזדמנויות, סיכונים ופעולות על בסיס הנתונים הקיימים בלבד.</div>}
          {briefing && <div className="grid gap-5 md:grid-cols-3"><div><div className="mb-2 font-bold text-emerald-700">הזדמנויות</div><ul className="space-y-2 text-sm">{briefing.briefing.highlights.map((x, i) => <li key={`h-${i}`}>• {x}</li>)}</ul></div><div><div className="mb-2 font-bold text-amber-700">סיכונים</div><ul className="space-y-2 text-sm">{briefing.briefing.risks.map((x, i) => <li key={`r-${i}`}>• {x}</li>)}</ul></div><div><div className="mb-2 font-bold text-indigo-700">פעולות</div><ul className="space-y-2 text-sm">{briefing.briefing.actions.map((x, i) => <li key={`a-${i}`}>→ {x}</li>)}</ul></div></div>}
        </div>
      </section>

      <div className="grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><Truck className="mb-2 text-blue-500" size={17} /><strong>זמן אספקה:</strong> משמש רק כשקיים אצל הספק נתון אמיתי.</div>
        <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><WalletCards className="mb-2 text-emerald-500" size={17} /><strong>חיסכון:</strong> מוצג רק כשקיימת השוואת מחיר תקפה.</div>
        <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><ClipboardCheck className="mb-2 text-violet-500" size={17} /><strong>מלאי:</strong> תחזית צריכה מתחילה לאחר לפחות שתי ספירות.</div>
      </div>
    </div>
  );
}
