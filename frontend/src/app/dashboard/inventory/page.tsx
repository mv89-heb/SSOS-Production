// @ts-nocheck
"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowDownToLine, ArrowUpFromLine, Barcode, CheckCircle2,
  ClipboardCheck, History, Package, RefreshCw, ScanLine, Search,
  SlidersHorizontal, Truck, Warehouse, X,
} from "lucide-react";
import { inventoryService, type InventoryMovement, type InventoryMovementType } from "@/services/inventory-service";
import InventoryBarcodeManager from "@/components/inventory/inventory-barcode-manager";
import InventoryPlanningPanel from "@/components/inventory/inventory-planning-panel";
import InventoryScannerModal from "@/components/inventory/inventory-scanner-modal";
import { ProductSortToggle } from "@/components/catalog/product-sort-toggle";
import { sortByHebrewName, type ProductSortDirection } from "@/lib/product-sorting";
import type { Product } from "@/types";

const number = (value: number | null | undefined) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 }).format(Number(value ?? 0));
const cartonNumber = (value: number | null | undefined) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(Number(value ?? 0));
const dateTime = (value: string) => new Intl.DateTimeFormat("he-IL", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
const movementLabels: Record<InventoryMovementType, string> = { count: "ספירה", receipt: "קבלה", issue: "ניפוק", adjustment: "התאמה" };
const unitLabel = (product: Product | null | undefined) => product?.stock_unit === "יחידה" ? "יחידות" : "ארגזים";
const unitSingular = (product: Product | null | undefined) => product?.stock_unit === "יחידה" ? "יחידה" : "ארגז";
const statusMeta = {
  urgent: { label: "חסר במלאי", className: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" },
  reorder: { label: "להזמין", className: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300" },
  healthy: { label: "תקין", className: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300" },
  insufficient_data: { label: "דורש השלמת נתונים", className: "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300" },
} as const;

function stockStatus(product: Product, forecast?: any) {
  // Recommendation readiness is authoritative: a zero balance without enough
  // physical counts and a configured target is unknown, not an urgent shortage.
  if (forecast?.status === "insufficient_data" || forecast?.data_ready === false || forecast?.configured_stock_target == null) return "insufficient_data" as const;
  if (forecast?.status === "urgent") return "urgent" as const;
  if (forecast?.status === "reorder") return "reorder" as const;
  if (forecast?.status === "healthy") return "healthy" as const;
  if (product.current_stock == null) return "insufficient_data" as const;
  const stock = Number(product.current_stock);
  if (stock <= 0) return "urgent" as const;
  if (product.min_stock != null && stock <= Number(product.min_stock)) return "reorder" as const;
  return "healthy" as const;
}

export default function InventoryPage() {
  const qc = useQueryClient();
  const [sortDirection, setSortDirection] = useState<ProductSortDirection>("asc");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "urgent" | "reorder" | "healthy" | "insufficient_data">("all");
  const [inventoryTab, setInventoryTab] = useState<"urgent" | "needs_data" | "all">("urgent");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [recommendationTab, setRecommendationTab] = useState<"urgent" | "reorder" | "needs_data">("urgent");
  const [supplierFilter, setSupplierFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [movementType, setMovementType] = useState<InventoryMovementType>("count");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [showMovement, setShowMovement] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showAllRecentMovements, setShowAllRecentMovements] = useState(false);
  const [showScanner, setShowScanner] = useState(false);
  const [showBarcodeManager, setShowBarcodeManager] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const summary = useQuery({ queryKey: ["inventory", "summary"], queryFn: inventoryService.getSummary, staleTime: 20_000 });
  const recommendations = useQuery({ queryKey: ["inventory", "recommendations"], queryFn: () => inventoryService.getRecommendations({ limit: 2000 }), staleTime: 30_000 });
  const history = useQuery({ queryKey: ["inventory", "history", selectedId], queryFn: () => inventoryService.getProductMovements(selectedId!, 100), enabled: selectedId != null && showHistory });
  const products = summary.data?.products ?? [];
  const recommendationByProduct = useMemo(() => new Map((recommendations.data ?? []).map((row) => [row.product_id, row])), [recommendations.data]);

  const rows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("he");
    const filtered = products.filter((product) => {
      const matches = !query || [product.name, product.sku, product.barcode, product.category, product.supplier_sku, recommendationByProduct.get(product.id)?.supplier_schedule?.supplier_name].filter(Boolean).some((v) => String(v).toLocaleLowerCase("he").includes(query));
      const status = stockStatus(product, recommendationByProduct.get(product.id));
      const matchesStatus = statusFilter === "all" || status === statusFilter;
      const matchesTab = inventoryTab === "all" || (inventoryTab === "urgent" ? status === "urgent" || status === "reorder" : status === "insufficient_data");
      const matchesSupplier = supplierFilter === "all" || String(product.supplier_id ?? "") === supplierFilter;
      const matchesCategory = categoryFilter === "all" || (product.category || "ללא קטגוריה") === categoryFilter;
      return matches && matchesStatus && matchesTab && matchesSupplier && matchesCategory;
    });
    return sortByHebrewName(filtered, (product) => product.name, sortDirection);
  }, [products, recommendationByProduct, search, statusFilter, sortDirection, inventoryTab, supplierFilter, categoryFilter]);

  const categories = useMemo(() => [...new Set(products.map((product) => product.category || "ללא קטגוריה"))].sort((a,b)=>a.localeCompare(b,"he")), [products]);
  const suppliers = useMemo(() => {
    const found = new Map<string, string>();
    for (const product of products) {
      const forecast = recommendationByProduct.get(product.id);
      if (product.supplier_id != null) found.set(String(product.supplier_id), forecast?.supplier_schedule?.supplier_name || ("ספק " + product.supplier_id));
    }
    return [...found.entries()].sort((a,b)=>a[1].localeCompare(b[1],"he"));
  }, [products, recommendationByProduct]);
  const urgentCount = useMemo(() => products.filter((product) => { const status = stockStatus(product, recommendationByProduct.get(product.id)); return status === "urgent" || status === "reorder"; }).length, [products, recommendationByProduct]);
  const needsDataCount = useMemo(() => products.filter((product) => stockStatus(product, recommendationByProduct.get(product.id)) === "insufficient_data").length, [products, recommendationByProduct]);
  const healthyCount = useMemo(() => products.filter((product) => stockStatus(product, recommendationByProduct.get(product.id)) === "healthy").length, [products, recommendationByProduct]);
  const selected = products.find((product) => product.id === selectedId) ?? null;
  const selectedForecast = selected ? recommendationByProduct.get(selected.id) : undefined;

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
      if (event.key === "Escape") {
        if (showMovement) closeMovement();
        else if (showHistory) setShowHistory(false);
      }
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [showMovement, showHistory]);
  const weeklyConsumption = useMemo(() => (recommendations.data ?? []).map((row) => ({ ...row, weeklyUsage: row.carton_recommendation_ready && row.average_daily_usage_cartons != null ? Number(row.average_daily_usage_cartons) * 7 : Number(row.average_daily_usage ?? 0) * 7, usageUnit: row.carton_recommendation_ready && row.average_daily_usage_cartons != null ? "קרטונים" : "יחידות" })).filter((row) => Number.isFinite(row.weeklyUsage) && row.weeklyUsage > 0).sort((a, b) => b.weeklyUsage - a.weeklyUsage).slice(0, 8), [recommendations.data]);

  const openMovement = useCallback((product: Product, type: InventoryMovementType) => {
    setSelectedId(product.id);
    setMovementType(type);
    setQuantity(type === "count" || type === "adjustment" ? String(product.current_stock ?? 0) : "");
    setNote("");
    setMessage(null);
    setShowHistory(false);
    setShowMovement(true);
  }, []);
  const openHistory = useCallback((product: Product) => {
    setSelectedId(product.id);
    setShowHistory(true);
  }, []);

  const closeMovement = () => {
    if (busy) return;
    setShowMovement(false);
    setMessage(null);
    setQuantity("");
    setNote("");
  };

  const submitMovement = async () => {
    if (!selected || busy) return;
    const qty = Number(quantity);
    if (!Number.isInteger(qty) || qty < 0 || (movementType !== "count" && movementType !== "adjustment" && qty <= 0)) {
      setMessage({ text: movementType === "count" ? `יש להזין מספר שלם של ${unitLabel(selected)} שאינו שלילי.` : `יש להזין מספר שלם של ${unitLabel(selected)} הגדול מאפס.`, error: true });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const result = await inventoryService.createMovement({ product_id: selected.id, movement_type: movementType, quantity: qty, note: note.trim() || undefined });
      const balanceAfter = Number(result.movement.balance_after ?? 0);
      qc.setQueryData(["inventory", "summary"], (current: any) => {
        if (!current?.products) return current;
        return {
          ...current,
          products: current.products.map((product: Product) => product.id === selected.id ? { ...product, current_stock: balanceAfter } : product),
          recent_movements: [result.movement, ...(current.recent_movements ?? []).filter((movement: InventoryMovement) => movement.id !== result.movement.id)].slice(0, 50),
          stats: current.stats ? { ...current.stats } : current.stats,
        };
      });
      qc.setQueryData(["inventory", "history", selected.id], (current: any) => {
        if (!current?.movements) return current;
        return { ...current, movements: [result.movement, ...(current.movements ?? []).filter((movement: InventoryMovement) => movement.id !== result.movement.id)].slice(0, 100) };
      });
      void qc.invalidateQueries({ queryKey: ["inventory", "summary"], refetchType: "inactive" });
      void qc.invalidateQueries({ queryKey: ["inventory", "recommendations"], refetchType: "inactive" });
      void qc.invalidateQueries({ queryKey: ["inventory", "count-status"] });
      if (showHistory) void qc.invalidateQueries({ queryKey: ["inventory", "history", selected.id] });
      void qc.invalidateQueries({ queryKey: ["procurement-intelligence"], refetchType: "inactive" });
      setShowMovement(false);
      setQuantity("");
      setNote("");
      setMessage({ text: `${movementLabels[movementType]} נשמרה בהצלחה: ${balanceAfter} ${unitLabel(selected)} במלאי.` });
    } catch (error) {
      setMessage({ text: error instanceof Error ? error.message : "שמירת התנועה נכשלה.", error: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div dir="rtl" className="space-y-5 pb-12">
      <header className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="bg-gradient-to-l from-indigo-700 via-indigo-600 to-blue-600 px-5 py-6 text-white sm:px-7 sm:py-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div><div className="mb-2 flex items-center gap-2 text-sm font-bold text-indigo-100"><Warehouse size={18}/> מחסן ומלאי</div><h1 className="text-3xl font-black tracking-tight sm:text-4xl">ניהול מלאי</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-indigo-100">ספירה פיזית היא נקודת האמת. אין צורך לדווח על כל לקיחה מהמחסן; הרכישות והספירות משמשות לחישוב קצב הצריכה.</p></div>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
              <a href="/dashboard/inventory/count" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-black text-indigo-700 shadow-lg hover:bg-indigo-50"><ClipboardCheck size={19}/> ספירת מלאי</a>\n              <button onClick={() => setShowScanner(true)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-black text-indigo-700 shadow-lg hover:bg-indigo-50"><ScanLine size={19}/> סרוק ברקוד</button>
              <button onClick={() => setShowBarcodeManager(true)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white/10 px-5 text-sm font-black text-white ring-1 ring-white/25 hover:bg-white/20"><Barcode size={18}/> ברקודים ומדבקות</button>
              <button onClick={() => qc.invalidateQueries({ queryKey: ["inventory"] })} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-white/20 bg-white/10 px-5 text-sm font-black hover:bg-white/20"><RefreshCw size={18}/> רענן</button>
            </div>
          </div>
        </div>
      </header>

      {message && !showMovement && <div className={`flex items-center gap-2 rounded-2xl p-4 text-sm font-black ${message.error ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"}`}>{message.error ? <AlertTriangle size={18}/> : <CheckCircle2 size={18}/>} {message.text}</div>}

      <section aria-label="סיכום מצב המלאי" className="grid gap-3 md:grid-cols-3">
        <button type="button" onClick={() => { setInventoryTab("urgent"); setStatusFilter("all"); }} className={`rounded-2xl border p-5 text-right shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${inventoryTab === "urgent" ? "border-red-300 bg-red-50 ring-2 ring-red-100 dark:border-red-900 dark:bg-red-950/30" : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"}`}>
          <div className="flex items-center justify-between"><span className="text-sm font-bold text-red-700 dark:text-red-300">רכש דחוף / דורש טיפול</span><span className="rounded-xl bg-red-100 p-2 text-red-700 dark:bg-red-900/40"><AlertTriangle size={20}/></span></div>
          <div className="mt-3 text-3xl font-black">{number(urgentCount)}</div><div className="mt-1 text-xs text-slate-500">מחסור או צורך בהזמנה לפי נתונים תקינים</div>
        </button>
        <button type="button" onClick={() => { setInventoryTab("needs_data"); setStatusFilter("all"); }} className={`rounded-2xl border p-5 text-right shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${inventoryTab === "needs_data" ? "border-amber-300 bg-amber-50 ring-2 ring-amber-100 dark:border-amber-900 dark:bg-amber-950/30" : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"}`}>
          <div className="flex items-center justify-between"><span className="text-sm font-bold text-amber-800 dark:text-amber-300">דורש השלמת נתונים</span><span className="rounded-xl bg-amber-100 p-2 text-amber-800 dark:bg-amber-900/40"><ClipboardCheck size={20}/></span></div>
          <div className="mt-3 text-3xl font-black">{number(needsDataCount)}</div><div className="mt-1 text-xs text-slate-500">מוצרים שממתינים לספירות או ליעד מלאי</div>
        </button>
        <button type="button" onClick={() => { setInventoryTab("all"); setStatusFilter("healthy"); }} className="rounded-2xl border border-slate-200 bg-white p-5 text-right shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-950">
          <div className="flex items-center justify-between"><span className="text-sm font-bold text-emerald-700 dark:text-emerald-300">מלאי תקין</span><span className="rounded-xl bg-emerald-100 p-2 text-emerald-700 dark:bg-emerald-900/40"><CheckCircle2 size={20}/></span></div>
          <div className="mt-3 text-3xl font-black">{number(healthyCount)}</div><div className="mt-1 text-xs text-slate-500">מוצרים עם נתונים תקינים שאינם דורשים רכש</div>
        </button>
      </section>


  <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-black">איתור וניהול מוצרים</h2><p className="mt-1 text-xs text-slate-500">תצוגה תמציתית עם חיפוש מיידי והיסטוריה לפי דרישה.</p></div><ProductSortToggle direction={sortDirection} onToggle={() => setSortDirection((current) => current === "asc" ? "desc" : "asc")} /></div>
  <div role="tablist" aria-label="תצוגת מלאי" className="mb-4 grid grid-cols-3 gap-2">{([{id:"urgent",label:"🚨 רכש דחוף",count:urgentCount},{id:"needs_data",label:"⚠️ דורש השלמת נתונים",count:needsDataCount},{id:"all",label:"📦 כלל המוצרים",count:products.length}] as const).map((tab) => <button key={tab.id} role="tab" aria-selected={inventoryTab===tab.id} onClick={() => { setInventoryTab(tab.id); setStatusFilter("all"); }} className={`rounded-xl px-3 py-3 text-sm font-black ${inventoryTab===tab.id ? "bg-indigo-600 text-white shadow-sm" : "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300"}`}>{tab.label}<span className="mr-2 rounded-full bg-white/20 px-2 py-0.5 text-xs">{tab.count}</span></button>)}</div>
  <div className="flex flex-col gap-3 lg:flex-row lg:items-center"><label className="relative min-w-0 flex-1"><Search className="absolute right-3 top-3.5 text-slate-400" size={19}/><input ref={searchInputRef} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חפש לפי שם מוצר, מק״ט, ברקוד או קטגוריה…" className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pr-10 pl-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900"/><span className="absolute left-3 top-3 rounded-md border border-slate-200 px-1.5 py-0.5 text-[10px] font-bold text-slate-400">Ctrl K</span></label>
  <select aria-label="סינון לפי ספק" value={supplierFilter} onChange={(e)=>setSupplierFilter(e.target.value)} className="min-h-12 rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="all">כל הספקים</option>{suppliers.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select>
  <select aria-label="סינון לפי קטגוריה" value={categoryFilter} onChange={(e)=>setCategoryFilter(e.target.value)} className="min-h-12 rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm dark:border-slate-700 dark:bg-slate-900"><option value="all">כל הקטגוריות</option>{categories.map((category)=><option key={category} value={category}>{category}</option>)}</select></div>
  <div className="mt-3 flex flex-wrap items-center gap-2"><span className="text-xs text-slate-500">קטגוריות נפוצות:</span><button type="button" onClick={()=>setCategoryFilter("all")} className={`rounded-full px-3 py-1.5 text-xs font-bold ${categoryFilter === "all" ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300"}`}>הכול</button>{categories.slice(0,5).map((category)=><button type="button" key={category} onClick={()=>setCategoryFilter(category)} className={`rounded-full px-3 py-1.5 text-xs font-bold ${categoryFilter === category ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300"}`}>{category}</button>)}{suppliers.slice(0,4).map(([id,name])=><button type="button" key={id} onClick={()=>setSupplierFilter(id)} className={`rounded-full px-3 py-1.5 text-xs font-bold ${supplierFilter === id ? "bg-violet-600 text-white" : "bg-violet-50 text-violet-700 dark:bg-violet-950/30 dark:text-violet-300"}`}>{name}</button>)}</div>
  <div className="mt-3 flex flex-wrap items-center gap-2"><span className="text-xs text-slate-500">סינון לפי מצב:</span>{(["all","urgent","reorder","healthy","insufficient_data"] as const).map((filter) => <button key={filter} onClick={() => setStatusFilter(filter)} className={`rounded-full px-3 py-2 text-xs font-bold ${statusFilter === filter ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300"}`}>{filter === "all" ? "כל המצבים" : statusMeta[filter].label}</button>)}</div>
</section>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-200 p-5 dark:border-slate-800"><div><h2 className="text-xl font-black">מלאי לפי מוצר</h2><p className="mt-1 text-xs text-slate-500">{rows.length} מוצרים מוצגים מתוך {products.length} · בחר מוצר לפתיחת פרטים מלאים והיסטוריית תנועות.</p></div><div className="rounded-xl bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">תצוגה תמציתית</div></div>
        <div dir="rtl" className="hidden w-full min-w-0 max-w-full overflow-x-auto overscroll-x-contain md:block"><table dir="rtl" className="w-full min-w-[700px] text-right text-sm"><thead className="bg-slate-50 text-xs font-bold text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">שם המוצר / מק״ט</th><th className="px-5 py-3">סטטוס ומלאי</th><th className="px-5 py-3">המלצת רכש / נתונים חסרים</th><th className="px-5 py-3">פעולה מהירה</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{rows.map((product) => <InventoryProductRow key={product.id} product={product} forecast={recommendationByProduct.get(product.id)} status={stockStatus(product, recommendationByProduct.get(product.id))} onMovement={openMovement} onHistory={openHistory} />)}</tbody></table></div>
        <div className="space-y-3 p-3 md:hidden">{rows.map((product) => <InventoryProductRow key={product.id} mobile product={product} forecast={recommendationByProduct.get(product.id)} status={stockStatus(product, recommendationByProduct.get(product.id))} onMovement={openMovement} onHistory={openHistory} />)}</div>
        {!rows.length && <div className="p-12 text-center"><Package className="mx-auto text-slate-300" size={40}/><h3 className="mt-3 font-black">לא נמצאו מוצרים</h3></div>}
      </section>





      <details className="rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"><summary className="cursor-pointer px-5 py-4 text-sm font-black">כלי תכנון מלאי מתקדמים</summary><div className="border-t border-slate-200 p-4 dark:border-slate-800"><InventoryPlanningPanel /></div></details>

      {showMovement && selected && <div className="fixed inset-0 z-[200] flex items-end justify-center bg-slate-950/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"><div className="w-full max-w-lg rounded-t-3xl bg-white p-5 shadow-2xl dark:bg-slate-950 sm:rounded-3xl"><div className="flex items-start justify-between gap-4"><div><div className="text-xs font-bold text-indigo-600">פעולת מחסן</div><h2 className="mt-1 text-2xl font-black">{selected.name}</h2><p className="mt-1 text-xs text-slate-500">מלאי נוכחי: {selected.current_stock == null ? "לא ידוע" : number(selected.current_stock)} {unitLabel(selected)}</p></div><button onClick={closeMovement} disabled={busy} className="rounded-xl bg-slate-100 p-2 disabled:opacity-50"><X size={19}/></button></div><div className="mt-5 grid grid-cols-4 gap-2">{(Object.keys(movementLabels) as InventoryMovementType[]).map((type) => <button key={type} disabled={busy} onClick={() => {setMovementType(type);setQuantity(type === "count" || type === "adjustment" ? String(selected.current_stock ?? 0) : "");}} className={`rounded-xl py-3 text-xs font-black disabled:opacity-50 ${movementType===type ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"}`}>{movementLabels[type]}</button>)}</div><label className="mt-5 block"><span className="text-sm font-bold">{movementType === "count" ? `כמות בפועל (${unitLabel(selected)})` : movementType === "receipt" ? `כמות שהתקבלה (${unitLabel(selected)})` : movementType === "issue" ? `כמות שנופקה (${unitLabel(selected)})` : `כמות לאחר ההתאמה (${unitLabel(selected)})`}</span><input autoFocus inputMode="numeric" type="number" min="0" step="1" disabled={busy} value={quantity} onChange={(e)=>setQuantity(e.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-3xl font-black outline-none focus:border-indigo-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900"/></label><input disabled={busy} value={note} onChange={(e)=>setNote(e.target.value)} placeholder="הערה (אופציונלי)" className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm outline-none focus:border-indigo-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900"/>{message && <div className={`mt-3 rounded-xl p-3 text-sm font-bold ${message.error ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"}`}>{message.text}</div>}<button onClick={submitMovement} disabled={busy || quantity === ""} className="mt-5 inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-2xl bg-indigo-600 text-base font-black text-white disabled:opacity-50">{busy ? <><RefreshCw className="animate-spin" size={20}/> שומר את המלאי...</> : <><CheckCircle2 size={20}/> שמור {movementLabels[movementType]}</>}</button><button onClick={closeMovement} disabled={busy} className="mt-2 w-full rounded-xl py-3 text-sm font-black text-slate-500 disabled:opacity-50">ביטול</button></div></div>}

      {showHistory && selected && <div className="fixed inset-0 z-[200] flex justify-end bg-slate-950/50 backdrop-blur-sm" onClick={() => setShowHistory(false)}><aside role="dialog" aria-modal="true" aria-label={`פרטי מוצר: ${selected.name}`} onClick={(event) => event.stopPropagation()} className="flex h-full w-full max-w-xl flex-col overflow-hidden border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-950"><div className="flex items-start justify-between border-b border-slate-200 p-5 dark:border-slate-800"><div><div className="text-xs font-bold text-indigo-600">היסטוריית מחסן</div><h2 className="mt-1 text-2xl font-black">{selected.name}</h2><p className="mt-1 text-xs text-slate-500">הכמויות מוצגות ב{unitLabel(selected)}.</p></div><button onClick={()=>setShowHistory(false)} className="rounded-xl bg-slate-100 p-2"><X size={19}/></button></div><div className="overflow-y-auto p-4"><div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">מלאי נוכחי</div><div className="mt-1 text-xl font-black">{selected.current_stock == null ? "לא ידוע" : number(selected.current_stock)} <span className="text-xs font-normal">{unitLabel(selected)}</span></div></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">צריכה שבועית</div><div className="mt-1 text-xl font-black">{selectedForecast?.data_ready && selectedForecast?.carton_recommendation_ready && selectedForecast?.average_daily_usage_cartons != null ? cartonNumber(selectedForecast.average_daily_usage_cartons * 7) + " קרטונים" : "אין נתון אמין"}</div></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">מצב</div><div className="mt-2"><span className={`rounded-full px-2.5 py-1 text-xs font-black ${statusMeta[stockStatus(selected, selectedForecast)].className}`}>{statusMeta[stockStatus(selected, selectedForecast)].label}</span></div></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">יעד מלאי</div><div className="mt-1 font-black">{selectedForecast?.configured_stock_target != null ? cartonNumber(selectedForecast.configured_stock_target) : "לא הוגדר"}</div></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">ספירות בתקופה</div><div className="mt-1 font-black">{number(selectedForecast?.stock_checks_in_period ?? 0)}</div></div><div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">המלצת רכש</div><div className="mt-1 font-black">{selectedForecast?.status === "insufficient_data" ? (selectedForecast?.needs_data_reason === "stock_target_not_configured" ? "יש להגדיר יעד מלאי" : "נדרשות ספירות נוספות") : selectedForecast?.recommended_order_cartons != null && Number(selectedForecast.recommended_order_cartons) > 0 ? number(selectedForecast.recommended_order_cartons) + " קרטונים" : "אין צורך בהזמנה"}</div></div></div>{history.isLoading && <div className="p-8 text-center text-sm text-slate-500"><RefreshCw className="mx-auto mb-2 animate-spin" size={22}/>טוען היסטוריה...</div>}{!history.isLoading && !(history.data?.movements ?? []).length && <div className="p-8 text-center text-sm text-slate-500">אין היסטוריה למוצר הזה.</div>}{(history.data?.movements ?? []).map((movement) => <MovementRow key={movement.id} movement={movement} products={products} detailed/>)}</div><div className="border-t border-slate-200 p-4"><button onClick={()=>{setShowHistory(false);openMovement(selected,"count");}} className="min-h-12 w-full rounded-xl bg-indigo-600 font-black text-white">בצע ספירה חדשה</button></div></div></aside></div>}

      <InventoryBarcodeManager open={showBarcodeManager} products={products} displayedProducts={rows} onClose={()=>setShowBarcodeManager(false)} onRefresh={()=>qc.invalidateQueries({queryKey:["inventory","summary"]})}/>
      <InventoryScannerModal open={showScanner} onClose={()=>setShowScanner(false)}/>
    </div>
  );
}

type InventoryProductRowProps = {
  product: Product;
  forecast: any;
  status: keyof typeof statusMeta;
  onMovement: (product: Product, type: InventoryMovementType) => void;
  onHistory: (product: Product) => void;
  mobile?: boolean;
};

const InventoryProductRow = memo(function InventoryProductRow({ product, forecast, status, onMovement, onHistory, mobile = false }: InventoryProductRowProps) {
  const stock = product.current_stock == null ? "לא ידוע" : number(product.current_stock);
  const weekly = forecast?.data_ready && forecast?.carton_recommendation_ready && forecast.average_daily_usage_cartons != null
    ? cartonNumber(forecast.average_daily_usage_cartons * 7) : "—";
  const order = forecast?.recommended_order_cartons != null && Number(forecast.recommended_order_cartons) > 0
    ? number(forecast.recommended_order_cartons) : null;
  const missingReason = forecast?.needs_data_reason === "stock_target_not_configured"
    ? "יש להגדיר יעד מלאי"
    : `נדרשות לפחות 2 ספירות פיזיות (כרגע ${number(forecast?.stock_checks_in_period ?? 0)})`;
  const recommendation = status === "insufficient_data"
    ? missingReason
    : order ? `מומלץ להזמין ${order} קרטונים`
    : status === "healthy" ? "אין צורך בהזמנה לפי הנתונים" : "בדוק את יעד המלאי וההזמנות הפתוחות";
  if (mobile) return <article className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
    <div className="flex items-start justify-between gap-3"><button onClick={() => onHistory(product)} className="min-w-0 text-right"><h3 className="font-black">{product.name}</h3><p className="mt-1 text-xs text-slate-400">{product.sku || "ללא מק״ט"} · {product.barcode || "ללא ברקוד"}</p></button><span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-black ${statusMeta[status].className}`}>{statusMeta[status].label}</span></div>
    <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div><div className="text-xs text-slate-500">מלאי נוכחי</div><div className="font-black">{stock} <span className="text-xs font-normal">{unitSingular(product)}</span></div></div><div className="text-left"><div className="text-xs text-slate-500">צריכה שבועית</div><div className="font-black">{weekly === "—" ? "אין נתון אמין" : `${weekly} קרטונים`}</div></div></div>
    <div className="mt-3 text-sm font-bold">{recommendation}</div>
    <div className="mt-3 flex gap-2"><button onClick={() => onMovement(product,"count")} className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-black text-white">{status === "insufficient_data" ? "עדכן ספירה" : "ספירה חדשה"}</button><button onClick={() => onHistory(product)} className="rounded-xl bg-slate-100 px-4 py-3 text-xs font-black text-slate-700 dark:bg-slate-800 dark:text-slate-200">פרטים והיסטוריה</button></div>
  </article>;
  return <tr className="group cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900/60" onClick={() => onHistory(product)}>
    <td className="px-5 py-4"><button onClick={(event) => { event.stopPropagation(); onHistory(product); }} className="text-right font-black hover:text-indigo-600">{product.name}<span className="mt-0.5 block text-xs font-normal text-slate-400">{product.sku || "ללא מק״ט"}{product.barcode ? ` · ${product.barcode}` : ""}</span></button></td>
    <td className="px-5 py-4"><div><span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${statusMeta[status].className}`}>{statusMeta[status].label}</span></div><div className="mt-2 text-base font-black">{stock} <span className="text-xs font-normal text-slate-400">{unitSingular(product)}</span></div></td>
    <td className="px-5 py-4"><div className={`font-bold ${status === "insufficient_data" ? "text-amber-700 dark:text-amber-300" : ""}`}>{recommendation}</div>{status !== "insufficient_data" && <div className="mt-1 text-xs text-slate-500">{weekly === "—" ? "צריכה שבועית: אין נתון אמין" : `צריכה שבועית: ${weekly} קרטונים`}</div>}</td>
    <td className="px-5 py-4"><div className="flex items-center gap-2"><button title="עדכן ספירה" aria-label={`עדכן ספירה: ${product.name}`} onClick={(event) => { event.stopPropagation(); onMovement(product,"count"); }} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-indigo-600 px-3 text-xs font-black text-white"><ClipboardCheck size={16}/> ספירה</button><button title="פרטים והיסטוריה" aria-label={`פרטים והיסטוריה: ${product.name}`} onClick={(event) => { event.stopPropagation(); onHistory(product); }} className="rounded-xl bg-slate-100 p-2 text-slate-700 dark:bg-slate-800 dark:text-slate-200"><History size={17}/></button></div></td>
  </tr>;
});

function MovementRow({ movement, products, detailed = false }: { movement: InventoryMovement; products: Product[]; detailed?: boolean }) {
  const product = products.find((item) => item.id === movement.product_id);
  const sign = movement.movement_type === "receipt" ? "+" : movement.movement_type === "issue" ? "−" : "";
  return <div className="flex items-center gap-3 px-5 py-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600"><ClipboardCheck size={17}/></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-bold">{detailed ? movementLabels[movement.movement_type] : product?.name || `מוצר #${movement.product_id}`}</span><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">{movementLabels[movement.movement_type]}</span></div><div className="mt-0.5 text-xs text-slate-400">{dateTime(movement.occurred_at)}{movement.note ? ` · ${movement.note}` : ""}</div></div><div className="text-left"><div className="font-black">{sign}{number(movement.quantity)}</div>{movement.balance_after != null && <div className="text-[10px] text-slate-400">יתרה {number(movement.balance_after)} {unitLabel(product)}</div>}</div></div>;
}
