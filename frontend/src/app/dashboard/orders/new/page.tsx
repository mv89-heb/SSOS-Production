"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, AlertTriangle, CalendarDays, CheckCircle2, PackageSearch, Plus, ShoppingCart, Trash2, X } from "lucide-react";
import { catalogService } from "@/services/catalog-service";
import { orderService } from "@/services/order-service";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DraftLine {
  product_id: number | "";
  quantity: number;
  quantity_unit?: "carton";
}

export default function NewOrderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedSupplierId = searchParams.get("supplier_id");
  const preselectedDate = searchParams.get("planned_order_date");

  const [supplierId, setSupplierId] = useState<number | "">(
    preselectedSupplierId ? Number(preselectedSupplierId) : ""
  );
  const [notes, setNotes] = useState("");
  const [plannedOrderDate, setPlannedOrderDate] = useState(preselectedDate || "");
  const [lines, setLines] = useState<DraftLine[]>([{ product_id: "", quantity: 1 }]);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: suppliers, isLoading: suppliersLoading } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => catalogService.listSuppliers(true),
  });

  const selectedSupplier = useMemo(
    () => suppliers?.find((supplier) => supplier.id === supplierId),
    [suppliers, supplierId],
  );
  const forecastTargetDate = useMemo(() => {
    const today = new Date();
    const baseDate = plannedOrderDate || [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");
    const target = new Date(`${baseDate}T12:00:00`);
    if (Number.isNaN(target.getTime())) return baseDate;
    const leadDays = Number(selectedSupplier?.lead_time_days ?? 0);
    target.setDate(target.getDate() + (Number.isFinite(leadDays) ? Math.max(0, leadDays) : 0));
    return [
      target.getFullYear(),
      String(target.getMonth() + 1).padStart(2, "0"),
      String(target.getDate()).padStart(2, "0"),
    ].join("-");
  }, [plannedOrderDate, selectedSupplier?.lead_time_days]);

  const { data: products, isLoading: productsLoading, isError: productsError } = useQuery({
    queryKey: ["products", supplierId],
    queryFn: () => catalogService.listProducts(supplierId === "" ? undefined : supplierId),
    enabled: supplierId !== "",
  });

  useEffect(() => {
    if (supplierId !== "" && suppliers && !suppliers.some((s) => s.id === supplierId)) {
      setSupplierId("");
    }
  }, [suppliers, supplierId]);

  const { data: supplierHistoryForecast, isLoading: historyForecastLoading, isError: historyForecastError } = useQuery({
    queryKey: ["orders", "supplier-history-forecast", supplierId, forecastTargetDate],
    queryFn: () => orderService.getSupplierHistoryForecast(supplierId as number, forecastTargetDate),
    enabled: supplierId !== "",
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: orderService.createOrder,
    onSuccess: (order) => router.push(`/dashboard/orders/${order.id}`),
  });

  // An order has one supplier and must not present a mixed-currency amount as one total.
  // Keep the estimate grouped by the actual selected product currencies.
  const estimatedTotalsByCurrency = useMemo(() => {
    const totals: Record<string, number> = {};
    if (!products) return totals;
    for (const line of lines) {
      if (line.product_id === "" || line.quantity <= 0) continue;
      const product = products.find((candidate) => candidate.id === line.product_id);
      if (!product || product.current_price == null || product.current_price <= 0) continue;
      const currency = (product.currency || "ILS").toUpperCase();
      const pricePerCarton = line.quantity_unit === "carton" && product.unit === "יחידה" && product.units_per_carton ? product.current_price * product.units_per_carton : product.current_price;
      totals[currency] = (totals[currency] || 0) + pricePerCarton * line.quantity;
    }
    return totals;
  }, [lines, products]);
  const selectedCurrencies = Object.keys(estimatedTotalsByCurrency);
  const hasMixedCurrencies = selectedCurrencies.length > 1;
  const formatEstimatedTotals = () => Object.entries(estimatedTotalsByCurrency)
    .map(([currencyCode, total]) => `${currencyCode} ${total.toLocaleString("he-IL", { maximumFractionDigits: 2 })}`)
    .join(" · ");
  const hasSelectedLines = lines.some((line) => line.product_id !== "");
  const selectedCount = lines.filter((line) => line.product_id !== "").length;
  const unitConversionReviewCount = supplierHistoryForecast?.products.filter((item) => item.unit_conversion_issues > 0).length ?? 0;
  const historySuggestions = useMemo(() => {
    if (!products || !supplierHistoryForecast) return [];
    return supplierHistoryForecast.products.filter((item) =>
      item.data_ready
      && products.some((product) => product.id === item.product_id)
      && !lines.some((line) => line.product_id === item.product_id)
    );
  }, [products, supplierHistoryForecast, lines]);

  const updateLine = (index: number, patch: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  };

  const removeLine = (index: number) => {
    setLines((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.length ? next : [{ product_id: "", quantity: 1 }];
    });
  };

  const addSuggestedProduct = (productId: number, quantity: number) => {
    const safeQuantity = Number.isFinite(quantity) && quantity > 0 ? quantity : 1;
    const emptyIndex = lines.findIndex((line) => line.product_id === "");
    if (emptyIndex >= 0) {
      updateLine(emptyIndex, { product_id: productId, quantity: safeQuantity });
      return;
    }
    setLines((prev) => [...prev, { product_id: productId, quantity: safeQuantity }]);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (supplierId === "") {
      setFormError("בחר ספק תחילה.");
      return;
    }
    const items = lines.filter((line) => line.product_id !== "" && line.quantity > 0);
    if (items.length === 0) {
      setFormError("הוסף לפחות שורת מוצר אחת.");
      return;
    }
    const missingPrice = items.find((line) => {
      const product = products?.find((candidate) => candidate.id === line.product_id);
      return !product || product.current_price == null || product.current_price <= 0;
    });
    if (hasMixedCurrencies) {
      setFormError("נבחרו מוצרים במטבעות שונים. יש לפצל להזמנות נפרדות לפי מטבע כדי למנוע סכום שגוי.");
      return;
    }
    if (missingPrice) {
      setFormError("אי אפשר ליצור הזמנה עם מוצר שאין לו מחיר רכישה תקין. השלם את המחיר בקטלוג לפני ההזמנה.");
      return;
    }
    createMutation.mutate({
      supplier_id: supplierId,
      notes: notes || undefined,
      planned_order_date: plannedOrderDate || undefined,
      items: items.map((line) => ({ product_id: line.product_id as number, quantity: line.quantity, ...(line.quantity_unit ? { quantity_unit: line.quantity_unit } : {}) })),
    });
  };

  const inputClass =
    "block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 dark:border-slate-700 dark:bg-slate-950 dark:text-white";

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-10">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            href="/dashboard/orders"
            className="mb-2 inline-flex items-center gap-1 text-sm font-semibold text-slate-500 transition hover:text-indigo-600"
          >
            <ArrowLeft size={16} />
            חזרה להזמנות
          </Link>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">הזמנה חדשה</h1>
          <p className="mt-1 text-sm text-slate-500">בנה את ההזמנה במהירות וקבל אינדיקציה מיידית לעלות.</p>
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <ShoppingCart size={18} className="text-indigo-600" />
          <div>
            <p className="text-[11px] font-bold text-slate-400">פריטים שנבחרו</p>
            <p className="font-extrabold text-slate-900 dark:text-white">{selectedCount}</p>
          </div>
        </div>
      </header>

      <Card className="overflow-hidden rounded-3xl border-slate-200/80 shadow-sm dark:border-slate-800">
        <CardHeader className="border-b border-slate-100 bg-slate-50/70 dark:border-slate-800 dark:bg-slate-950/40">
          <CardTitle className="text-base text-slate-900 dark:text-white">1. בחר ספק</CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <select
            className={inputClass}
            value={supplierId}
            disabled={suppliersLoading}
            onChange={(e) => {
              setSupplierId(e.target.value ? Number(e.target.value) : "");
              setLines([{ product_id: "", quantity: 1 }]);
              setFormError(null);
            }}
          >
            <option value="">{suppliersLoading ? "טוען ספקים..." : "בחר ספק..."}</option>
            {suppliers?.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
            ))}
          </select>
          {supplierId !== "" && (
            <div className="mt-3 flex items-center gap-2 text-xs font-semibold text-emerald-600">
              <CheckCircle2 size={15} />
              הספק נבחר — המוצרים יוצגו לפי הספק הזה
            </div>
          )}
          {supplierId !== "" && (() => {
            const supplier = suppliers?.find((item) => item.id === supplierId);
            if (!supplier) return null;
            const details = [
              supplier.order_days ? ["ימי הזמנה", supplier.order_days] : null,
              supplier.order_cutoff_time ? ["שעת סגירת הזמנות", supplier.order_cutoff_time] : null,
              supplier.delivery_days ? ["ימי אספקה", supplier.delivery_days] : null,
              supplier.lead_time_days != null ? ["זמן אספקה משוער", `${supplier.lead_time_days} ימים`] : null,
              supplier.payment_terms ? ["תנאי תשלום", supplier.payment_terms] : null,
              supplier.credit_days != null ? ["ימי אשראי", `${supplier.credit_days} ימים`] : null,
              supplier.minimum_order_amount != null ? ["מינימום להזמנה", Number(supplier.minimum_order_amount).toLocaleString("he-IL", { maximumFractionDigits: 2 })] : null,
              supplier.delivery_fee != null ? ["דמי משלוח", Number(supplier.delivery_fee).toLocaleString("he-IL", { maximumFractionDigits: 2 })] : null,
            ].filter((item): item is [string, string] => item !== null);
            if (!details.length) return (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-200">
                לא הוגדרו תנאי הזמנה לספק הזה. מומלץ להשלים אותם בכרטיס הספק לפני שליחת ההזמנה.
                <Link href={`/dashboard/suppliers/${supplier.id}`} className="mr-2 font-bold underline">לכרטיס הספק</Link>
              </div>
            );
            return (
              <div className="mt-4 rounded-2xl border border-indigo-100 bg-indigo-50/60 p-4 dark:border-indigo-900/60 dark:bg-indigo-950/20">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <h3 className="text-sm font-extrabold text-slate-900 dark:text-white">תנאי הספק להזמנה זו</h3>
                  <Link href={`/dashboard/suppliers/${supplier.id}`} className="text-xs font-bold text-indigo-700 underline dark:text-indigo-300">עדכון פרטי ספק</Link>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {details.map(([label, value]) => (
                    <div key={label} className="rounded-xl bg-white/80 p-3 dark:bg-slate-900/70">
                      <div className="text-xs text-slate-500">{label}</div>
                      <div className="mt-1 break-words text-sm font-bold text-slate-900 dark:text-white">{value}</div>
                    </div>
                  ))}
                </div>
                {(supplier.minimum_order_amount != null || supplier.delivery_fee != null) && (
                  <p className="mt-3 text-xs text-slate-500">
                    הסכומים מוצגים כפי שנשמרו בכרטיס הספק; לא מוגדר להם מטבע נפרד, ולכן יש לאמת את המטבע מול הספק לפני אישור ההזמנה.
                  </p>
                )}
              </div>
            );
          })()}
        </CardContent>
      </Card>

      <Card className="rounded-3xl border-slate-200/80 shadow-sm dark:border-slate-800">
        <CardHeader className="border-b border-slate-100 bg-slate-50/70 dark:border-slate-800 dark:bg-slate-950/40">
          <CardTitle className="flex items-center gap-2 text-base text-slate-900 dark:text-white"><CalendarDays size={17} className="text-indigo-600" /> מועד ביצוע ההזמנה</CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input type="date" className={inputClass} value={plannedOrderDate} onChange={(e) => setPlannedOrderDate(e.target.value)} />
            {plannedOrderDate && <button type="button" onClick={() => setPlannedOrderDate("")} className="rounded-xl px-3 py-2 text-sm font-bold text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">נקה תאריך</button>}
          </div>
          <p className="mt-2 text-xs text-slate-500">התאריך נשמר כחלק מההזמנה ומאפשר לנהל אותה ישירות מלוח השנה.</p>
        </CardContent>
      </Card>

      {supplierId !== "" && (
        <section className="rounded-3xl border border-indigo-200 bg-indigo-50/60 p-5 dark:border-indigo-900/60 dark:bg-indigo-950/20">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-indigo-600 p-2 text-white"><PackageSearch size={18} /></div>
            <div className="min-w-0 flex-1">
              <h2 className="font-extrabold text-slate-950 dark:text-white">הצעות לפי היסטוריית הזמנות</h2>
              <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                מבוסס על הזמנות שנשלחו לספק או הושלמו במערכת בלבד. טיוטות, אישורים פנימיים, ביטולים וספירות מלאי אינם נכללים.
                הכמויות מנורמלות ליחידת המלאי של המוצר; שורות קרטון מומרות לפי גודל האריזה שנשמר בהזמנה. המחזור הוא 3 שבועות רגילים ושבוע רביעי בתוספת 40%.
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                שבוע היעד מחושב לפי מועד ההזמנה בתוספת זמן האספקה של הספק: {forecastTargetDate}.
              </p>
              {unitConversionReviewCount > 0 && (
                <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
                  {unitConversionReviewCount} מוצרים כוללים בהיסטוריה שורות קרטון ללא נתון המרה אמין או יחידות לא עקביות. לא תוצג עבורם המלצת כמות עד לתיקון נתוני היחידות.
                </p>
              )}
              {historyForecastLoading || productsLoading ? (
                <p className="mt-3 text-sm text-slate-500">טוען היסטוריית הזמנות...</p>
              ) : historyForecastError || productsError ? (
                <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200">
                  לא ניתן לטעון את היסטוריית ההזמנות כרגע. נסה לרענן את המסך.
                </p>
              ) : historySuggestions.length > 0 ? (
                <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {historySuggestions.slice(0, 6).map((item) => (
                    <div key={item.product_id} className="rounded-2xl border border-indigo-100 bg-white p-3 dark:border-indigo-900/50 dark:bg-slate-900">
                      <div className="font-bold text-slate-900 dark:text-white">{item.product_name}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        ממוצע שבוע רגיל: {item.normal_weekly_average.toLocaleString("he-IL", { maximumFractionDigits: 2 })} {item.unit}
                      </div>
                      <div className="text-xs text-slate-500">
                        שבוע מתוגבר: {item.boosted_weekly_forecast.toLocaleString("he-IL", { maximumFractionDigits: 2 })} {item.unit}
                      </div>
                      <button
                        type="button"
                        onClick={() => addSuggestedProduct(item.product_id, item.recommended_quantity)}
                        className="mt-3 w-full rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-700"
                      >
                        הוסף להזמנה · {item.recommended_quantity.toLocaleString("he-IL", { maximumFractionDigits: 2 })} {item.unit}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
                  אין עדיין מוצרים עם היסטוריית הזמנות מספקת ויחידות מדידה תקינות כדי להמליץ על כמויות. לא נשתמש ביתרות מלאי ישנות כתחליף.
                </p>
              )}
              {supplierHistoryForecast && (
                <p className="mt-3 text-[11px] text-slate-500">
                  נבדקו {supplierHistoryForecast.order_count} הזמנות בטווח {supplierHistoryForecast.period.start_date} עד {supplierHistoryForecast.period.end_date}.
                </p>
              )}
            </div>
          </div>
        </section>
      )}

      <Card className="overflow-hidden rounded-3xl border-slate-200/80 shadow-sm dark:border-slate-800">
        <CardHeader className="border-b border-slate-100 bg-slate-50/70 dark:border-slate-800 dark:bg-slate-950/40">
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-base text-slate-900 dark:text-white">2. פריטי הזמנה</CardTitle>
            <span className="text-xs font-bold text-slate-400">{selectedCount} שורות</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 p-5">
          {productsLoading && supplierId !== "" ? (
            <div className="space-y-3">
              {[1, 2].map((row) => <div key={row} className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />)}
            </div>
          ) : lines.map((line, index) => (
            <div key={index} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-950/40">
              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <div className="min-w-0 flex-1">
                  <label className="mb-1 block text-[11px] font-bold text-slate-400">מוצר</label>
                  <select
                    className={inputClass}
                    value={line.product_id}
                    disabled={supplierId === ""}
                    onChange={(e) => updateLine(index, { product_id: e.target.value ? Number(e.target.value) : "" })}
                  >
                    <option value="">בחר מוצר...</option>
                    {products?.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.sku ? `${product.sku} — ` : ""}{product.name} ({product.current_price != null && product.current_price > 0 ? `${product.currency} ${product.current_price.toLocaleString()}` : "חסר מחיר"}{product.unit ? ` / ${product.unit}` : ""})
                      </option>
                    ))}
                  </select>
                  {line.quantity_unit === "carton" && <p className="mt-1 text-[11px] font-bold text-indigo-600">מחיר ההזמנה יחושב לפי קרטון; מחיר יחידה יומר לפי מספר היחידות באריזה.</p>}
                </div>
                <div className="w-full md:w-28">
                  <label className="mb-1 block text-[11px] font-bold text-slate-400">{line.quantity_unit === "carton" ? "כמות (קרטונים)" : "כמות"}</label>
                  <input
                    type="number"
                    min={1}
                    className={inputClass}
                    value={line.quantity}
                    onChange={(e) => updateLine(index, { quantity: Math.max(1, Number(e.target.value) || 1) })}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => removeLine(index)}
                  className="self-end rounded-xl p-2.5 text-slate-400 transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30"
                  aria-label="הסרת שורה"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}

          <Button
            variant="secondary"
            onClick={() => setLines((prev) => [...prev, { product_id: "", quantity: 1 }])}
            disabled={supplierId === ""}
            className="mt-1"
          >
            <Plus size={16} /> הוספת שורה
          </Button>

          {hasSelectedLines && (
            <div className="mt-4 flex flex-col gap-2 rounded-2xl bg-slate-950 p-4 text-white sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-400">סכום משוער לפי מטבע</p>
                <p className="text-sm text-slate-300">הסכום הסופי מחושב ומאומת בצד השרת בעת יצירת ההזמנה.</p>
                {hasMixedCurrencies && <p role="alert" className="mt-2 text-sm font-bold text-amber-300">נבחרו מטבעות שונים — יש לפצל להזמנות נפרדות.</p>}
              </div>
              <p className="text-2xl font-black">{formatEstimatedTotals() || "—"}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-3xl border-slate-200/80 shadow-sm dark:border-slate-800">
        <CardHeader>
          <CardTitle className="text-base text-slate-900 dark:text-white">3. הערות</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <textarea
            className={cn(inputClass, "resize-y")}
            rows={4}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="הערות לספק או לצוות הרכש..."
          />
        </CardContent>
      </Card>

      {(formError || createMutation.isError) && (
        <div className="flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700 dark:border-red-900/60 dark:bg-red-950/20 dark:text-red-300">
          <AlertTriangle className="mt-0.5 shrink-0" size={18} />
          <span>{formError ?? "יצירת ההזמנה נכשלה — בדוק את השדות ונסה שוב."}</span>
          <button type="button" className="mr-auto" onClick={() => setFormError(null)} aria-label="סגירת הודעת שגיאה"><X size={16} /></button>
        </div>
      )}

      <div className="sticky bottom-3 z-20 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-xl backdrop-blur sm:flex-row sm:items-center sm:justify-end dark:border-slate-800 dark:bg-slate-900/95">
        <Link href="/dashboard/orders" className="order-2 sm:order-1">
          <Button variant="ghost" disabled={createMutation.isPending}>ביטול</Button>
        </Link>
        <Button onClick={handleSubmit} disabled={createMutation.isPending || supplierId === ""} className="order-1 min-w-40 shadow-lg shadow-indigo-500/20 sm:order-2">
          <ShoppingCart size={16} />
          {createMutation.isPending ? "יוצר..." : "יצירת הזמנה"}
        </Button>
      </div>
    </div>
  );
}
