"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Award, Pencil, Plus, Trash2 } from "lucide-react";
import { useOffers, useCreateOffer, useUpdateOffer, useDeleteOffer } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Supplier } from "@/types";
import { priceIntelligenceService, type PriceOfferComparison } from "@/services/price-intelligence-service";

interface PriceComparisonProps {
  productId: number;
  primarySupplierId: number;
  primarySupplierName: string;
  primaryPrice: number | null;
  currency: string;
  suppliers: Supplier[] | undefined;
  canManage: boolean;
}

function money(value: number, currency: string) {
  try {
    return new Intl.NumberFormat("he-IL", { style: "currency", currency: currency || "ILS", maximumFractionDigits: 3 }).format(value);
  } catch {
    return `${value.toLocaleString("he-IL", { maximumFractionDigits: 3 })} ${currency || "ILS"}`;
  }
}

function normalizedUnitLabel(unit: string | null) {
  const labels: Record<string, string> = { UNIT: "יחידה", KG: "ק״ג", G: "גרם", L: "ליטר", ML: "מ״ל", M: "מטר", PACK: "מארז", CARTON: "קרטון" };
  return unit ? labels[unit] ?? unit : "יחידה לא ידועה";
}

/** Supplier comparison uses the server's unit/currency-aware ranking.
 * It never changes the product's primary price or existing order snapshots.
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
  const { data: offers = [], isLoading: offersLoading, isError: offersError } = useOffers(productId);
  const comparison = useQuery({
    queryKey: ["price-intelligence", "comparison", productId],
    queryFn: () => priceIntelligenceService.compareProduct(productId),
    enabled: productId > 0,
    retry: 1,
  });
  const createOffer = useCreateOffer(productId);
  const updateOffer = useUpdateOffer(productId);
  const deleteOffer = useDeleteOffer(productId);
  const [addingOffer, setAddingOffer] = useState(false);
  const [newSupplierId, setNewSupplierId] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newUnit, setNewUnit] = useState("");
  const [newCartonSize, setNewCartonSize] = useState("");
  const [newCurrency, setNewCurrency] = useState(currency || "ILS");
  const [error, setError] = useState<string | null>(null);

  const alreadyOfferedSupplierIds = new Set([primarySupplierId, ...offers.map((o) => o.supplier_id)]);
  const availableSuppliers = (suppliers ?? []).filter((s) => s.active && !alreadyOfferedSupplierIds.has(s.id));
  const offerBySupplier = useMemo(() => new Map(offers.map((offer) => [offer.supplier_id, offer])), [offers]);

  const comparableRows = comparison.data?.offers ?? [];
  const incomparableRows = comparison.data?.incomparable_offers ?? [];
  const cheapest = comparison.data?.best_offer ?? null;
  const loading = offersLoading || comparison.isLoading;

  const handleAddOffer = () => {
    setError(null);
    if (editingOfferId === null && !newSupplierId) return setError("בחר ספק.");
    const price = Number(newPrice);
    if (!Number.isFinite(price) || price <= 0) return setError("הזן מחיר גדול מאפס; מחיר חסר יש להשאיר לא מוגדר.");
    if (!newUnit.trim()) return setError("יש להזין יחידת מכירה כדי למנוע השוואה שגויה בין אריזות שונות.");
    const cartonSize = newCartonSize.trim() ? Number(newCartonSize) : undefined;
    if (/(קרטון|ארגז|carton|case)/i.test(newUnit.trim()) && (!cartonSize || !Number.isInteger(cartonSize) || cartonSize <= 0)) {
      return setError("כשהמחיר הוא לקרטון, יש להזין כמה יחידות יש בקרטון.");
    }
    if (newCartonSize.trim() && (!cartonSize || !Number.isInteger(cartonSize) || cartonSize <= 0)) {
      return setError("מספר היחידות בקרטון חייב להיות מספר שלם וחיובי.");
    }

    const resetOfferForm = () => {
      setAddingOffer(false);
      setEditingOfferId(null);
      setNewSupplierId("");
      setNewPrice("");
      setNewUnit("");
      setNewCartonSize("");
      setError(null);
    };
    const onError = (err: unknown) => {
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(message || (editingOfferId !== null ? "עדכון הצעת המחיר נכשל." : "הוספת הצעת המחיר נכשלה."));
    };
    if (editingOfferId !== null) {
      updateOffer.mutate(
        { offerId: editingOfferId, input: { price, currency: newCurrency, unit: newUnit.trim(), units_per_carton: cartonSize } },
        { onSuccess: resetOfferForm, onError },
      );
    } else {
      createOffer.mutate(
        { supplier_id: Number(newSupplierId), price, currency: newCurrency, unit: newUnit.trim(), units_per_carton: cartonSize },
        { onSuccess: resetOfferForm, onError },
      );
    }
  };

  const renderRow = (row: PriceOfferComparison, index: number, isComparable: boolean) => {
    const offer = offerBySupplier.get(row.supplier_id);
    const isPrimary = row.primary || row.supplier_id === primarySupplierId;
    const isBest = isComparable && cheapest?.supplier_id === row.supplier_id;
    const supplierLabel = isPrimary ? (primarySupplierName || row.supplier_name || `ספק #${row.supplier_id}`) : (row.supplier_name || `ספק #${row.supplier_id}`);
    const saving = comparison.data?.current && isComparable
      ? comparison.data.current.normalized_price - row.normalized_price
      : null;
    return (
      <div key={`${row.supplier_id}-${index}-${isComparable}`} className="grid grid-cols-[minmax(0,1.2fr)_minmax(100px,0.8fr)] gap-3 px-3 py-3 text-sm sm:grid-cols-[minmax(0,1.2fr)_minmax(110px,0.8fr)_minmax(100px,0.8fr)_auto]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 font-medium text-slate-900">
            <span className="truncate">{supplierLabel}</span>
            {isPrimary && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">ספק ראשי</span>}
            {isBest && <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800">הזול ביותר</span>}
          </div>
          <div className="mt-1 text-xs text-slate-500">{row.unit || "יחידת מחיר לא צוינה"}{row.comparison_unit ? ` · השוואה לפי ${normalizedUnitLabel(row.comparison_unit)}` : ""}</div>
        </div>
        <div className="text-right">
          <div className="font-semibold text-slate-900">{money(row.price, row.currency)}</div>
          <div className="text-xs text-slate-400">מחיר מקורי</div>
        </div>
        <div className="hidden text-right sm:block">
          {isComparable ? <><div className="font-semibold text-slate-900">{money(row.normalized_price, row.currency)}</div><div className="text-xs text-slate-400">לפי יחידת השוואה</div></> : <span className="text-xs text-amber-700">לא ניתן להשוות</span>}
        </div>
        <div className="flex items-center justify-end gap-2">
          {saving !== null && isComparable && <span className={saving > 0.000001 ? "text-xs font-semibold text-emerald-700" : saving < -0.000001 ? "text-xs font-semibold text-red-600" : "text-xs text-slate-400"}>{saving > 0.000001 ? "חיסכון " : saving < -0.000001 ? "יקר ב־" : ""}{Math.abs(saving) > 0.000001 ? money(Math.abs(saving), comparison.data?.current?.currency || currency) : "—"}</span>}
          {canManage && offer && <><button type="button" onClick={() => { setEditingOfferId(offer.id); setNewSupplierId(String(offer.supplier_id)); setNewPrice(String(offer.price)); setNewUnit(offer.unit ?? ""); setNewCartonSize(offer.units_per_carton != null ? String(offer.units_per_carton) : ""); setNewCurrency(offer.currency || "ILS"); setError(null); setAddingOffer(true); }} disabled={updateOffer.isPending} className="rounded p-1.5 text-slate-400 hover:bg-indigo-50 hover:text-indigo-600 disabled:opacity-50" aria-label={`עריכת הצעת ${row.supplier_name ?? "ספק"}`} title="עריכת הצעת מחיר"><Pencil size={14} /></button><button type="button" onClick={() => deleteOffer.mutate(offer.id)} disabled={deleteOffer.isPending} className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50" aria-label={`הסרת הצעת ${row.supplier_name ?? "ספק"}`} title="הסרת הצעת מחיר"><Trash2 size={14} /></button></>}
        </div>
      </div>
    );
  };

  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900"><Award size={16} className="text-indigo-600" />השוואת מחירים בין ספקים</h3>
          <p className="mt-1 text-xs text-slate-500">הדירוג מתחשב ביחידת המידה ובמטבע. הצעות שאינן בנות השוואה מוצגות בנפרד.</p>
        </div>
        {canManage && !addingOffer && availableSuppliers.length > 0 && <Button onClick={() => setAddingOffer(true)} variant="secondary" className="h-8 text-xs"><Plus size={14} />הוספת הצעת ספק</Button>}
      </div>

      {loading && <div className="space-y-2 py-2"><div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" /><div className="h-10 animate-pulse rounded bg-slate-50" /></div>}
      {!loading && (comparison.isError || offersError) && <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-800"><AlertTriangle size={15} className="mt-0.5 shrink-0" /><div>לא ניתן לטעון את השוואת הספקים. <button type="button" onClick={() => { comparison.refetch(); }} className="font-semibold underline">נסה שוב</button></div></div>}

      {!loading && !comparison.isError && comparison.data && <>
        {comparison.data.current && comparison.data.best_offer && comparison.data.saving_per_unit > 0 && <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-500">מחיר ספק ראשי</div><div className="mt-1 font-bold">{money(comparison.data.current.normalized_price, comparison.data.current.currency)}</div><div className="text-xs text-slate-400">ל־{normalizedUnitLabel(comparison.data.current.comparison_unit)}</div></div>
          <div className="rounded-lg bg-emerald-50 p-3"><div className="text-xs text-emerald-800">חיסכון אפשרי ליחידה</div><div className="mt-1 font-bold text-emerald-800">{money(comparison.data.saving_per_unit, comparison.data.current.currency)}</div><div className="text-xs text-emerald-700">{comparison.data.saving_percent.toFixed(1)}% פחות</div></div>
          <div className="rounded-lg bg-indigo-50 p-3"><div className="text-xs text-indigo-800">הספק הזול ביותר</div><div className="mt-1 font-bold text-indigo-900">{comparison.data.best_offer.supplier_name || `ספק #${comparison.data.best_offer.supplier_id}`}</div><div className="text-xs text-indigo-700">{money(comparison.data.best_offer.normalized_price, comparison.data.best_offer.currency)} ליחידת השוואה</div></div>
        </div>}

        {comparableRows.length > 0 ? <div className="overflow-hidden rounded-lg border border-slate-200">
          <div className="hidden grid-cols-[minmax(0,1.2fr)_minmax(110px,0.8fr)_minmax(100px,0.8fr)_auto] gap-3 bg-slate-50 px-3 py-2 text-[11px] font-semibold text-slate-500 sm:grid"><span>ספק / יחידת מכירה</span><span className="text-right">מחיר מקורי</span><span className="text-right">מחיר מנורמל</span><span className="text-right">פער / פעולה</span></div>
          <div className="divide-y divide-slate-100">{comparableRows.map((row, i) => renderRow(row, i, true))}</div>
        </div> : <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-sm text-slate-500">{primaryPrice != null && primaryPrice > 0 ? "אין עדיין הצעות מחיר בנות השוואה למוצר." : "אין מחיר ראשי או הצעה שאפשר להשוות כרגע."}</div>}

        {incomparableRows.length > 0 && <div className="overflow-hidden rounded-lg border border-amber-200">
          <div className="flex items-start gap-2 bg-amber-50 p-3 text-xs text-amber-900"><AlertTriangle size={15} className="mt-0.5 shrink-0" /><div><div className="font-semibold">הצעות שדורשות השלמת נתונים</div><div className="mt-0.5">לא נדרג אותן בטעות כמחיר הזול ביותר. בדוק מטבע, יחידת מכירה ויחידות בקרטון.</div></div></div>
          <div className="divide-y divide-amber-100">{incomparableRows.map((row, i) => <ReactIncomparableRow key={`${row.supplier_id}-${i}`} row={row} render={renderRow} index={i} />)}</div>
        </div>}
      </>}

      {!loading && !comparison.isError && comparison.data && comparableRows.length <= 1 && incomparableRows.length === 0 && offers.length === 0 && <p className="text-xs text-slate-500">עדיין לא הוזנו מחירים מספקים חלופיים.</p>}

      {addingOffer && <div className="space-y-3 rounded-lg border border-indigo-100 bg-indigo-50/40 p-3">
        <div className="font-semibold text-sm">{editingOfferId !== null ? "עריכת הצעת מחיר" : "הוספת הצעת מחיר"}</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {editingOfferId === null && <label className="text-xs text-slate-600">ספק<select value={newSupplierId} onChange={(e) => setNewSupplierId(e.target.value)} className="mt-1 block h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm"><option value="">בחר ספק...</option>{availableSuppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>}
          <label className="text-xs text-slate-600">מחיר חיובי<input type="number" min="0.01" step="0.01" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} placeholder="למשל 12.50" className="mt-1 block h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" /></label>
          <label className="text-xs text-slate-600">מטבע<select value={newCurrency} onChange={(e) => setNewCurrency(e.target.value)} className="mt-1 block h-10 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm"><option value="ILS">שקל (ILS)</option><option value="USD">דולר (USD)</option><option value="EUR">אירו (EUR)</option>{newCurrency && !["ILS", "USD", "EUR"].includes(newCurrency) && <option value={newCurrency}>{newCurrency}</option>}</select></label>
          <label className="text-xs text-slate-600">יחידת מכירה<input value={newUnit} onChange={(e) => setNewUnit(e.target.value)} placeholder="יחידה, ק״ג, ליטר, קרטון..." required className="mt-1 block h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" /></label>
          <label className="text-xs text-slate-600 sm:col-span-2">יחידות בקרטון (רק למחיר קרטון)<input type="number" min="1" step="1" value={newCartonSize} onChange={(e) => setNewCartonSize(e.target.value)} placeholder="למשל 12" className="mt-1 block h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm" /></label>
        </div>
        {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
        <div className="flex gap-2"><Button onClick={handleAddOffer} disabled={createOffer.isPending || updateOffer.isPending} className="text-xs">{createOffer.isPending || updateOffer.isPending ? "שומר..." : editingOfferId !== null ? "שמירת עדכון" : "שמירת הצעה"}</Button><Button variant="ghost" onClick={() => { setAddingOffer(false); setEditingOfferId(null); setError(null); }} disabled={createOffer.isPending || updateOffer.isPending} className="text-xs">ביטול</Button></div>
      </div>}
    </section>
  );
}

function ReactIncomparableRow({ row, render, index }: { row: PriceOfferComparison; render: (row: PriceOfferComparison, index: number, comparable: boolean) => React.ReactNode; index: number }) {
  return <>{render(row, index, false)}<div className="px-3 pb-3 text-xs text-amber-800">{row.incomparable_reason || "נתוני המחיר אינם תואמים"}</div></>;
}
