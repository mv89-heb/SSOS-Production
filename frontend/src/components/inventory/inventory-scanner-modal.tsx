"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowUpFromLine, Camera, CheckCircle2, ClipboardCheck, PackageSearch, RefreshCw, ScanLine, X } from "lucide-react";
import { inventoryService, type InventoryMovementType } from "@/services/inventory-service";
import type { Product } from "@/types";

interface InventoryScannerModalProps {
  open: boolean;
  onClose: () => void;
}

const movementMeta: Record<"count" | "receipt" | "issue", { label: string; description: string }> = {
  count: { label: "ספירה", description: "עדכון הכמות הפיזית שנמצאה במחסן" },
  receipt: { label: "קבלה", description: "הוספת כמות למלאי" },
  issue: { label: "ניפוק", description: "הפחתת כמות מהמלאי" },
};

export default function InventoryScannerModal({ open, onClose }: InventoryScannerModalProps) {
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<BarcodeDetector | null>(null);
  const [supported, setSupported] = useState(false);
  const [running, setRunning] = useState(false);
  const [value, setValue] = useState("");
  const [product, setProduct] = useState<Product | null>(null);
  const [movementType, setMovementType] = useState<"count" | "receipt" | "issue" | null>(null);
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setRunning(false);
  };

  const resetProduct = () => {
    setProduct(null);
    setMovementType(null);
    setQuantity("");
    setNote("");
    setSuccess("");
    setError("");
  };

  const startNewScan = () => {
    stopCamera();
    resetProduct();
    setValue("");
  };

  useEffect(() => {
    if (!open) return;
    const available = typeof window !== "undefined" && "BarcodeDetector" in window;
    setSupported(available);
    if (available) {
      detectorRef.current = new BarcodeDetector({ formats: ["ean_13", "ean_8", "code_128", "code_39", "itf", "upc_a", "upc_e"] });
    }
    return () => stopCamera();
  }, [open]);

  const lookup = async (raw?: string) => {
    const code = (raw ?? value).trim();
    if (!code) return;
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const result = await inventoryService.lookupProduct(code);
      setProduct(result);
      setMovementType(null);
      setQuantity("");
      setNote("");
      stopCamera();
    } catch (e) {
      setProduct(null);
      setError(e instanceof Error ? e.message : "המוצר לא נמצא.");
    } finally {
      setLoading(false);
    }
  };

  const scanFrame = async () => {
    if (!videoRef.current || !detectorRef.current || !streamRef.current) return;
    try {
      const codes = await detectorRef.current.detect(videoRef.current);
      if (codes.length > 0 && codes[0].rawValue) {
        setValue(codes[0].rawValue);
        await lookup(codes[0].rawValue);
        return;
      }
    } catch {
      // Continue scanning through transient camera-frame detection errors.
    }
    if (streamRef.current) window.requestAnimationFrame(scanFrame);
  };

  const startCamera = async () => {
    setError("");
    setSuccess("");
    resetProduct();
    if (!supported || !detectorRef.current) {
      setError("הדפדפן אינו תומך בסריקת ברקוד. השתמש בחיפוש ידני.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      streamRef.current = stream;
      if (!videoRef.current) return;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setRunning(true);
      scanFrame();
    } catch {
      setError("לא ניתן לפתוח את המצלמה. יש לאשר הרשאת מצלמה ולנסות שוב.");
    }
  };

  const chooseMovement = (type: "count" | "receipt" | "issue") => {
    if (!product) return;
    setMovementType(type);
    setSuccess("");
    setError("");
    setQuantity(type === "count" ? String(product.current_stock ?? 0) : "");
  };

  const saveMovement = async () => {
    if (!product || !movementType) return;
    const qty = Number(quantity);
    if (!Number.isInteger(qty) || qty < 0 || (movementType !== "count" && qty <= 0)) {
      setError(movementType === "count" ? "בספירה יש להזין מספר שלם שאינו שלילי." : "בקבלה או ניפוק יש להזין כמות גדולה מאפס.");
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const result = await inventoryService.createMovement({ product_id: product.id, movement_type: movementType as InventoryMovementType, quantity: qty, note: note.trim() || undefined });
      const balanceAfter = Number(result.movement.balance_after ?? 0);
      setProduct((current) => current ? { ...current, current_stock: balanceAfter } : current);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["inventory", "summary"] }),
        queryClient.invalidateQueries({ queryKey: ["inventory", "recommendations"] }),
        queryClient.invalidateQueries({ queryKey: ["inventory", "history", product.id] }),
        queryClient.invalidateQueries({ queryKey: ["procurement-intelligence"] }),
      ]);
      const label = movementMeta[movementType].label;
      setSuccess(`${label} של ${product.name} נקלטה בהצלחה. מלאי נוכחי: ${balanceAfter}.`);
      setMovementType(null);
      setQuantity("");
      setNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "שמירת התנועה נכשלה.");
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[250] flex items-end justify-center bg-slate-950/60 p-0 backdrop-blur-sm sm:items-center sm:p-4" dir="rtl">
      <div className="max-h-[94vh] w-full max-w-2xl overflow-y-auto rounded-t-3xl bg-white shadow-2xl dark:bg-slate-950 sm:rounded-3xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 p-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
          <div className="flex items-center gap-3"><ScanLine className="text-indigo-600" size={23} /><div><h2 className="font-black">סריקת ברקוד</h2><p className="text-xs text-slate-500">סריקה → בחירת פעולה → עדכון מלאי</p></div></div>
          <button onClick={onClose} className="rounded-xl bg-slate-100 p-2 dark:bg-slate-900" aria-label="סגור"><X size={19} /></button>
        </div>

        <div className="p-4 sm:p-5">
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-slate-950">
            <video ref={videoRef} muted playsInline className={`h-full w-full object-cover ${running ? "block" : "hidden"}`} />
            {!running && <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-white"><Camera size={42} className="text-slate-400" /><p className="font-bold">המצלמה כבויה</p><button onClick={startCamera} className="rounded-xl bg-indigo-600 px-5 py-3 font-black hover:bg-indigo-500">פתח מצלמה</button></div>}
            {running && <div className="pointer-events-none absolute inset-0 flex items-center justify-center"><div className="h-40 w-64 rounded-2xl border-2 border-white shadow-[0_0_0_9999px_rgba(0,0,0,.25)]" /></div>}
          </div>
          {running && <div className="flex justify-center p-3"><button onClick={stopCamera} className="inline-flex items-center gap-2 rounded-xl bg-slate-100 px-4 py-2 text-sm font-black dark:bg-slate-900"><X size={17} /> סגור מצלמה</button></div>}

          <div className="mt-4 flex gap-2">
            <input value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => e.key === "Enter" && lookup()} placeholder="או הזן ברקוד / מק״ט ידנית" className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900" />
            <button disabled={loading} onClick={() => lookup()} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-black text-white disabled:opacity-50">{loading ? <RefreshCw className="animate-spin" size={18} /> : <PackageSearch size={18} />} חפש</button>
          </div>

          {!supported && <p className="mt-3 text-xs text-slate-500">סריקת מצלמה אינה זמינה בדפדפן הזה; החיפוש הידני עדיין זמין.</p>}
          {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-300">{error}</p>}
          {success && <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm font-bold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">{success}</p>}

          {product && <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950/20">
            <div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 shrink-0 text-emerald-600" size={24} /><div className="min-w-0 flex-1"><h3 className="text-xl font-black">{product.name}</h3><p className="mt-1 text-sm text-slate-600 dark:text-slate-300">מק״ט: {product.sku || "—"} · ברקוד: {product.barcode || "—"}</p><div className="mt-4 grid grid-cols-3 gap-2 text-center"><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">מלאי</span><strong className="text-xl">{product.current_stock ?? 0}</strong></div><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">מינימום</span><strong className="text-xl">{product.min_stock ?? "—"}</strong></div><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">יעד</span><strong className="text-xl">{product.recommended_stock ?? "—"}</strong></div></div></div></div>

            {!movementType && <div className="mt-5"><p className="mb-3 text-sm font-black">מה תרצה לעשות עם המוצר?</p><div className="grid grid-cols-1 gap-2 sm:grid-cols-3"><button onClick={() => chooseMovement("count")} className="inline-flex min-h-16 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-black text-white hover:bg-indigo-500"><ClipboardCheck size={19} /> ספירה</button><button onClick={() => chooseMovement("receipt")} className="inline-flex min-h-16 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 font-black text-white hover:bg-emerald-500"><ArrowDownToLine size={19} /> קבלה</button><button onClick={() => chooseMovement("issue")} className="inline-flex min-h-16 items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-3 font-black text-white hover:bg-amber-400"><ArrowUpFromLine size={19} /> ניפוק</button></div></div>}

            {movementType && <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950"><div className="flex items-center justify-between gap-3"><div><h4 className="font-black">{movementMeta[movementType].label}</h4><p className="mt-1 text-xs text-slate-500">{movementMeta[movementType].description}</p></div><button onClick={() => setMovementType(null)} className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-black dark:bg-slate-900">החלף פעולה</button></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="block"><span className="mb-1 block text-xs font-bold text-slate-500">כמות</span><input autoFocus type="number" min="0" step="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-lg font-black outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900" /></label><label className="block"><span className="mb-1 block text-xs font-bold text-slate-500">הערה (אופציונלי)</span><input value={note} onChange={(e) => setNote(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900" /></label></div><button disabled={saving} onClick={saveMovement} className="mt-4 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 font-black text-white disabled:opacity-50">{saving ? <RefreshCw className="animate-spin" size={18} /> : <CheckCircle2 size={18} />} שמור {movementMeta[movementType].label}</button></div>}

            <div className="mt-3 flex flex-wrap gap-2">
              <button onClick={startNewScan} className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-black dark:bg-slate-900">סרוק מוצר אחר</button>
              <button onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-black dark:border-slate-800">סיום</button>
            </div>
          </div>}
        </div>
      </div>
    </div>
  );
}
