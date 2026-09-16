"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, PackageSearch, RefreshCw, ScanLine, X } from "lucide-react";
import { inventoryService } from "@/services/inventory-service";
import type { Product } from "@/types";

interface InventoryScannerModalProps {
  open: boolean;
  onClose: () => void;
  onProductFound?: (product: Product) => void;
}

export default function InventoryScannerModal({ open, onClose, onProductFound }: InventoryScannerModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<BarcodeDetector | null>(null);
  const [supported, setSupported] = useState(false);
  const [running, setRunning] = useState(false);
  const [value, setValue] = useState("");
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setRunning(false);
  };

  useEffect(() => {
    if (!open) return;
    const available = typeof window !== "undefined" && "BarcodeDetector" in window;
    setSupported(available);
    if (available) detectorRef.current = new BarcodeDetector({ formats: ["ean_13", "ean_8", "code_128", "code_39", "itf", "upc_a", "upc_e"] });
    return () => stopCamera();
  }, [open]);

  const lookup = async (raw?: string) => {
    const code = (raw ?? value).trim();
    if (!code) return;
    setLoading(true);
    setError("");
    try {
      const result = await inventoryService.lookupProduct(code);
      setProduct(result);
      stopCamera();
      onProductFound?.(result);
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
    setProduct(null);
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

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[250] flex items-end justify-center bg-slate-950/60 p-0 backdrop-blur-sm sm:items-center sm:p-4" dir="rtl">
      <div className="max-h-[94vh] w-full max-w-2xl overflow-y-auto rounded-t-3xl bg-white shadow-2xl dark:bg-slate-950 sm:rounded-3xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 p-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
          <div className="flex items-center gap-3"><ScanLine className="text-indigo-600" size={23} /><div><h2 className="font-black">סריקת ברקוד</h2><p className="text-xs text-slate-500">זיהוי מוצר ישירות מתוך המחסן</p></div></div>
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

          {product && <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950/20"><div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 shrink-0 text-emerald-600" size={24} /><div className="min-w-0 flex-1"><h3 className="text-xl font-black">{product.name}</h3><p className="mt-1 text-sm text-slate-600 dark:text-slate-300">מק״ט: {product.sku || "—"} · ברקוד: {product.barcode || "—"}</p><div className="mt-4 grid grid-cols-3 gap-2 text-center"><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">מלאי</span><strong className="text-xl">{product.current_stock ?? 0}</strong></div><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">מינימום</span><strong className="text-xl">{product.min_stock ?? "—"}</strong></div><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">יעד</span><strong className="text-xl">{product.recommended_stock ?? "—"}</strong></div></div></div></div></div>}
        </div>
      </div>
    </div>
  );
}
