"use client";

import { useMemo } from "react";
import { Filter, RotateCcw, SlidersHorizontal } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCategories, useSuppliers } from "@/hooks/use-catalog";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";

const CATALOG_KEYS = ["gf_supplier", "gf_status", "gf_stock", "gf_price_min", "gf_price_max", "gf_unit", "gf_missing", "gf_category"];
const SUPPLIER_KEYS = ["gf_status", "gf_contact", "gf_phone", "gf_email", "gf_days"];

function FilterSelect({ value, onChange, children, className = "" }: { value: string; onChange: (value: string) => void; children: React.ReactNode; className?: string }) {
  return <Select value={value} onChange={(event) => onChange(event.target.value)} className={`h-10 min-w-[145px] ${className}`}>{children}</Select>;
}

function useFilterState(keys: string[]) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeCount = useMemo(() => keys.reduce((count, key) => count + (searchParams.get(key) ? 1 : 0), 0), [keys, searchParams]);
  const setFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value && value !== "all") params.set(key, value); else params.delete(key);
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
  };
  const clearFilters = () => {
    const params = new URLSearchParams(searchParams.toString());
    keys.forEach((key) => params.delete(key));
    router.replace(`${pathname}${params.toString() ? `?${params.toString()}` : ""}`, { scroll: false });
  };
  return { searchParams, activeCount, setFilter, clearFilters };
}

export function DashboardFilters() {
  const pathname = usePathname();
  if (pathname === "/dashboard/suppliers") return <SupplierFilters />;
  if (pathname === "/dashboard/catalog") return <CatalogFilters />;
  return null;
}

function SupplierFilters() {
  const { searchParams, activeCount, setFilter, clearFilters } = useFilterState(SUPPLIER_KEYS);
  return (
    <section className="mb-5 rounded-2xl border border-slate-200/80 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900" aria-label="סינון ספקים">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
        <div className="flex items-center gap-2 text-sm font-extrabold text-slate-800 dark:text-slate-100">
          <span className="rounded-lg bg-indigo-50 p-2 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300"><Filter size={16} /></span>
          סינון ספקים
          {activeCount > 0 && <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[11px] font-bold text-white">{activeCount}</span>}
        </div>
        <div className="flex flex-1 flex-wrap gap-2">
          <FilterSelect value={searchParams.get("gf_status") ?? "all"} onChange={(value) => setFilter("gf_status", value)}><option value="all">כל הסטטוסים</option><option value="active">פעילים בלבד</option><option value="inactive">לא פעילים</option></FilterSelect>
          <FilterSelect value={searchParams.get("gf_contact") ?? "all"} onChange={(value) => setFilter("gf_contact", value)}><option value="all">איש קשר — הכל</option><option value="yes">עם איש קשר</option><option value="no">ללא איש קשר</option></FilterSelect>
          <FilterSelect value={searchParams.get("gf_phone") ?? "all"} onChange={(value) => setFilter("gf_phone", value)}><option value="all">טלפון — הכל</option><option value="yes">עם טלפון</option><option value="no">ללא טלפון</option></FilterSelect>
          <FilterSelect value={searchParams.get("gf_email") ?? "all"} onChange={(value) => setFilter("gf_email", value)}><option value="all">אימייל — הכל</option><option value="yes">עם אימייל</option><option value="no">ללא אימייל</option></FilterSelect>
          <FilterSelect value={searchParams.get("gf_days") ?? "all"} onChange={(value) => setFilter("gf_days", value)}><option value="all">ימי הזמנה/אספקה — הכל</option><option value="complete">מוגדרים</option><option value="missing">חסרים</option></FilterSelect>
        </div>
        {activeCount > 0 && <Button variant="ghost" onClick={clearFilters} className="shrink-0"><RotateCcw size={15} />איפוס סינון</Button>}
      </div>
    </section>
  );
}

function CatalogFilters() {
  const { data: suppliers = [] } = useSuppliers();
  const { data: categories = [] } = useCategories();
  const { searchParams, activeCount, setFilter, clearFilters } = useFilterState(CATALOG_KEYS);
  const units = useMemo(() => ["ק" + "ג", "יח", "ליטר", "מגש", "קרטון", "אריזה"], []);
  return (
    <section className="mb-5 rounded-2xl border border-slate-200/80 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900" aria-label="סינון מתקדם לקטלוג">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-extrabold text-slate-800 dark:text-slate-100">
            <span className="rounded-lg bg-indigo-50 p-2 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300"><SlidersHorizontal size={16} /></span>
            סינון מתקדם בקטלוג
            {activeCount > 0 && <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[11px] font-bold text-white">{activeCount} פעילים</span>}
          </div>
          {activeCount > 0 && <Button variant="ghost" onClick={clearFilters}><RotateCcw size={15} />איפוס סינון</Button>}
        </div>
        <div className="flex flex-wrap gap-2">
          <FilterSelect value={searchParams.get("gf_supplier") ?? "all"} onChange={(value) => setFilter("gf_supplier", value)} className="min-w-[190px]"><option value="all">כל הספקים</option>{suppliers.map((supplier) => <option key={supplier.id} value={String(supplier.id)}>{supplier.name}</option>)}</FilterSelect>
          <FilterSelect value={searchParams.get("gf_status") ?? "all"} onChange={(value) => setFilter("gf_status", value)}><option value="all">כל הסטטוסים</option><option value="active">פעילים בלבד</option><option value="inactive">לא פעילים</option></FilterSelect>
          <FilterSelect value={searchParams.get("gf_stock") ?? "all"} onChange={(value) => setFilter("gf_stock", value)}><option value="all">כל מצבי המלאי</option><option value="low">מלאי נמוך</option><option value="healthy">מלאי תקין</option><option value="missing">ללא נתוני מלאי</option></FilterSelect>
          <FilterSelect value={searchParams.get("gf_missing") ?? "all"} onChange={(value) => setFilter("gf_missing", value)}><option value="all">שלמות נתונים — הכל</option><option value="price">מחיר חסר</option><option value="category">קטגוריה חסרה</option><option value="unit">יחידת מידה חסרה</option><option value="sku">מק״ט חסר</option><option value="barcode">ברקוד חסר</option></FilterSelect>
          <FilterSelect value={searchParams.get("gf_unit") ?? "all"} onChange={(value) => setFilter("gf_unit", value)}><option value="all">כל יחידות המידה</option>{units.map((unit) => <option key={unit} value={unit}>{unit}</option>)}</FilterSelect>
          <FilterSelect value={searchParams.get("gf_category") ?? "all"} onChange={(value) => setFilter("gf_category", value)} className="min-w-[170px]"><option value="all">כל הקטגוריות</option>{categories.map((category) => <option key={category} value={category}>{category}</option>)}</FilterSelect>
          <input aria-label="מחיר מינימום" inputMode="decimal" type="number" min="0" step="0.01" placeholder="מחיר מינ׳" value={searchParams.get("gf_price_min") ?? ""} onChange={(event) => setFilter("gf_price_min", event.target.value)} className="h-10 w-32 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-950" />
          <input aria-label="מחיר מקסימום" inputMode="decimal" type="number" min="0" step="0.01" placeholder="מחיר מקס׳" value={searchParams.get("gf_price_max") ?? ""} onChange={(event) => setFilter("gf_price_max", event.target.value)} className="h-10 w-32 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-950" />
        </div>
      </div>
    </section>
  );
}
