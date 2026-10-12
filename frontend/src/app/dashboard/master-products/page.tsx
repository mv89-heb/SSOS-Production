"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/services/api-client";
import { AlertTriangle, CheckCircle2, ChevronLeft, PackageSearch, RefreshCw, Search, Scale, Tags } from "lucide-react";

type MasterProduct = {
  id: number; masterProductId: number; canonical_name: string; name: string; normalized_name: string;
  category?: string | null; base_unit?: string | null; barcode?: string | null; current_price: number | null;
  currency: string; supplier_count: number; listing_count: number; best_supplier_name: string | null; has_price: boolean;
};
type Offer = {
  supplier_id: number; supplier_name: string | null; price: number; currency: string; unit: string | null;
  comparison_unit: string | null; normalized_price: number; supplier_product_id: number;
  supplier_product_name: string; supplier_sku?: string | null; source_type?: string; observed_at?: string | null; source_document_id?: number | null; match_confidence?: number | null;
};
type Comparison = {
  master_product: MasterProduct; groups: Array<{ currency: string; comparison_unit: string; offers: Offer[]; best_offer: Offer | null }>;
  incomplete_offers: Array<{ id: number; supplier_name: string; supplier_company_name?: string | null; price: number | null;
    currency: string; unit: string | null; incomparable_reason: string; supplier_product_name?: string }>;
  supplier_product_count: number;
};
type ReviewCandidate = { supplier_product: Pending; supplier_company_name: string; current_master_product?: { id: number; canonical_name: string } | null; suggested_master_product: { id: number; canonical_name: string }; confidence: number; match_method: string; };
type Pending = {
  id: number; supplier_id: number; supplier_name: string; supplier_company_name?: string | null; price: number | null;
  currency: string; unit: string | null; match_confidence?: number | null; match_method?: string | null;
  suggested_master_product_id?: number | null; suggested_master_product?: { id: number; canonical_name: string } | null;
};

const money = (value: number | null | undefined, currency = "ILS") => {
  if (value == null || !Number.isFinite(value)) return "אין מחיר";
  try { return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 2 }).format(value); }
  catch { return value.toFixed(2) + " " + currency; }
};

export default function MasterProductsPage() {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const productsQuery = useQuery({
    queryKey: ["master-products", search],
    queryFn: async () => (await apiClient.get<{ master_products: MasterProduct[] }>("/api/catalog/master-products", { params: { q: search || undefined, limit: 1000 } })).data.master_products,
  });
  const comparisonQuery = useQuery({
    queryKey: ["master-product-comparison", selectedId],
    enabled: selectedId !== null,
    queryFn: async () => (await apiClient.get<Comparison>(`/api/catalog/master-products/${selectedId}/comparison`)).data,
  });
  const pendingQuery = useQuery({
    queryKey: ["master-products-pending"],
    queryFn: async () => (await apiClient.get<{ supplier_products: Pending[] }>("/api/catalog/supplier-products/pending")).data.supplier_products,
  });
  const reviewCandidatesQuery = useQuery({
    queryKey: ["master-product-review-candidates"],
    queryFn: async () => (await apiClient.get<{ candidates: ReviewCandidate[] }>("/api/catalog/master-products/review-candidates", { params: { limit: 250 } })).data.candidates,
  });
  const products = productsQuery.data ?? [];
  const comparison = comparisonQuery.data;
  const sortedProducts = useMemo(() => [...products].sort((a, b) => a.canonical_name.localeCompare(b.canonical_name, "he")), [products]);

  const approve = async (item: Pending) => {
    if (!item.suggested_master_product_id) return;
    await apiClient.post(`/api/catalog/supplier-products/${item.id}/approve`, { master_product_id: item.suggested_master_product_id });
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["master-products-pending"] }),
      queryClient.invalidateQueries({ queryKey: ["master-products"] }),
    ]);
  };
  const approveCandidate = async (candidate: ReviewCandidate) => {
    await apiClient.post(`/api/catalog/supplier-products/${candidate.supplier_product.id}/approve`, {
      master_product_id: candidate.suggested_master_product.id,
    });
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["master-product-review-candidates"] }),
      queryClient.invalidateQueries({ queryKey: ["master-products"] }),
      queryClient.invalidateQueries({ queryKey: ["master-product-comparison"] }),
    ]);
  };

  return <main dir="rtl" className="space-y-6 pb-12">
    <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-violet-600"><Scale size={18}/><span className="text-sm font-semibold">Master Catalog</span></div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">קטלוג אב והשוואת ספקים</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">כל מוצר אב מופיע פעם אחת. הצעות המחיר של מוצרי הספק המקושרים אליו מוצגות יחד, בלי לאחד אוטומטית פריטים שזוהו כלא תואמים.</p>
        </div>
        <Link href="/dashboard/price-intelligence" className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold hover:border-violet-300"><ChevronLeft size={16}/> ניתוח מחירים קיים</Link>
      </div>
      <div className="relative mt-5 max-w-lg"><Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={17}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="חפש מוצר אב, קטגוריה או שם..." className="w-full rounded-xl border border-slate-200 bg-white py-3 pr-10 pl-3 text-sm outline-none focus:border-violet-500 dark:border-slate-700 dark:bg-slate-900 dark:text-white"/></div>
      <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500"><span>{products.length} מוצרי אב</span><span>·</span><span>{products.filter(p => p.supplier_count > 1).length} עם יותר מספק אחד</span><span>·</span><span>{products.filter(p => !p.has_price).length} ללא מחיר אחיד להצגה</span></div>
    </header>

    <div className="grid gap-6 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.6fr)]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="mb-3 flex items-center justify-between"><h2 className="font-bold">מוצרי האב</h2><button type="button" onClick={() => productsQuery.refetch()} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="רענן"><RefreshCw size={15}/></button></div>
        {productsQuery.isLoading && <p className="p-4 text-sm text-slate-500">טוען קטלוג...</p>}
        {productsQuery.isError && <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700">לא ניתן לטעון את קטלוג האב. בדוק הרשאות ופריסת שרת.</div>}
        {!productsQuery.isLoading && !productsQuery.isError && sortedProducts.length === 0 && <p className="p-4 text-sm text-slate-500">לא נמצאו מוצרי אב.</p>}
        <div className="max-h-[760px] space-y-2 overflow-y-auto">
          {sortedProducts.map(product => <button key={product.id} type="button" onClick={() => setSelectedId(product.id)} className={`w-full rounded-xl border p-3 text-right transition ${selectedId === product.id ? "border-violet-300 bg-violet-50 ring-1 ring-violet-200 dark:bg-violet-950/30" : "border-transparent hover:border-slate-200 hover:bg-slate-50 dark:hover:bg-slate-900"}`}>
            <div className="font-semibold text-slate-900 dark:text-white">{product.canonical_name}</div>
            <div className="mt-2 flex items-center justify-between gap-2 text-xs text-slate-500"><span>{product.supplier_count} ספקים · {product.listing_count} פריטי ספק</span><span className="font-bold">{money(product.current_price, product.currency)}</span></div>
            {product.best_supplier_name && <div className="mt-1 text-xs text-emerald-700 dark:text-emerald-400">המחיר הנמוך: {product.best_supplier_name}</div>}
          </button>)}
        </div>
      </section>

      <section className="space-y-5">
        {!selectedId && <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 p-8 text-center text-slate-500"><PackageSearch size={32} className="mb-3"/><p className="font-semibold">בחר מוצר אב</p><p className="mt-1 text-sm">כל הצעות הספקים המקושרות יוצגו כאן בטבלת השוואה.</p></div>}
        {selectedId && comparisonQuery.isLoading && <div className="rounded-2xl border p-8 text-center text-sm text-slate-500">טוען השוואת ספקים...</div>}
        {comparisonQuery.isError && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">טעינת ההשוואה נכשלה. <button className="font-bold underline" onClick={() => comparisonQuery.refetch()}>נסה שוב</button></div>}
        {comparison && <div className="space-y-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-2xl font-bold">{comparison.master_product.canonical_name}</h2><p className="mt-1 text-sm text-slate-500">{comparison.master_product.category || "ללא קטגוריה"} · {comparison.master_product.base_unit || "יחידה לא הוגדרה"}</p></div><span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">{comparison.supplier_product_count} הצעות מקושרות</span></div>
          </div>
          {comparison.groups.length === 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><AlertTriangle className="ml-2 inline" size={16}/>אין כרגע הצעות עם מחיר ויחידת השוואה תקינים.</div>}
          {comparison.groups.map(group => <div key={group.currency + group.comparison_unit} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4"><h3 className="font-bold">השוואה לפי {group.comparison_unit} · {group.currency}</h3>{group.best_offer && <span className="text-sm font-semibold text-emerald-700">הזול ביותר: {group.best_offer.supplier_name} — {money(group.best_offer.normalized_price, group.currency)}</span>}</div>
            <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-4 py-3">ספק</th><th className="px-4 py-3">שם אצל הספק</th><th className="px-4 py-3">מחיר מקורי</th><th className="px-4 py-3">מחיר מנורמל</th><th className="px-4 py-3">פער מהזול</th><th className="px-4 py-3">דירוג</th><th className="px-4 py-3">מקור / תאריך</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{group.offers.map((offer, i) => <tr key={`${offer.supplier_id}-${offer.supplier_product_id ?? "observation"}`}><td className="px-4 py-3 font-semibold">{offer.supplier_name || "ספק"}</td><td className="px-4 py-3">{offer.supplier_product_name}</td><td className="px-4 py-3">{money(offer.price, offer.currency)}<div className="text-xs text-slate-400">{offer.unit || "יחידה"}</div></td><td className="px-4 py-3 font-semibold">{money(offer.normalized_price, offer.currency)}</td><td className="px-4 py-3">{money(offer.normalized_price - (group.best_offer?.normalized_price ?? offer.normalized_price), offer.currency)}</td><td className="px-4 py-3">{i === 0 ? <span className="inline-flex items-center gap-1 text-emerald-700"><CheckCircle2 size={15}/>הזול ביותר</span> : <span className="text-slate-500">חלופה</span>}</td><td className="px-4 py-3 text-xs text-slate-500">{offer.observed_at ? <><strong>{offer.source_type || "מסמך ספק"}</strong><div>{new Intl.DateTimeFormat("he-IL", { dateStyle: "medium" }).format(new Date(offer.observed_at))}</div>{offer.match_confidence != null && <div>ביטחון {Math.round(offer.match_confidence * 100)}%</div>}</> : "מחיר קטלוג"}</td></tr>)}</tbody></table></div>
          </div>)}
          {comparison.incomplete_offers.length > 0 && <div className="overflow-hidden rounded-2xl border border-amber-200 bg-white dark:bg-slate-950"><div className="border-b border-amber-100 bg-amber-50 p-4 font-semibold text-amber-900">הצעות שדורשות השלמת נתונים ({comparison.incomplete_offers.length})</div><div className="divide-y">{comparison.incomplete_offers.map((item, i) => <div key={item.id ?? i} className="flex flex-wrap justify-between gap-2 p-4 text-sm"><div className="font-medium">{item.supplier_company_name || item.supplier_name} · {item.supplier_product_name || ""}</div><div className="text-amber-800">{item.incomparable_reason}</div></div>)}</div></div>}
        </div>}
      </section>
    </div>

    <section className="rounded-2xl border border-violet-200 bg-white p-5 shadow-sm dark:border-violet-900 dark:bg-slate-950">
      <div className="mb-3 flex items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-bold"><Scale size={18}/>מוצרים דומים שייתכן שצריך לאחד</h2><p className="mt-1 text-sm text-slate-500">הצעות התאמה שמבוססות על שם המוצר. יש לאשר רק אם מדובר באותו מוצר ובאותה אריזה.</p></div><span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-bold text-violet-800">{reviewCandidatesQuery.data?.length ?? 0} הצעות לבדיקה</span></div>
      {reviewCandidatesQuery.isError && <p className="text-sm text-red-700">לא ניתן לטעון הצעות התאמה.</p>}
      {reviewCandidatesQuery.data?.length === 0 && <p className="text-sm text-slate-500">לא נמצאו כרגע התאמות דומות בביטחון גבוה.</p>}
      <div className="grid gap-3 lg:grid-cols-2">{reviewCandidatesQuery.data?.map(candidate => <div key={candidate.supplier_product.id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
        <div className="font-semibold">{candidate.supplier_company_name} · {candidate.supplier_product.supplier_name}</div>
        <div className="mt-1 text-sm text-slate-500">{money(candidate.supplier_product.price, candidate.supplier_product.currency)} · {candidate.supplier_product.unit || "יחידה לא הוגדרה"}</div>
        <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2"><div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">שיוך נוכחי</div><strong>{candidate.current_master_product?.canonical_name || "ללא מוצר אב"}</strong></div><div className="rounded-lg bg-violet-50 p-3 dark:bg-violet-950/30"><div className="text-xs text-violet-700 dark:text-violet-300">מועמד לאיחוד</div><strong>{candidate.suggested_master_product.canonical_name}</strong></div></div>
        <div className="mt-2 text-xs text-slate-500">התאמה {Math.round(candidate.confidence * 100)}% · {candidate.match_method}</div>
        <button onClick={() => approveCandidate(candidate).catch(() => alert("לא ניתן לעדכן את השיוך. בדוק הרשאות ונסה שוב."))} className="mt-3 inline-flex items-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-700"><CheckCircle2 size={14}/>אשר שזה אותו מוצר</button>
      </div>)}</div>
    </section>

    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="mb-3 flex items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-bold"><Tags size={18}/>שיוכים שממתינים לאישור</h2><p className="mt-1 text-sm text-slate-500">המערכת לא מחברת אוטומטית התאמות לא ודאיות.</p></div><span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800">{pendingQuery.data?.length ?? 0} ממתינים</span></div>
      {pendingQuery.isError && <p className="text-sm text-red-700">לא ניתן לטעון שיוכים ממתינים.</p>}
      {pendingQuery.data?.length === 0 && <p className="text-sm text-slate-500">אין כרגע שיוכים שממתינים לאישור.</p>}
      <div className="grid gap-3 lg:grid-cols-2">{pendingQuery.data?.map(item => <div key={item.id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><div className="font-semibold">{item.supplier_company_name || `ספק #${item.supplier_id}`} · {item.supplier_name}</div><div className="mt-1 text-sm text-slate-500">{money(item.price, item.currency)} · {item.unit || "יחידה לא הוגדרה"}</div><div className="mt-2 text-sm">הצעת התאמה: <strong>{item.suggested_master_product?.canonical_name || "לא נמצאה התאמה בטוחה"}</strong></div><div className="mt-1 text-xs text-slate-500">שיטת התאמה: {item.match_method || "—"} · ביטחון: {item.match_confidence == null ? "—" : `${Math.round(item.match_confidence * 100)}%`}</div>{item.suggested_master_product_id && <button onClick={() => approve(item).catch(() => alert("לא ניתן לאשר את השיוך. בדוק הרשאות ונסה שוב."))} className="mt-3 inline-flex items-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-700"><CheckCircle2 size={14}/>אשר שיוך מוצע</button>}</div>)}</div>
    </section>
  </main>;
}
