"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Calculator, RotateCcw, Search, Package, Scale } from "lucide-react";
import { useProducts, useSuppliers } from "@/hooks/use-catalog";
import type { Product } from "@/types";

const money = (value: number, currency = "ILS") => new Intl.NumberFormat("he-IL", { style: "currency", currency: currency === "ILS" ? "ILS" : currency, maximumFractionDigits: 4 }).format(value);
const numeric = (value: string) => value.trim() === "" ? null : Number(value);
const unitKey = (value: string | null | undefined) => (value ?? "").trim().toLocaleLowerCase("he").replace(/[״"'’]/g, "").replace(/\s+/g, "");
const conversion = (from: string, to: string): number | null => {
  const f = unitKey(from), t = unitKey(to);
  if (!f || !t) return f === t ? 1 : null;
  if (f === t) return 1;
  const mass: Record<string, number> = { "קג": 1000, "קילוגרם": 1000, "kg": 1000, "גרם": 1, "גר": 1, "g": 1, "מג": 0.001, "mg": 0.001 };
  const volume: Record<string, number> = { "ליטר": 1000, "ל": 1000, "liter": 1000, "litre": 1000, "l": 1000, "מל": 1, "מיליליטר": 1, "ml": 1 };
  if (mass[f] && mass[t]) return mass[f] / mass[t];
  if (volume[f] && volume[t]) return volume[f] / volume[t];
  return null;
};

export default function CostCalculatorPage() {
  const { data: products = [], isLoading, isError, refetch } = useProducts(undefined, true);
  const { data: suppliers = [] } = useSuppliers();
  const [search, setSearch] = useState("");
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [quantityUnit, setQuantityUnit] = useState("");
  const [manualPackagePrice, setManualPackagePrice] = useState("");
  const [packageQuantity, setPackageQuantity] = useState("");
  const [packageUnit, setPackageUnit] = useState("");
  const [amountToCost, setAmountToCost] = useState("");
  const [amountUnit, setAmountUnit] = useState("");
  const [useManualPackage, setUseManualPackage] = useState(false);

  const selected = products.find((product) => String(product.id) === productId) ?? null;
  const filteredProducts = useMemo(() => {
    const q = search.trim().toLocaleLowerCase("he");
    return products.filter((p) => !q || [p.name, p.sku, p.barcode, p.category].filter(Boolean).some((v) => String(v).toLocaleLowerCase("he").includes(q))).slice(0, 100);
  }, [products, search]);
  const supplierName = (product: Product) => suppliers.find((s) => s.id === product.supplier_id)?.name ?? "ספק לא ידוע";
  const basePrice = useManualPackage ? numeric(manualPackagePrice) : selected?.current_price == null ? null : Number(selected.current_price);
  const baseQty = useManualPackage ? numeric(packageQuantity) : 1;
  const baseUnit = useManualPackage ? packageUnit : selected?.unit ?? "";
  const conversionFactor = amountUnit && baseUnit ? conversion(amountUnit, baseUnit) : null;
  const validInputs = basePrice != null && Number.isFinite(basePrice) && basePrice >= 0 && baseQty != null && Number.isFinite(baseQty) && baseQty > 0 && numeric(amountToCost) != null && Number.isFinite(Number(amountToCost)) && Number(amountToCost) >= 0 && conversionFactor != null;
  const totalCost = validInputs ? (basePrice! / baseQty!) * Number(amountToCost) * conversionFactor! : null;
  const reset = () => { setSearch(""); setProductId(""); setQuantity(""); setQuantityUnit(""); setManualPackagePrice(""); setPackageQuantity(""); setPackageUnit(""); setAmountToCost(""); setAmountUnit(""); setUseManualPackage(false); };

  return <div dir="rtl" className="mx-auto max-w-5xl space-y-6 pb-10 text-slate-900 dark:text-slate-100">
    <header className="overflow-hidden rounded-3xl bg-gradient-to-l from-slate-950 via-indigo-950 to-blue-900 p-6 text-white shadow-xl sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-bold text-blue-100"><Calculator className="h-4 w-4"/> כלי עזר לרכש</div>
          <h1 className="text-2xl font-black tracking-tight sm:text-3xl">מחשבון עלויות מוצרים גולמיים</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-blue-100">בדקו מחיר ליחידת מידה ואת עלות הכמות הדרושה מתוך מוצר או אריזה. החישוב זמני בלבד ואינו משנה את מחיר המוצר או את נתוני המלאי.</p>
        </div>
        <button type="button" onClick={reset} className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-sm font-bold hover:bg-white/15"><RotateCcw className="h-4 w-4"/> איפוס</button>
      </div>
    </header>

    <div className="grid gap-4 md:grid-cols-2">
      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2"><Package className="h-5 w-5 text-indigo-600"/><h2 className="text-lg font-extrabold">בחירת מוצר ומחיר</h2></div>
        <label className="block text-sm font-bold">חיפוש בקטלוג המוצרים
          <span className="relative mt-1 block"><Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="שם מוצר, מק״ט או ברקוד" className={inputClass + " pr-9"}/></span>
        </label>
        <label className="block text-sm font-bold">מוצר מהקטלוג
          <select value={productId} onChange={e => { setProductId(e.target.value); setUseManualPackage(false); setAmountUnit(""); }} className={inputClass + " mt-1"}>
            <option value="">בחרו מוצר</option>
            {filteredProducts.map(p => <option key={p.id} value={p.id}>{p.name}{p.current_price != null && p.current_price > 0 ? ` — ${money(p.current_price, p.currency)}` : " — חסר מחיר"}</option>)}
          </select>
        </label>
        {isLoading && <p className="text-sm text-slate-500">טוען מוצרים מהקטלוג…</p>}
        {isError && <div role="alert" className="text-sm text-rose-600">לא ניתן לטעון את הקטלוג. <button onClick={() => refetch()} className="font-bold underline">נסו שוב</button></div>}
        {selected && <div className="rounded-xl bg-slate-50 p-3 text-sm dark:bg-slate-800/70"><div className="font-extrabold">{selected.name}</div><div className="mt-1 text-slate-500">ספק: {supplierName(selected)}</div><div className="mt-1">מחיר בקטלוג: <strong>{selected.current_price != null && selected.current_price > 0 ? money(selected.current_price, selected.currency) : "לא הוגדר מחיר תקין"}</strong>{selected.unit ? ` לכל ${selected.unit}` : ""}</div></div>}
        <div className="border-t border-slate-200 pt-4 dark:border-slate-700">
          <label className="flex items-center gap-2 text-sm font-bold"><input type="checkbox" checked={useManualPackage} onChange={e => setUseManualPackage(e.target.checked)} className="h-4 w-4 accent-indigo-600"/> לחשב לפי מחיר אריזה וכמות אריזה אחרת</label>
          {useManualPackage && <div className="mt-3 grid gap-3 sm:grid-cols-2"><Field label="מחיר אריזה (₪)" value={manualPackagePrice} onChange={setManualPackagePrice}/><Field label="כמות באריזה" value={packageQuantity} onChange={setPackageQuantity}/><Field label="יחידת מידה באריזה" value={packageUnit} onChange={setPackageUnit} placeholder="למשל ק״ג, ליטר, יחידה"/></div>}
        </div>
      </section>

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-2"><Scale className="h-5 w-5 text-indigo-600"/><h2 className="text-lg font-extrabold">חישוב עלות כמות</h2></div>
        <p className="text-sm leading-6 text-slate-500">הזינו כמות ויחידת מידה. המערכת תמיר בין גרם לק״ג ובין מ״ל לליטר. יחידות שאינן ניתנות להמרה יחושבו רק כאשר יחידת המידה זהה.</p>
        <Field label="כמות לחישוב" value={amountToCost} onChange={setAmountToCost} placeholder="למשל 250"/>
        <Field label="יחידת מידה של הכמות" value={amountUnit} onChange={setAmountUnit} placeholder="למשל גרם, ק״ג, ליטר, יחידה"/>
        {selected && !useManualPackage && <p className="text-xs text-slate-500">יחידת המידה שמוגדרת בקטלוג: {selected.unit || "לא הוגדרה"}. ודאו שהמחיר בקטלוג מתייחס ליחידה זו.</p>}
        <div className="rounded-2xl border border-indigo-200 bg-indigo-50 p-5 dark:border-indigo-900/60 dark:bg-indigo-950/30">
          <div className="text-sm font-bold text-indigo-800 dark:text-indigo-200">עלות הכמות המבוקשת</div>
          <div className="mt-2 text-3xl font-black tabular-nums text-indigo-950 dark:text-white">{totalCost == null ? "—" : money(totalCost, useManualPackage ? "ILS" : selected?.currency ?? "ILS")}</div>
          {totalCost != null && baseQty != null && baseQty > 0 && <p className="mt-2 text-xs leading-5 text-indigo-800 dark:text-indigo-200">מחיר יחידת המידה: {money(basePrice! / baseQty!, useManualPackage ? "ILS" : selected?.currency ?? "ILS")} לכל {baseUnit}</p>}
          {selected && !useManualPackage && !(selected.current_price != null && selected.current_price > 0) && <p className="mt-2 text-sm font-bold text-amber-700">למוצר הזה אין מחיר תקין בקטלוג. לא מוצג חישוב המבוסס על מחיר חסר.</p>}
          {amountUnit && baseUnit && conversionFactor == null && <p className="mt-2 text-sm font-bold text-amber-700">לא ניתן להמיר בין יחידות המידה האלה. בחרו יחידות זהות או יחידות משקל/נפח תואמות.</p>}
        </div>
      </section>
    </div>

    <div className="flex flex-wrap gap-3 text-sm"><Link href="/dashboard/catalog" className="rounded-xl border border-slate-200 px-4 py-2.5 font-bold hover:border-indigo-300 dark:border-slate-700">חזרה לקטלוג ולמחירים</Link><Link href="/dashboard/inventory" className="rounded-xl border border-slate-200 px-4 py-2.5 font-bold hover:border-indigo-300 dark:border-slate-700">מעבר למלאי</Link></div>
    <p className="text-xs leading-5 text-slate-500">הערה: החישוב משתמש במחיר המוצר הנוכחי שמוצג בקטלוג, ואינו מחליף בדיקת מחיר מול ספק. אין כאן שמירה של חישובים, שינוי מחיר, תמחור מתכון או חישוב רווח.</p>
  </div>;
}

const inputClass = "block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100";
function Field({ label, value, onChange, placeholder = "" }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return <label className="block text-sm font-bold">{label}<input type="number" min="0" step="any" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} className={inputClass + " mt-1"} /></label>;
}
