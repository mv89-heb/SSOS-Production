"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, AlertTriangle, CheckCircle2, PackageSearch, Plus, ShoppingCart, Trash2, X } from "lucide-react";
import { catalogService } from "@/services/catalog-service";
import { orderService } from "@/services/order-service";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface DraftLine {
  product_id: number | "";
  quantity: number;
}

export default function NewOrderPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedSupplierId = searchParams.get("supplier_id");

  const [supplierId, setSupplierId] = useState<number | "">(
    preselectedSupplierId ? Number(preselectedSupplierId) : ""
  );
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([{ product_id: "", quantity: 1 }]);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: suppliers, isLoading: suppliersLoading } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => catalogService.listSuppliers(true),
  });

  const { data: products, isLoading: productsLoading } = useQuery({
    queryKey: ["products", supplierId],
    queryFn: () => catalogService.listProducts(supplierId === "" ? undefined : supplierId),
    enabled: supplierId !== "",
  });

  useEffect(() => {
    if (supplierId !== "" && suppliers && !suppliers.some((s) => s.id === supplierId)) {
      setSupplierId("");
    }
  }, [suppliers, supplierId]);

  const createMutation = useMutation({
    mutationFn: orderService.createOrder,
    onSuccess: (order) => router.push(`/dashboard/orders/${order.id}`),
  });

  const selectedProductIds = useMemo(
    () => new Set(lines.filter((line) => line.product_id !== "").map((line) => line.product_id)),
    [lines]
  );

  const lowStockSuggestions = useMemo(() => {
    if (!products) return [];
    return products
      .filter((product) =>
        product.current_stock !== null &&
        product.min_stock !== null &&
        product.current_stock <= product.min_stock &&
        !selectedProductIds.has(product.id)
      )
      .slice(0, 6);
  }, [products, selectedProductIds]);

  const estimatedTotal = useMemo(() => {
    if (!products) return 0;
    return lines.reduce((sum, line) => {
      if (line.product_id === "" || line.quantity <= 0) return sum;
      const product = products.find((p) => p.id === line.product_id);
      return product ? sum + product.current_price * line.quantity : sum;
    }, 0);
  }, [lines, products]);

  const currency = products?.[0]?.currency ?? "ILS";
  const hasSelectedLines = lines.some((line) => line.product_id !== "");
  const selectedCount = lines.filter((line) => line.product_id !== "").length;

  const updateLine = (index: number, patch: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  };

  const removeLine = (index: number) => {
    setLines((prev) => {
      const next = prev.filter((_, i) => i !== index);
      return next.length ? next : [{ product_id: "", quantity: 1 }];
    });
  };

  const addSuggestedProduct = (productId: number) => {
    const emptyIndex = lines.findIndex((line) => line.product_id === "");
    if (emptyIndex >= 0) {
      updateLine(emptyIndex, { product_id: productId, quantity: 1 });
      return;
    }
    setLines((prev) => [...prev, { product_id: productId, quantity: 1 }]);
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
    createMutation.mutate({
      supplier_id: supplierId,
      notes: notes || undefined,
      items: items.map((line) => ({ product_id: line.product_id as number, quantity: line.quantity })),
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
        </CardContent>
      </Card>

      {supplierId !== "" && lowStockSuggestions.length > 0 && (
        <section className="rounded-3xl border border-amber-200 bg-amber-50/70 p-5 dark:border-amber-900/60 dark:bg-amber-950/20">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-amber-500 p-2 text-white"><AlertTriangle size={18} /></div>
            <div className="min-w-0 flex-1">
              <h2 className="font-extrabold text-amber-950 dark:text-amber-200">מוצרים שכדאי לשקול להזמין</h2>
              <p className="mt-1 text-xs text-amber-800 dark:text-amber-300">המערכת זיהתה מוצרים של הספק שנמצאים במלאי מינימום.</p>
              <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {lowStockSuggestions.map((product) => (
                  <button
                    key={product.id}
                    type="button"
                    onClick={() => addSuggestedProduct(product.id)}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-white p-3 text-right transition hover:-translate-y-0.5 hover:shadow-sm dark:border-amber-900/60 dark:bg-slate-900"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-bold text-slate-800 dark:text-white">{product.name}</span>
                      <span className="mt-1 block text-[11px] text-red-600">מלאי: {product.current_stock} / מינימום: {product.min_stock}</span>
                    </span>
                    <span className="shrink-0 rounded-xl bg-indigo-600 p-2 text-white"><Plus size={15} /></span>
                  </button>
                ))}
              </div>
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
                        {product.sku ? `${product.sku} — ` : ""}{product.name} ({product.currency} {product.current_price.toLocaleString()}{product.unit ? ` / ${product.unit}` : ""})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-full md:w-28">
                  <label className="mb-1 block text-[11px] font-bold text-slate-400">כמות</label>
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
                <p className="text-xs font-semibold text-slate-400">סכום משוער</p>
                <p className="text-sm text-slate-300">הסכום הסופי מחושב ומאומת בצד השרת בעת יצירת ההזמנה.</p>
              </div>
              <p className="text-2xl font-black">{currency} {estimatedTotal.toLocaleString("he-IL")}</p>
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
