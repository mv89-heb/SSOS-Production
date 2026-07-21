"use client";
import { useState, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation } from "@tanstack/react-query";
import { catalogService } from "@/services/catalog-service";
import { orderService } from "@/services/order-service";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ArrowLeft, Trash2, Plus } from "lucide-react";

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

  const { data: suppliers } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => catalogService.listSuppliers(true),
  });

  const { data: products } = useQuery({
    queryKey: ["products", supplierId],
    queryFn: () => catalogService.listProducts(supplierId === "" ? undefined : supplierId),
    enabled: supplierId !== "",
  });

  // If the supplier arrived via ?supplier_id= before the suppliers list
  // has loaded, there's nothing to validate against yet — once it loads,
  // silently drop a supplier id that doesn't actually belong to this tenant.
  useEffect(() => {
    if (supplierId !== "" && suppliers && !suppliers.some((s) => s.id === supplierId)) {
      setSupplierId("");
    }
  }, [suppliers, supplierId]);

  const createMutation = useMutation({
    mutationFn: orderService.createOrder,
    onSuccess: (order) => router.push(`/dashboard/orders/${order.id}`),
  });

  const updateLine = (index: number, patch: Partial<DraftLine>) => {
    setLines((prev) => prev.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  };

  const removeLine = (index: number) => {
    setLines((prev) => prev.filter((_, i) => i !== index));
  };

  // Client-side estimate only — the authoritative subtotal/tax/total are
  // computed server-side at creation (see the order detail page's frozen
  // snapshot). This just gives a live sense of cost while building the
  // order, using each selected product's current catalog price.
  const estimatedTotal = useMemo(() => {
    if (!products) return 0;
    return lines.reduce((sum, line) => {
      if (line.product_id === "" || line.quantity <= 0) return sum;
      const product = products.find((p) => p.id === line.product_id);
      return product ? sum + product.current_price * line.quantity : sum;
    }, 0);
  }, [lines, products]);
  const currency = products?.[0]?.currency ?? "ILS";
  const hasSelectedLines = lines.some((l) => l.product_id !== "");

  const handleSubmit = () => {
    setFormError(null);
    if (supplierId === "") {
      setFormError("בחר ספק תחילה.");
      return;
    }
    const items = lines.filter((l) => l.product_id !== "" && l.quantity > 0);
    if (items.length === 0) {
      setFormError("הוסף לפחות שורת מוצר אחת.");
      return;
    }
    createMutation.mutate({
      supplier_id: supplierId,
      notes: notes || undefined,
      items: items.map((l) => ({ product_id: l.product_id as number, quantity: l.quantity })),
    });
  };

  const inputClass =
    "block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-primary focus:ring-2 focus:ring-primary/20";

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/orders"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft size={16} />
        חזרה להזמנות
      </Link>

      <h1 className="text-2xl font-bold text-slate-900">הזמנה חדשה</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">ספק</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <select
            className={inputClass}
            value={supplierId}
            onChange={(e) => {
              setSupplierId(e.target.value ? Number(e.target.value) : "");
              setLines([{ product_id: "", quantity: 1 }]);
            }}
          >
            <option value="">בחר ספק...</option>
            {suppliers?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">פריטי הזמנה</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-3">
          {lines.map((line, index) => (
            <div key={index} className="flex items-center gap-3">
              <select
                className={cn(inputClass, "flex-1")}
                value={line.product_id}
                disabled={supplierId === ""}
                onChange={(e) =>
                  updateLine(index, { product_id: e.target.value ? Number(e.target.value) : "" })
                }
              >
                <option value="">בחר מוצר...</option>
                {products?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku ? `${p.sku} — ` : ""}
                    {p.name} ({p.currency} {p.current_price.toLocaleString()}
                    {p.unit ? ` / ${p.unit}` : ""})
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={1}
                className={cn(inputClass, "w-24")}
                value={line.quantity}
                onChange={(e) => updateLine(index, { quantity: Number(e.target.value) })}
              />
              <button
                onClick={() => removeLine(index)}
                className="text-slate-400 hover:text-red-500"
                aria-label="הסרת שורה"
              >
                <Trash2 size={18} />
              </button>
            </div>
          ))}
          <Button
            variant="secondary"
            onClick={() => setLines((prev) => [...prev, { product_id: "", quantity: 1 }])}
            disabled={supplierId === ""}
          >
            <Plus size={16} />
            הוספת שורה
          </Button>

          {hasSelectedLines && (
            <div className="flex justify-between border-t pt-3 text-sm">
              <span className="text-slate-500">סכום משוער</span>
              <span className="font-semibold text-slate-900">
                {currency} {estimatedTotal.toLocaleString()}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">הערות</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <textarea
            className={inputClass}
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </CardContent>
      </Card>

      {formError && <p className="text-sm text-red-500">{formError}</p>}
      {createMutation.isError && (
        <p className="text-sm text-red-500">יצירת ההזמנה נכשלה — בדוק את השדות ונסה שוב.</p>
      )}

      <Button onClick={handleSubmit} disabled={createMutation.isPending}>
        {createMutation.isPending ? "יוצר..." : "יצירת הזמנה"}
      </Button>
    </div>
  );
}
