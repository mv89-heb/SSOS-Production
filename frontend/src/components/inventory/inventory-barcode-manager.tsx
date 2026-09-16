"use client";

import { useMemo, useState } from "react";
import { CheckSquare, Loader2, Minus, Plus, Printer, RefreshCw, Square, X } from "lucide-react";
import { inventoryService, type BarcodeLabelItem } from "@/services/inventory-service";
import type { Product } from "@/types";

interface Props {
  open: boolean;
  products: Product[];
  displayedProducts?: Product[];
  onClose: () => void;
  onRefresh: () => Promise<void> | void;
}

const MAX_TOTAL_LABELS = 5000;

export default function InventoryBarcodeManager({ open, products, displayedProducts, onClose, onRefresh }: Props) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [quantities, setQuantities] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const visibleProducts = displayedProducts ?? products;
  const missingCount = products.filter((product) => !product.barcode?.trim()).length;
  const selectedCount = selectedIds.length;

  const selectedItems = useMemo<BarcodeLabelItem[]>(
    () => selectedIds.map((productId) => ({ product_id: productId, quantity: quantities[productId] ?? 1 })),
    [quantities, selectedIds],
  );
  const selectedLabelCount = useMemo(() => selectedItems.reduce((sum, item) => sum + item.quantity, 0), [selectedItems]);
  const allLabelCount = products.length;
  const selectedPageCount = Math.ceil(selectedLabelCount / 10);
  const visibleIds = useMemo(() => visibleProducts.map((product) => product.id), [visibleProducts]);

  if (!open) return null;

  const setQuantity = (id: number, value: number) => {
    const quantity = Math.max(1, Math.min(5000, Math.floor(Number.isFinite(value) ? value : 1)));
    setQuantities((current) => ({ ...current, [id]: quantity }));
  };

  const toggle = (id: number) => {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  const selectVisible = () => {
    setSelectedIds((current) => Array.from(new Set([...current, ...visibleIds])));
  };

  const clearSelection = () => setSelectedIds([]);

  const refreshAfterGeneration = async (generatedProducts: Product[]) => {
    if (!generatedProducts.length) return;
    try {
      await onRefresh();
    } catch {
      // Barcode generation already succeeded; a refresh failure should not turn success into an error.
    }
  };

  const generateMissing = async () => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await inventoryService.generateBarcodes();
      setMessage(result.generated_count ? `נוצרו ${result.generated_count} ברקודים חדשים. ברקודים קיימים נשמרו.` : "לכל המוצרים הפעילים כבר יש ברקוד.");
      await refreshAfterGeneration(result.products);
    } catch (err) {
      setError(err instanceof Error ? err.message : "יצירת הברקודים נכשלה.");
    } finally {
      setBusy(false);
    }
  };

  const print = async (items: BarcodeLabelItem[], labelCount: number) => {
    if (!items.length || labelCount < 1) return;
    if (labelCount > MAX_TOTAL_LABELS) {
      setError(`ניתן להדפיס עד ${MAX_TOTAL_LABELS.toLocaleString("he-IL")} מדבקות בפעולה אחת.`);
      return;
    }

    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const blob = await inventoryService.printBarcodeLabels(items);
      const url = URL.createObjectURL(blob);
      const popup = window.open(url, "_blank", "noopener,noreferrer");
      if (!popup) {
        const link = document.createElement("a");
        link.href = url;
        link.download = "inventory-barcode-labels.pdf";
        link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      setMessage(`נוצר PDF עם ${labelCount.toLocaleString("he-IL")} מדבקות (${Math.ceil(labelCount / 10)} עמודים).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "הדפסת המדבקות נכשלה.");
    } finally {
      setBusy(false);
    }
  };

  const printAll = () => {
    void print(products.map((product) => ({ product_id: product.id, quantity: 1 })), allLabelCount);
  };

  const printSelected = () => {
    void print(selectedItems, selectedLabelCount);
  };

  return (
    <div dir="rtl" className="fixed inset-0 z-[260] flex items-end justify-center bg-slate-950/60 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <div className="relative flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl dark:bg-slate-950 sm:rounded-3xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5 dark:border-slate-800">
          <div>
            <div className="text-xs font-black text-indigo-600">ברקודים פנימיים</div>
            <h2 className="mt-1 text-2xl font-black">ניהול והדפסת מדבקות</h2>
            <p className="mt-1 text-sm text-slate-500">ברקוד מזהה את המוצר הארגוני, ללא תלות בספק. ניתן לבחור כמה מדבקות להדפיס לכל מוצר.</p>
          </div>
          <button onClick={onClose} disabled={busy} className="rounded-xl bg-slate-100 p-2 disabled:opacity-50 dark:bg-slate-900" aria-label="סגירה"><X size={19} /></button>
        </div>

        <div className="grid gap-3 p-5 sm:grid-cols-4">
          <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-900"><div className="text-xs font-bold text-slate-500">מוצרים פעילים</div><div className="mt-1 text-2xl font-black">{products.length}</div></div>
          <div className="rounded-2xl bg-amber-50 p-4 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"><div className="text-xs font-bold">ללא ברקוד</div><div className="mt-1 text-2xl font-black">{missingCount}</div></div>
          <div className="rounded-2xl bg-indigo-50 p-4 text-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-200"><div className="text-xs font-bold">מוצרים נבחרים</div><div className="mt-1 text-2xl font-black">{selectedCount}</div></div>
          <div className="rounded-2xl bg-emerald-50 p-4 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200"><div className="text-xs font-bold">מדבקות נבחרות</div><div className="mt-1 text-2xl font-black">{selectedLabelCount}</div></div>
        </div>

        <div className="flex flex-wrap gap-2 border-b border-slate-200 px-5 pb-4 dark:border-slate-800">
          <button onClick={generateMissing} disabled={busy || missingCount === 0} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-black text-white disabled:opacity-50"><RefreshCw size={17} /> צור ברקודים חסרים</button>
          <button onClick={printAll} disabled={busy || !products.length || allLabelCount > MAX_TOTAL_LABELS} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-slate-900 px-4 text-sm font-black text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"><Printer size={17} /> הדפס מוצר אחד מכל מוצר</button>
          <button onClick={printSelected} disabled={busy || !selectedCount || selectedLabelCount > MAX_TOTAL_LABELS} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-black disabled:opacity-50 dark:border-slate-700"><Printer size={17} /> הדפס נבחרים ({selectedLabelCount})</button>
          <button onClick={selectVisible} disabled={busy || !visibleProducts.length} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-black dark:border-slate-700"><CheckSquare size={17} /> הוסף מוצגים</button>
          <button onClick={clearSelection} disabled={busy} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-black dark:border-slate-700"><Square size={17} /> נקה</button>
        </div>

        {(message || error) && <div className={`mx-5 mt-4 rounded-xl p-3 text-sm font-bold ${error ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"}`}>{error || message}</div>}

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs font-bold text-slate-500">
            <span>{visibleProducts.length} מוצרים מוצגים</span>
            <span>{selectedCount ? `${selectedLabelCount} מדבקות ≈ ${selectedPageCount} עמודי A4` : "בחר מוצרים והגדר כמות מדבקות"}</span>
          </div>
          <div className="space-y-2">
            {visibleProducts.map((product) => {
              const checked = selectedIds.includes(product.id);
              const quantity = quantities[product.id] ?? 1;
              return (
                <div key={product.id} className={`flex flex-wrap items-center gap-3 rounded-2xl border p-3 transition ${checked ? "border-indigo-300 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-950/30" : "border-slate-200 dark:border-slate-800"}`}>
                  <button type="button" onClick={() => toggle(product.id)} disabled={busy} className="flex min-w-0 flex-1 items-center gap-3 text-right">
                    {checked ? <CheckSquare className="shrink-0 text-indigo-600" size={20} /> : <Square className="shrink-0 text-slate-400" size={20} />}
                    <span className="min-w-0 flex-1"><span className="block truncate font-black">{product.name}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{product.sku || "ללא מק״ט"}</span></span>
                    <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-black ${product.barcode ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300" : "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"}`}>{product.barcode || "חסר"}</span>
                  </button>

                  <div className="flex shrink-0 items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-950" onClick={(event) => event.stopPropagation()}>
                    <button type="button" onClick={() => setQuantity(product.id, quantity - 1)} disabled={busy || quantity <= 1} className="rounded-lg p-2 disabled:opacity-30" aria-label={`הפחת כמות עבור ${product.name}`}><Minus size={15} /></button>
                    <input type="number" min={1} max={5000} value={quantity} onChange={(event) => setQuantity(product.id, Number(event.target.value))} disabled={busy} className="w-16 rounded-lg border-0 bg-transparent text-center text-sm font-black outline-none" aria-label={`כמות מדבקות עבור ${product.name}`} />
                    <button type="button" onClick={() => setQuantity(product.id, quantity + 1)} disabled={busy || quantity >= 5000} className="rounded-lg p-2 disabled:opacity-30" aria-label={`הוסף כמות עבור ${product.name}`}><Plus size={15} /></button>
                  </div>
                </div>
              );
            })}
            {!visibleProducts.length && <div className="p-10 text-center text-sm text-slate-500">אין מוצרים להצגה.</div>}
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-slate-200 p-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-xs text-slate-500">PDF בגודל A4, תבנית 2×5, Code 128 וטקסט מזהה. המגבלה היא 5,000 מדבקות בפעולת הדפסה.</span>
          <button onClick={onClose} disabled={busy} className="min-h-11 rounded-xl bg-slate-100 px-5 text-sm font-black disabled:opacity-50 dark:bg-slate-900">סיום</button>
        </div>
        {busy && <div className="absolute inset-x-0 bottom-0 flex justify-center pb-20"><div className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-xs font-bold text-white"><Loader2 className="animate-spin" size={15} /> מעבד…</div></div>}
      </div>
    </div>
  );
}
