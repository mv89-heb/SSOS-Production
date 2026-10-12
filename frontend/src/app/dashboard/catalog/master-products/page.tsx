"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Package, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { catalogService } from "@/services/catalog-service";
import type { MasterProductRecord } from "@/services/catalog-service";

const money = (value: number, currency: string) => {
  try { return new Intl.NumberFormat("he-IL", { style: "currency", currency, maximumFractionDigits: 3 }).format(value); }
  catch { return `${value.toFixed(2)} ${currency}`; }
};
const unitLabel: Record<string, string> = { UNIT: "יחידה", KG: "ק״ג", G: "גרם", L: "ליטר", ML: "מ״ל", M: "מטר", PACK: "מארז", CARTON: "קרטון" };

export default function MasterProductsPage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selected, setSelected] = useState<MasterProductRecord | null>(null);
  const masters = useQuery({ queryKey: ["catalog", "master-products", submittedQuery], queryFn: () => catalogService.listMasterProducts(submittedQuery) });
  const comparison = useQuery({ queryKey: ["catalog", "master-product-comparison", selected?.id], queryFn: () => catalogService.compareMasterProduct(selected!.id), enabled: selected != null });

  return <main dir="rtl" className="mx-auto max-w-7xl space-y-6 p-4 md:p-6">
    <header><p className="text-sm font-semibold text-primary">קטלוג אחיד</p><h1 className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">מוצרי אב והשוואת מחירים</h1><p className="mt-2 max-w-3xl text-sm text-slate-600 dark:text-slate-300">כל שורה מייצגת מוצר גנרי אחיד. ההשוואה מציגה רק מחירים באותו מטבע ובאותה יחידת השוואה; מחירים לא שלמים נשארים בנפרד ולא מקבלים דירוג מטעה.</p></header>

    <div className="grid gap-4 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.7fr)]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <form onSubmit={(e) => { e.preventDefault(); setSubmittedQuery(query.trim()); }} className="flex gap-2"><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="חיפוש מוצר אב, מותג או ברקוד" /><Button type="submit" aria-label="חיפוש"><Search size={16} /></Button></form>
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500"><span>{masters.data?.length ?? 0} מוצרים</span><span>בחר מוצר להשוואה</span></div>
        <div className="mt-3 max-h-[65vh] space-y-2 overflow-y-auto">
          {masters.isLoading && <p className="p-4 text-sm text-slate-500">טוען קטלוג...</p>}
          {masters.isError && <p className="p-4 text-sm text-red-700">טעינת הקטלוג נכשלה. נסה שוב.</p>}
          {(masters.data || []).map((master) => <button key={master.id} type="button" onClick={() => setSelected(master)} className={`w-full rounded-xl border p-3 text-right transition ${selected?.id === master.id ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900"}`}><span className="flex items-start gap-2"><Package size={17} className="mt-0.5 shrink-0 text-slate-400" /><span className="min-w-0"><span className="block font-semibold text-slate-900 dark:text-white">{master.canonical_name}</span><span className="mt-1 block text-xs text-slate-500">{[master.brand, master.category, master.barcode].filter(Boolean).join(" · ") || "אין פרטי זיהוי נוספים"}</span></span></span></button>)}
          {!masters.isLoading && !masters.isError && masters.data?.length === 0 && <p className="p-6 text-center text-sm text-slate-500">לא נמצאו מוצרי אב. אפשר ליצור מוצר אב חדש דרך מסך התאמת מוצרי ספקים.</p>}
        </div>
      </section>

      <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950 md:p-5">
        {!selected && <div className="flex min-h-64 flex-col items-center justify-center text-center"><Package size={30} className="text-slate-300" /><h2 className="mt-3 font-bold">בחר מוצר אב</h2><p className="mt-1 max-w-sm text-sm text-slate-500">כאן יוצגו כל הספקים ששויכו לאותו מוצר, המחיר המקורי והמחיר המנורמל.</p></div>}
        {selected && <><div className="border-b border-slate-100 pb-4 dark:border-slate-800"><div className="text-xs font-semibold text-primary">מוצר אב #{selected.id}</div><h2 className="mt-1 text-xl font-bold">{selected.canonical_name}</h2><p className="mt-1 text-sm text-slate-500">{[selected.brand, selected.category, selected.base_unit, selected.barcode].filter(Boolean).join(" · ") || "אין פרטים נוספים"}</p></div>
          {comparison.isLoading && <p className="p-6 text-sm text-slate-500">מחשב השוואת ספקים...</p>}
          {comparison.isError && <p className="p-6 text-sm text-red-700">לא ניתן לטעון את השוואת המחירים.</p>}
          {comparison.data && <div className="mt-4 space-y-5">
            <div className="flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">{comparison.data.supplier_product_count} הצעות משויכות</span><span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800">{comparison.data.groups.reduce((n, group) => n + group.offers.length, 0)} מחירים בני השוואה</span><span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800">{comparison.data.incomplete_offers.length} דורשות השלמה</span></div>
            {comparison.data.groups.map((group) => <div key={group.currency + group.comparison_unit} className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800"><div className="flex items-center justify-between bg-slate-50 px-3 py-3 dark:bg-slate-900"><h3 className="font-bold">השוואה לפי {unitLabel[group.comparison_unit] || group.comparison_unit}</h3><span className="text-xs text-slate-500">{group.currency}</span></div><div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-3 px-3 py-2 text-[11px] font-semibold text-slate-500"><span>ספק / שם מוצר</span><span>מחיר מקורי</span><span>מחיר מנורמל</span></div><div className="divide-y divide-slate-100 dark:divide-slate-800">{group.offers.map((offer, index) => <div key={offer.supplier_product_id} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 px-3 py-3 text-sm"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2 font-semibold"><span>{offer.supplier_name || `ספק #${offer.supplier_id}`}</span>{index === 0 && <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] text-emerald-800">הזול ביותר</span>}</div><p className="mt-1 truncate text-xs text-slate-500">{offer.supplier_product_name}{offer.supplier_sku ? ` · מק״ט ${offer.supplier_sku}` : ""}</p></div><div className="whitespace-nowrap text-slate-600">{money(offer.price, offer.currency)}</div><div className="whitespace-nowrap font-bold">{money(offer.normalized_price, offer.currency)}</div></div>)}</div></div>)}
            {comparison.data.groups.length === 0 && <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">עדיין אין הצעות עם מחיר חיובי ויחידת השוואה מוגדרת למוצר זה.</div>}
            {comparison.data.incomplete_offers.length > 0 && <div className="overflow-hidden rounded-xl border border-amber-200"><div className="flex items-center gap-2 bg-amber-50 p-3 text-sm font-semibold text-amber-900"><AlertTriangle size={17} />הצעות שאינן ניתנות להשוואה עדיין</div><div className="divide-y divide-amber-100">{comparison.data.incomplete_offers.map((offer) => <div key={offer.id} className="flex flex-col gap-1 p-3 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="font-medium">{offer.supplier_company_name || `ספק #${offer.supplier_id}`} — {offer.supplier_name}</span><span className="text-xs text-amber-800">{offer.incomparable_reason || "יש להשלים מחיר, יחידת מכירה או כמות באריזה"}</span></div>)}</div></div>}
            {comparison.data.groups.length > 0 && <p className="flex items-start gap-2 text-xs text-slate-500"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />המחירים ממוינים בתוך כל קבוצה בעלת מטבע ויחידת השוואה זהים. לא מבוצעת המרת מטבע אוטומטית.</p>}
          </div>}
        </>}
      </section>
    </div>
  </main>;
}
