"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, PackageSearch, RefreshCw, ScanLine, X } from "lucide-react";
import { inventoryService } from "@/services/inventory-service";
import type { Product } from "@/types";

export default function InventoryScanPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<BarcodeDetector | null>(null);
  const [supported, setSupported] = useState(false);
  const [running, setRunning] = useState(false);
  const [value, setValue] = useState("");
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const available = typeof window !== "undefined" && "BarcodeDetector" in window;
    setSupported(available);
    if (available) detectorRef.current = new BarcodeDetector({ formats: ["ean_13", "ean_8", "code_128", "code_39", "itf", "upc_a", "upc_e"] });
    return () => stopCamera();
  }, []);

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setRunning(false);
  };

  const lookup = async (raw?: string) => {
    const code = (raw ?? value).trim();
    if (!code) return;
    setLoading(true);
    setError("");
    try {
      const result = await inventoryService.lookupProduct(code);
      setProduct(result);
      stopCamera();
    } catch (e) {
      setProduct(null);
      setError(e instanceof Error ? e.message : "המוצר לא נמצא.");
    } finally {
      setLoading(false);
    }
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
      // Continue scanning; transient camera frames can fail detection.
    }
    if (streamRef.current) window.requestAnimationFrame(scanFrame);
  };

  return (
    <main dir="rtl" className="mx-auto max-w-2xl space-y-5 p-4 pb-12 sm:p-6">
      <header className="rounded-3xl bg-gradient-to-l from-indigo-700 to-blue-600 p-6 text-white shadow-sm">
        <div className="flex items-center gap-3"><ScanLine size={28} /><div><h1 className="text-2xl font-black">סריקת ברקוד</h1><p className="mt-1 text-sm text-indigo-100">סרוק מוצר מהטלפון וקבל מיד את המלאי שלו.</p></div></div>
      </header>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="relative aspect-[4/3] bg-slate-950">
          <video ref={videoRef} muted playsInline className={`h-full w-full object-cover ${running ? "block" : "hidden"}`} />
          {!running && <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-white"><Camera size={42} className="text-slate-400" /><p className="font-bold">המצלמה כבויה</p><button onClick={startCamera} className="rounded-xl bg-indigo-600 px-5 py-3 font-black hover:bg-indigo-500">פתח מצלמה</button></div>}
          {running && <div className="pointer-events-none absolute inset-0 flex items-center justify-center"><div className="h-40 w-64 rounded-2xl border-2 border-white shadow-[0_0_0_9999px_rgba(0,0,0,.25)]" /></div>}
        </div>
        {running && <div className="flex justify-center p-3"><button onClick={stopCamera} className="inline-flex items-center gap-2 rounded-xl bg-slate-100 px-4 py-2 text-sm font-black dark:bg-slate-900"><X size={17} /> סגור מצלמה</button></div>}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex gap-2">
          <input value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => e.key === "Enter" && lookup()} placeholder="או הזן ברקוד / מק״ט ידנית" className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900" />
          <button disabled={loading} onClick={() => lookup()} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-black text-white disabled:opacity-50">{loading ? <RefreshCw className="animate-spin" size={18} /> : <PackageSearch size={18} />} חפש</button>
        </div>
        {!supported && <p className="mt-3 text-xs text-slate-500">סריקת מצלמה אינה זמינה בדפדפן הזה; החיפוש הידני עדיין זמין.</p>}
        {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm font-bold text-red-700 dark:bg-red-950/30 dark:text-red-300">{error}</p>}
      </section>

      {product && <section className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm dark:border-emerald-900 dark:bg-emerald-950/20"><div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 text-emerald-600" size={24} /><div className="min-w-0 flex-1"><h2 className="text-xl font-black">{product.name}</h2><p className="mt-1 text-sm text-slate-600 dark:text-slate-300">מק״ט: {product.sku || "—"} · ברקוד: {product.barcode || "—"}</p><div className="mt-4 grid grid-cols-3 gap-3"><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">מלאי</span><strong className="text-xl">{product.current_stock ?? 0}</strong></div><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">מינימום</span><strong className="text-xl">{product.min_stock ?? "—"}</strong></div><div className="rounded-xl bg-white p-3 dark:bg-slate-950"><span className="block text-xs text-slate-500">יעד</span><strong className="text-xl">{product.recommended_stock ?? "—"}</strong></div></div></div></div></section>}
    </main>
  );
}
