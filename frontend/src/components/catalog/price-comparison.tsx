"use client";
import { useState } from "react";
import { Trash2, Plus, Award } from "lucide-react";
import { useOffers, useCreateOffer, useDeleteOffer } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Supplier } from "@/types";

interface PriceComparisonProps {
  productId: number;
  primarySupplierId: number;
  primarySupplierName: string;
  primaryPrice: number;
  currency: string;
  suppliers: Supplier[] | undefined;
  canManage: boolean;
}

/**
 * Phase 2: Supplier Catalog Engine. Shows this product's price across every
 * supplier on file for it — the product's own primary listing plus any
 * alternate-supplier offers — cheapest first, with the cheapest one marked.
 * Purely comparison data: adding/removing an offer here never changes an
 * order — orders always snapshot the product's own primary price.
 */
export function PriceComparison({
  productId,
  primarySupplierId,
  primarySupplierName,
  primaryPrice,
  currency,
  suppliers,
  canManage,
}: PriceComparisonProps) {
  const { data: offers, isLoading } = useOffers(productId);
  const createOffer = useCreateOffer(productId);
  const deleteOffer = useDeleteOffer(productId);

  const [addingOffer, setAddingOffer] = useState(false);
  const [newSupplierId, setNewSupplierId] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newUnit, setNewUnit] = useState("");
  const [error, setError] = useState<string | null>(null);

  const alreadyOfferedSupplierIds = new Set([
    primarySupplierId,
    ...(offers ?? []).map((o) => o.supplier_id),
  ]);
  const availableSuppliers = (suppliers ?? []).filter((s) => !alreadyOfferedSupplierIds.has(s.id));

  const rows = [
    { key: "primary", supplierName: primarySupplierName, price: primaryPrice, unit: null as string | null, offerId: null as number | null },
    ...((offers ?? []).map((o) => ({
      key: `offer-${o.id}`,
      supplierName: o.supplier_name ?? `#${o.supplier_id}`,
      price: o.price,
      unit: o.unit,
      offerId: o.id,
    }))),
  ].sort((a, b) => a.price - b.price);

  const cheapestPrice = rows.length > 0 ? Math.min(...rows.map((r) => r.price)) : null;

  const handleAddOffer = () => {
    setError(null);
    if (!newSupplierId) return setError("בחר ספק.");
    const price = Number(newPrice);
    if (!Number.isFinite(price) || price < 0) return setError("הזן מחיר תקין.");

    createOffer.mutate(
      { supplier_id: Number(newSupplierId), price, unit: newUnit.trim() || undefined },
      {
        onSuccess: () => {
          setAddingOffer(false);
          setNewSupplierId("");
          setNewPrice("");
          setNewUnit("");
        },
        onError: (err) => {
          const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
          setError(message || "הוספת הצעת המחיר נכשלה.");
        },
      }
    );
  };

  return (
    <div className="space-y-2 rounded-lg border border-slate-100 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">השוואת מחירים בין ספקים</h3>
        {canManage && !addingOffer && availableSuppliers.length > 0 && (
          <button
            type="button"
            onClick={() => setAddingOffer(true)}
            className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            <Plus size={14} />
            הוספת ספק להשוואה
          </button>
        )}
      </div>

      {isLoading && <p className="text-xs text-slate-400">טוען...</p>}

      {!isLoading && (
        <div className="divide-y divide-slate-200 rounded-md bg-white">
          {rows.map((row) => (
            <div key={row.key} className="flex items-center justify-between px-3 py-2 text-sm">
              <div className="flex items-center gap-2">
                {row.price === cheapestPrice && (
                  <span title="המחיר הזול ביותר" className="text-amber-500">
                    <Award size={14} />
                  </span>
                )}
                <span className="text-slate-900">{row.supplierName}</span>
                {row.key === "primary" && (
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">ספק ראשי</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="font-medium text-slate-900">
                  {currency} {row.price.toLocaleString()}
                  {row.unit && <span className="text-slate-400"> / {row.unit}</span>}
                </span>
                {canManage && row.offerId != null && (
                  <button
                    onClick={() => deleteOffer.mutate(row.offerId as number)}
                    className="text-slate-300 hover:text-red-500"
                    aria-label="הסרת הצעת מחיר"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {addingOffer && (
        <div className="space-y-2 rounded-md border border-slate-200 bg-white p-3">
          <div className="grid grid-cols-2 gap-2">
            <Select value={newSupplierId} onChange={(e) => setNewSupplierId(e.target.value)}>
              <option value="">בחר ספק...</option>
              {availableSuppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
            <Input
              type="number"
              min={0}
              step="0.01"
              placeholder="מחיר"
              value={newPrice}
              onChange={(e) => setNewPrice(e.target.value)}
            />
          </div>
          <Input
            placeholder='יחידת מכירה (לדוגמה: קילו, ארגז) — אופציונלי'
            value={newUnit}
            onChange={(e) => setNewUnit(e.target.value)}
          />
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex gap-2">
            <Button onClick={handleAddOffer} disabled={createOffer.isPending} className="text-xs">
              {createOffer.isPending ? "שומר..." : "הוספה"}
            </Button>
            <Button
              variant="ghost"
              className="text-xs"
              onClick={() => {
                setAddingOffer(false);
                setError(null);
              }}
              disabled={createOffer.isPending}
            >
              ביטול
            </Button>
          </div>
        </div>
      )}

      {!isLoading && (offers?.length ?? 0) === 0 && !addingOffer && (
        <p className="text-xs text-slate-400">אין עדיין ספקים נוספים להשוואה עבור מוצר זה.</p>
      )}
    </div>
  );
}
