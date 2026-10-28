"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Barcode, CheckCircle2, Loader2, Printer, QrCode, Search, Tag } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import type { Product } from "@/types";

type ProductCode = {
  id: number;
  product_id: number;
  code_type: "CODE128" | "QR";
  code_value: string;
  created_at: string;
};

export default function ProductCodesPage() {
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);
  const [products, setProducts] = useState<Product[]>([]);
  const [codes, setCodes] = useState<Record<number, ProductCode[]>>({});
  const [filter, setFilter] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!user) return;
    Promise.all([
      apiClient.get<{ success: boolean; products: Product[] }>("/api/catalog/products"),
      apiClient.get<{ success: boolean; codes: ProductCode[] }>("/api/product-codes"),
    ])
      .then(([productResponse, codeResponse]) => {
        setProducts(productResponse.data.products ?? []);
        const grouped = (codeResponse.data.codes ?? []).reduce<Record<number, ProductCode[]>>((acc, code) => {
          (acc[code.product_id] ??= []).push(code);
          return acc;
        }, {});
        setCodes(grouped);
      })
      .catch(() => setError("לא ניתן לטעון את קטלוג המוצרים והקודים השמורים."));
  }, [user]);

  const filtered = useMemo(() => {
    const term = filter.trim().toLocaleLowerCase("he");
    return products.filter((p) => !term || p.name.toLocaleLowerCase("he").includes(term) ||
      (p.sku ?? "").toLocaleLowerCase("he").includes(term) ||
      (p.barcode ?? "").includes(term));
  }, [products, filter]);

  async function loadCodes(productId: number) {
    const { data } = await apiClient.get<{ success: boolean; codes: ProductCode[] }>(`/api/product-codes/products/${productId}`);
    setCodes((current) => ({ ...current, [productId]: data.codes ?? [] }));
  }

  async function generate(productId: number) {
    setBusyId(productId); setError(""); setMessage("");
    try {
      await apiClient.post(`/api/product-codes/products/${productId}/generate`, { types: ["CODE128", "QR"] });
      await loadCodes(productId);
      setMessage("הקודים נוצרו או נטענו מחדש. ניתן להדפיס את התווית.");
    } catch (e: unknown) {
      const ex = e as { response?: { data?: { message?: string } }; message?: string };
      setError(ex.response?.data?.message ?? ex.message ?? "יצירת הקודים נכשלה.");
    } finally { setBusyId(null); }
  }

  if (!canManage) return <div dir="rtl" className="rounded-xl border bg-white p-8 text-center text-sm text-slate-500">נדרשת הרשאת ניהול קטלוג כדי ליצור תוויות.</div>;

  const apiBase = (process.env.NEXT_PUBLIC_API_URL || "https://ssos-backend.onrender.com").replace(/\/$/, "");

  return <main dir="rtl" className="mx-auto w-full max-w-7xl space-y-6 pb-12">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <Link href="/dashboard/settings" className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-indigo-700 hover:text-indigo-900"><ArrowRight size={16} /> חזרה להגדרות</Link>
        <h1 className="text-3xl font-extrabold tracking-tight">ברקודים ותוויות</h1>
        <p className="mt-1 text-sm leading-6 text-slate-500">יצירה דינמית של ברקוד פנימי ו־QR לכל מוצר, בלי לשנות ברקודי ספק קיימים.</p>
      </div>
      <button type="button" onClick={() => window.print()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold shadow-sm hover:bg-slate-50 print:hidden"><Printer size={17} /> הדפסה</button>
    </header>

    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm print:hidden">
      <label htmlFor="product-filter" className="mb-2 block text-sm font-bold">חיפוש מוצר</label>
      <div className="relative max-w-xl"><Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input id="product-filter" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="שם מוצר, מק״ט או ברקוד ספק" className="w-full rounded-xl border border-slate-200 py-3 pr-10 pl-3 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100" /></div>
      <p className="mt-2 text-xs text-slate-500">מוצגים {filtered.length} מתוך {products.length} מוצרים. יצירה חוזרת לא מחליפה קוד שכבר נוצר.</p>
    </section>

    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
    {message && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 print:hidden">{message}</div>}

    <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {filtered.map((product) => {
        const productCodes = codes[product.id] ?? [];
        const barcode = productCodes.find((code) => code.code_type === "CODE128");
        const qr = productCodes.find((code) => code.code_type === "QR");
        return <article key={product.id} className="break-inside-avoid rounded-2xl border border-slate-200 bg-white p-4 shadow-sm print:rounded-none print:border-slate-300 print:shadow-none">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0"><h2 className="font-bold leading-6">{product.name}</h2><p className="mt-1 text-xs text-slate-500">מק״ט: {product.sku || "לא הוגדר"} · ברקוד ספק: {product.barcode || "לא הוגדר"}</p></div>
            <Tag size={18} className="shrink-0 text-slate-400" />
          </div>
          {productCodes.length > 0 ? <div className="mt-4 grid grid-cols-2 gap-3">
            {barcode && <div className="min-w-0 rounded-xl border border-slate-100 p-2 text-center"><div className="mb-1 flex items-center justify-center gap-1 text-xs font-bold text-slate-600"><Barcode size={14} /> Code 128</div><img alt={`ברקוד פנימי עבור ${product.name}`} src={`${apiBase}/api/product-codes/${barcode.id}/image`} className="mx-auto max-h-20 max-w-full object-contain" /><p className="mt-1 break-all text-[10px] text-slate-600">{barcode.code_value}</p></div>}
            {qr && <div className="min-w-0 rounded-xl border border-slate-100 p-2 text-center"><div className="mb-1 flex items-center justify-center gap-1 text-xs font-bold text-slate-600"><QrCode size={14} /> QR</div><img alt={`קוד QR עבור ${product.name}`} src={`${apiBase}/api/product-codes/${qr.id}/image`} className="mx-auto h-24 w-24 object-contain" /><p className="mt-1 text-[10px] text-slate-600">פתיחת הקטלוג דורשת התחברות</p></div>}
          </div> : <div className="mt-4 rounded-xl border border-dashed border-slate-200 p-5 text-center text-xs text-slate-500 print:hidden">עדיין לא נוצרו קודים למוצר זה.</div>}
          <button type="button" onClick={() => generate(product.id)} disabled={busyId === product.id} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3 py-2.5 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-60 print:hidden">
            {busyId === product.id ? <Loader2 size={16} className="animate-spin" /> : productCodes.length ? <CheckCircle2 size={16} /> : <Tag size={16} />}
            {busyId === product.id ? "יוצר..." : productCodes.length ? "רענון תצוגת קודים" : "צור ברקוד ו־QR"}
          </button>
        </article>;
      })}
    </section>
    {!filtered.length && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">לא נמצאו מוצרים התואמים לחיפוש.</div>}
    <style jsx global>{`@media print { body { background: white !important; } main { max-width: none !important; padding: 0 !important; } article { break-inside: avoid; } }`}</style>
  </main>;
}
