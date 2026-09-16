"use client";

import { useMemo, useState } from "react";
import { CheckSquare, Loader2, Printer, RefreshCw, Square, X } from "lucide-react";
import { inventoryService } from "@/services/inventory-service";
import type { Product } from "@/types";

interface Props {
  open: boolean;
  products: Product[];
  displayedProducts?: Product[];
  onClose: () => void;
  onRefresh: () => Promise<void> | void;
}

export default function InventoryBarcodeManager({ open, products, displayedProducts, onClose, onRefresh }: Props) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const visibleProducts = displayedProducts ?? products;
  const missingCount = products.filter((product) => !product.barcode?.trim()).length;
  const selectedProducts = useMemo(() => products.filter((product) => selectedIds.includes(product.id)), [products, selectedIds]);

  if (!open) return null;

  const toggle = (id: number) => {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  const selectVisible = () => setSelectedIds(visibleProducts.map((product) => product.id));
  const clearSelection = () => setSelectedIds([]);

  const generateMissing = async () => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await inventoryService.generateBarcodes();
      await onRefresh();
      setMessage(result.generated_count ? `נוצרו ${result.generated_count} ברקודים חדשים. ברקודים קיימים נשמרו.` : "לכל המוצרים הפעילים כבר יש ברקוד.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "יצירת הברקודים נכשלה.");
    } finally {
      setBusy(false);
    }
  };

  const print = async (ids: number[]) => {
    if (!ids.length) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const blob = await inventoryService.printBarcodeLabels(ids);
      const url = URL.createObjectURL(blob);
      const popup = window.open(url, "_blank", "noopener,noreferrer");
      if (!popup) {
        const link = document.createElement("a");
        link.href = url;
        link.download = "inventory-barcode-labels.pdf";
        link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "הדפסת המדבקות נכשלה.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div dir="rtl" className="fixed inset-0 z-[260] flex items-end justify-center bg-slate-950/60 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl dark:bg-slate-950 sm:rounded-3xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5 dark:border-slate-800">
          <div>
            <div className="text-xs font-black text-indigo-600">ברקודים פנימיים</div>
            <h2 className="mt-1 text-2xl font-black">ניהול והדפסת מדבקות</h2>
            <p className="mt-1 text-sm text-slate-500">ברקוד מזהה את המוצר הארגוני, ללא תלות בספק. ספקים ומחירי ספק נשארים מידע נפרד.</p>
          </div>
          <button onClick={onClose} className="rounded-xl bg-slate-100 p-2 dark:bg-slate-900"><X size={19} /></button>
        </div>

        <div className="grid gap-3 p-5 sm:grid-cols-3">
          <div className="rounded-2xl bg-slate-50 p-4 dark:bg-slate-900"><div className="text-xs font-bold text-slate-500">מוצרים פעילים</div><div className="mt-1 text-2xl font-black">{products.length}</div></div>
          <div className="rounded-2xl bg-amber-50 p-4 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"><div className="text-xs font-bold">ללא ברקוד</div><div className="mt-1 text-2xl font-black">{missingCount}</div></div>
          <div className="rounded-2xl bg-indigo-50 p-4 text-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-200"><div className="text-xs font-bold">נבחרו</div><div className="mt-1 text-2xl font-black">{selectedIds.length}</div></div>
        </div>

        <div className="flex flex-wrap gap-2 border-b border-slate-200 px-5 pb-4 dark:border-slate-800">
          <button onClick={generateMissing} disabled={busy || missingCount === 0} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-black text-white disabled:opacity-50"><RefreshCw size={17} /> צור ברקודים חסרים</button>
          <button onClick={() => print(products.map((product) => product.id))} disabled={busy || !products.length} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-slate-900 px-4 text-sm font-black text-white disabled:opacity-50 dark:bg-white dark:text-slate-900"><Printer size={17} /> הדפס את כל המוצרים</button>
          <button onClick={() => print(selectedIds)} disabled={busy || !selectedIds.length} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-black disabled:opacity-50 dark:border-slate-700"><Printer size={17} /> הדפס נבחרים</button>
          <button onClick={selectVisible} disabled={busy || !visibleProducts.length} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-black dark:border-slate-700"><CheckSquare size={17} /> בחר מוצגים</button>
          <button onClick={clearSelection} disabled={busy} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-black dark:border-slate-700"><Square size={17} /> נקה</button>
        </div>

        {(message || error) && <div className={`mx-5 mt-4 rounded-xl p-3 text-sm font-bold ${error ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"}`}>{error || message}</div>}

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="mb-2 text-xs font-bold text-slate-500">{visibleProducts.length} מוצרים מוצגים</div>
          <div className="space-y-2">
            {visibleProducts.map((product) => {
              const checked = selectedIds.includes(product.id);
              return (
                <button key={product.id} onClick={() => toggle(product.id)} className={`flex w-full items-center gap-3 rounded-2xl border p-3 text-right transition ${checked ? "border-indigo-300 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-950/30" : "border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900"}`}>
                  {checked ? <CheckSquare className="shrink-0 text-indigo-600" size={20} /> : <Square className="shrink-0 text-slate-400" size={20} />}
                  <span className="min-w-0 flex-1"><span className="block truncate font-black">{product.name}</span><span className="mt-0.5 block truncate text-xs text-slate-500">{product.sku || "ללא מק״ט"}</span></span>
                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-black ${product.barcode ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300" : "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"}`}>{product.barcode || "חסר"}</span>
                </button>
              );
            })}
            {!visibleProducts.length && <div className="p-10 text-center text-sm text-slate-500">אין מוצרים להצגה.</div>}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-slate-200 p-4 dark:border-slate-800">
          <span className="text-xs text-slate-500">המדבקות מופקות כ-PDF בגודל A4, עם Code 128 וטקסט מזהה.</span>
          <button onClick={onClose} disabled={busy} className="min-h-11 rounded-xl bg-slate-100 px-5 text-sm font-black dark:bg-slate-900">סיום</button>
        </div>
        {busy && <div className="absolute inset-x-0 bottom-0 flex justify-center pb-20"><div className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-xs font-bold text-white"><Loader2 className="animate-spin" size={15} /> מעבד…</div></div>}
      </div>
    </div>
  );
}
