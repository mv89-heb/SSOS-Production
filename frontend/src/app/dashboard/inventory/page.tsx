// @ts-nocheck
"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowDownToLine, ArrowUpFromLine, Barcode, CheckCircle2,
  ClipboardCheck, History, Package, RefreshCw, ScanLine, Search,
  SlidersHorizontal, Truck, Warehouse, X,
} from "lucide-react";
import { inventoryService, type InventoryMovement, type InventoryMovementType } from "@/services/inventory-service";
import InventoryBarcodeManager from "@/components/inventory/inventory-barcode-manager";
import InventoryScannerModal from "@/components/inventory/inventory-scanner-modal";
import type { Product } from "@/types";

const number = (value: number | null | undefined) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 }).format(Number(value ?? 0));
const dateTime = (value: string) => new Intl.DateTimeFormat("he-IL", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
const movementLabels: Record<InventoryMovementType, string> = { count: "ספירה", receipt: "קבלה", issue: "ניפוק", adjustment: "התאמה" };
const unitLabel = (product: Product | null | undefined) => product?.unit === "יחידה" ? "יחידות" : "ארגזים";
const unitSingular = (product: Product | null | undefined) => product?.unit === "יחידה" ? "יחידה" : "ארגז";
const statusMeta = {
  urgent: { label: "חסר במלאי", className: "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" },
  reorder: { label: "להזמין", className: "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300" },
  healthy: { label: "תקין", className: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300" },
  insufficient_data: { label: "צריך עוד ספירות", className: "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300" },
} as const;

function stockStatus(product: Product) {
  const stock = Number(product.current_stock ?? 0);
  if (stock <= 0) return "urgent" as const;
  if (product.min_stock != null && stock <= Number(product.min_stock)) return "reorder" as const;
  return "healthy" as const;
}

export default function InventoryPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "urgent" | "reorder" | "healthy">("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [movementType, setMovementType] = useState<InventoryMovementType>("count");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [showMovement, setShowMovement] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showScanner, setShowScanner] = useState(false);
  const [showBarcodeManager, setShowBarcodeManager] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const summary = useQuery({ queryKey: ["inventory", "summary"], queryFn: inventoryService.getSummary, staleTime: 20_000 });
  const recommendations = useQuery({ queryKey: ["inventory", "recommendations"], queryFn: () => inventoryService.getRecommendations({ limit: 500 }), staleTime: 30_000 });
  const history = useQuery({ queryKey: ["inventory", "history", selectedId], queryFn: () => inventoryService.getProductMovements(selectedId!, 100), enabled: selectedId != null && showHistory });
  const products = summary.data?.products ?? [];

  const rows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("he");
    return products.filter((product) => {
      const matches = !query || [product.name, product.sku, product.barcode, product.category].filter(Boolean).some((v) => String(v).toLocaleLowerCase("he").includes(query));
      return matches && (statusFilter === "all" || stockStatus(product) === statusFilter);
    });
  }, [products, search, statusFilter]);

  const selected = products.find((product) => product.id === selectedId) ?? null;

  const openMovement = (product: Product, type: InventoryMovementType) => {
    setSelectedId(product.id);
    setMovementType(type);
    setQuantity(type === "count" || type === "adjustment" ? String(product.current_stock ?? 0) : "");
    setNote("");
    setMessage(null);
    setShowHistory(false);
    setShowMovement(true);
  };

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
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["inventory", "summary"] }),
        qc.invalidateQueries({ queryKey: ["inventory", "recommendations"] }),
        qc.invalidateQueries({ queryKey: ["inventory", "history", selected.id] }),
        qc.invalidateQueries({ queryKey: ["procurement-intelligence"] }),
      ]);
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
            <div><div className="mb-2 flex items-center gap-2 text-sm font-bold text-indigo-100"><Warehouse size={18}/> מחסן ומלאי</div><h1 className="text-3xl font-black tracking-tight sm:text-4xl">ניהול מלאי</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-indigo-100">ספירה, קבלה וניפוק לפי מוצר. ברירת המחדל היא ארגזים; מוצרים מיוחדים יכולים להיספר ביחידות.</p></div>
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
              <button onClick={() => setShowScanner(true)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-black text-indigo-700 shadow-lg hover:bg-indigo-50"><ScanLine size={19}/> סרוק ברקוד</button>
              <button onClick={() => setShowBarcodeManager(true)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-white/10 px-5 text-sm font-black text-white ring-1 ring-white/25 hover:bg-white/20"><Barcode size={18}/> ברקודים ומדבקות</button>
              <button onClick={() => qc.invalidateQueries({ queryKey: ["inventory"] })} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-white/20 bg-white/10 px-5 text-sm font-black hover:bg-white/20"><RefreshCw size={18}/> רענן</button>
            </div>
          </div>
        </div>
      </header>

      {message && !showMovement && <div className={`flex items-center gap-2 rounded-2xl p-4 text-sm font-black ${message.error ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"}`}>{message.error ? <AlertTriangle size={18}/> : <CheckCircle2 size={18}/>} {message.text}</div>}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[["מוצרים פעילים", summary.data?.stats.active_products ?? 0, Package], ["מלאי חסר", summary.data?.stats.out_of_stock ?? 0, AlertTriangle], ["מתחת למינימום", summary.data?.stats.low_stock ?? 0, SlidersHorizontal], ["ללא כללי מלאי", summary.data?.stats.without_stock_rule ?? 0, ClipboardCheck], ["תנועות אחרונות", summary.data?.stats.movement_count ?? 0, History]].map(([label, value, Icon]) => { const C = Icon as typeof Package; return <button key={String(label)} onClick={() => label === "מלאי חסר" ? setStatusFilter("urgent") : label === "מתחת למינימום" ? setStatusFilter("reorder") : undefined} className="rounded-2xl border border-slate-200 bg-white p-5 text-right shadow-sm dark:border-slate-800 dark:bg-slate-950"><C className="text-indigo-500" size={21}/><div className="mt-3 text-xs font-bold text-slate-500">{label}</div><div className="mt-1 text-2xl font-black">{number(Number(value))}</div></button>; })}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-col gap-3 lg:flex-row lg:items-center"><label className="relative min-w-0 flex-1"><Search className="absolute right-3 top-3.5 text-slate-400" size={19}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חפש לפי מוצר, מק״ט, ברקוד או קטגוריה…" className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pr-10 pl-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900"/></label><div className="flex flex-wrap gap-2">{(["all","urgent","reorder","healthy"] as const).map((filter) => <button key={filter} onClick={() => setStatusFilter(filter)} className={`rounded-xl px-4 py-3 text-sm font-black ${statusFilter === filter ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-300"}`}>{filter === "all" ? "הכול" : statusMeta[filter].label}</button>)}</div></div></section>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
        <div className="flex items-center justify-between border-b border-slate-200 p-5 dark:border-slate-800"><div><h2 className="text-xl font-black">מלאי לפי מוצר</h2><p className="mt-1 text-xs text-slate-500">{rows.length} מוצרים · הכמות היא ארגזים כברירת מחדל.</p></div><div className="rounded-xl bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">ברקוד = מוצר, לא ספק</div></div>
        <div className="hidden overflow-x-auto md:block"><table className="w-full text-right text-sm"><thead className="bg-slate-50 text-xs font-bold text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">מוצר</th><th className="px-5 py-3">מק״ט</th><th className="px-5 py-3">ברקוד</th><th className="px-5 py-3">מלאי</th><th className="px-5 py-3">מינימום</th><th className="px-5 py-3">יעד</th><th className="px-5 py-3">מצב</th><th className="px-5 py-3">פעולות</th></tr></thead><tbody className="divide-y divide-slate-100 dark:divide-slate-800">{rows.map((product) => { const status = stockStatus(product); return <tr key={product.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/60"><td className="px-5 py-4"><button onClick={() => {setSelectedId(product.id);setShowHistory(true);}} className="text-right font-black hover:text-indigo-600">{product.name}<span className="mt-0.5 block text-xs font-normal text-slate-400">{product.category || "ללא קטגוריה"}</span></button></td><td className="px-5 py-4 font-mono text-xs text-slate-500">{product.sku || "—"}</td><td className="px-5 py-4 font-mono text-[10px] text-slate-500">{product.barcode || "חסר"}</td><td className="px-5 py-4 text-lg font-black">{number(product.current_stock)} <span className="text-xs font-normal text-slate-400">{unitSingular(product)}</span></td><td className="px-5 py-4">{product.min_stock == null ? "—" : number(product.min_stock)}</td><td className="px-5 py-4">{product.recommended_stock == null ? "—" : number(product.recommended_stock)}</td><td className="px-5 py-4"><span className={`rounded-full px-3 py-1 text-xs font-black ${statusMeta[status].className}`}>{statusMeta[status].label}</span></td><td className="px-5 py-4"><div className="flex gap-2"><button title="ספירה" onClick={() => openMovement(product,"count")} className="rounded-lg bg-indigo-50 p-2 text-indigo-700"><ClipboardCheck size={17}/></button><button title="קבלה" onClick={() => openMovement(product,"receipt")} className="rounded-lg bg-emerald-50 p-2 text-emerald-700"><ArrowDownToLine size={17}/></button><button title="ניפוק" onClick={() => openMovement(product,"issue")} className="rounded-lg bg-amber-50 p-2 text-amber-700"><ArrowUpFromLine size={17}/></button><button title="היסטוריה" onClick={() => {setSelectedId(product.id);setShowHistory(true);}} className="rounded-lg bg-slate-100 p-2 text-slate-600"><History size={17}/></button></div></td></tr>; })}</tbody></table></div>
        <div className="space-y-3 p-3 md:hidden">{rows.map((product) => { const status = stockStatus(product); return <article key={product.id} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800"><div className="flex items-start justify-between gap-3"><div><h3 className="font-black">{product.name}</h3><p className="mt-1 text-xs text-slate-400">{product.sku || "ללא מק״ט"} · {product.barcode || "ללא ברקוד"}</p></div><span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${statusMeta[status].className}`}>{statusMeta[status].label}</span></div><div className="mt-4 rounded-xl bg-slate-50 p-4 text-center dark:bg-slate-900"><div className="text-xs text-slate-400">מלאי</div><div className="text-2xl font-black">{number(product.current_stock)} <span className="text-sm font-normal">{unitLabel(product)}</span></div></div><div className="mt-3 grid grid-cols-4 gap-2"><button onClick={() => openMovement(product,"count")} className="rounded-xl bg-indigo-600 py-3 text-xs font-black text-white">ספירה</button><button onClick={() => openMovement(product,"receipt")} className="rounded-xl bg-emerald-600 py-3 text-xs font-black text-white">קבלה</button><button onClick={() => openMovement(product,"issue")} className="rounded-xl bg-amber-500 py-3 text-xs font-black text-white">ניפוק</button><button onClick={() => {setSelectedId(product.id);setShowHistory(true);}} className="rounded-xl bg-slate-100 py-3 text-xs font-black text-slate-700">היסטוריה</button></div></article>; })}</div>
        {!rows.length && <div className="p-12 text-center"><Package className="mx-auto text-slate-300" size={40}/><h3 className="mt-3 font-black">לא נמצאו מוצרים</h3></div>}
      </section>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-200 p-5 dark:border-slate-800"><div className="flex items-center gap-2"><Truck className="text-indigo-600" size={20}/><div><h2 className="font-black">המלצות רכש</h2><p className="mt-1 text-xs text-slate-500">מבוססות על ספירות פיזיות וקצב צריכה.</p></div></div></div><div className="grid gap-3 p-4 lg:grid-cols-2">{(recommendations.data ?? []).filter((row) => row.status === "urgent" || row.status === "reorder").slice(0,20).map((row) => <button key={row.product_id} onClick={() => {const product=products.find((p)=>p.id===row.product_id);if(product)openMovement(product,"count");}} className="rounded-2xl border border-slate-200 p-4 text-right dark:border-slate-800"><div className="flex items-center justify-between gap-3"><span className="font-black">{row.product_name}</span><span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${statusMeta[row.status].className}`}>{statusMeta[row.status].label}</span></div><div className="mt-3 grid grid-cols-3 gap-2 text-xs"><div><span className="text-slate-400">מלאי</span><strong className="mt-1 block text-base">{number(row.current_stock)}</strong></div><div><span className="text-slate-400">נקודת הזמנה</span><strong className="mt-1 block text-base">{number(row.reorder_point)}</strong></div><div><span className="text-slate-400">מומלץ להזמין</span><strong className="mt-1 block text-base">{number(row.recommended_order)}</strong></div></div></button>)}{!(recommendations.data ?? []).some((row) => row.status === "urgent" || row.status === "reorder") && <div className="p-8 text-center text-sm text-slate-500 lg:col-span-2">אין כרגע המלצות דחופות או להזמנה.</div>}</div></section>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b border-slate-200 p-5 dark:border-slate-800"><h2 className="font-black">תנועות אחרונות</h2></div><div className="divide-y divide-slate-100 dark:divide-slate-800">{(summary.data?.recent_movements ?? []).slice(0,12).map((movement) => <MovementRow key={movement.id} movement={movement} products={products}/>)}{!summary.data?.recent_movements?.length && <div className="p-8 text-center text-sm text-slate-500">עדיין לא נרשמו תנועות מלאי.</div>}</div></section>

      {showMovement && selected && <div className="fixed inset-0 z-[200] flex items-end justify-center bg-slate-950/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"><div className="w-full max-w-lg rounded-t-3xl bg-white p-5 shadow-2xl dark:bg-slate-950 sm:rounded-3xl"><div className="flex items-start justify-between gap-4"><div><div className="text-xs font-bold text-indigo-600">פעולת מחסן</div><h2 className="mt-1 text-2xl font-black">{selected.name}</h2><p className="mt-1 text-xs text-slate-500">מלאי נוכחי: {number(selected.current_stock)} {unitLabel(selected)}</p></div><button onClick={closeMovement} disabled={busy} className="rounded-xl bg-slate-100 p-2 disabled:opacity-50"><X size={19}/></button></div><div className="mt-5 grid grid-cols-4 gap-2">{(Object.keys(movementLabels) as InventoryMovementType[]).map((type) => <button key={type} disabled={busy} onClick={() => {setMovementType(type);setQuantity(type === "count" || type === "adjustment" ? String(selected.current_stock ?? 0) : "");}} className={`rounded-xl py-3 text-xs font-black disabled:opacity-50 ${movementType===type ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"}`}>{movementLabels[type]}</button>)}</div><label className="mt-5 block"><span className="text-sm font-bold">{movementType === "count" ? `כמות בפועל (${unitLabel(selected)})` : movementType === "receipt" ? `כמות שהתקבלה (${unitLabel(selected)})` : movementType === "issue" ? `כמות שנופקה (${unitLabel(selected)})` : `כמות לאחר ההתאמה (${unitLabel(selected)})`}</span><input autoFocus inputMode="numeric" type="number" min="0" step="1" disabled={busy} value={quantity} onChange={(e)=>setQuantity(e.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-3xl font-black outline-none focus:border-indigo-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900"/></label><input disabled={busy} value={note} onChange={(e)=>setNote(e.target.value)} placeholder="הערה (אופציונלי)" className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm outline-none focus:border-indigo-500 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900"/>{message && <div className={`mt-3 rounded-xl p-3 text-sm font-bold ${message.error ? "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"}`}>{message.text}</div>}<button onClick={submitMovement} disabled={busy || quantity === ""} className="mt-5 inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-2xl bg-indigo-600 text-base font-black text-white disabled:opacity-50">{busy ? <><RefreshCw className="animate-spin" size={20}/> שומר את המלאי...</> : <><CheckCircle2 size={20}/> שמור {movementLabels[movementType]}</>}</button><button onClick={closeMovement} disabled={busy} className="mt-2 w-full rounded-xl py-3 text-sm font-black text-slate-500 disabled:opacity-50">ביטול</button></div></div>}

      {showHistory && selected && <div className="fixed inset-0 z-[200] flex items-end justify-center bg-slate-950/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"><div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-t-3xl bg-white shadow-2xl dark:bg-slate-950 sm:rounded-3xl"><div className="flex items-start justify-between border-b border-slate-200 p-5 dark:border-slate-800"><div><div className="text-xs font-bold text-indigo-600">היסטוריית מחסן</div><h2 className="mt-1 text-2xl font-black">{selected.name}</h2><p className="mt-1 text-xs text-slate-500">הכמויות מוצגות ב{unitLabel(selected)}.</p></div><button onClick={()=>setShowHistory(false)} className="rounded-xl bg-slate-100 p-2"><X size={19}/></button></div><div className="max-h-[65vh] overflow-y-auto p-4">{history.isLoading && <div className="p-8 text-center text-sm text-slate-500"><RefreshCw className="mx-auto mb-2 animate-spin" size={22}/>טוען היסטוריה...</div>}{!history.isLoading && !(history.data?.movements ?? []).length && <div className="p-8 text-center text-sm text-slate-500">אין היסטוריה למוצר הזה.</div>}{(history.data?.movements ?? []).map((movement) => <MovementRow key={movement.id} movement={movement} products={products} detailed/>)}</div><div className="border-t border-slate-200 p-4"><button onClick={()=>{setShowHistory(false);openMovement(selected,"count");}} className="min-h-12 w-full rounded-xl bg-indigo-600 font-black text-white">בצע ספירה חדשה</button></div></div></div>}

      <InventoryBarcodeManager open={showBarcodeManager} products={products} displayedProducts={rows} onClose={()=>setShowBarcodeManager(false)} onRefresh={()=>qc.invalidateQueries({queryKey:["inventory","summary"]})}/>
      <InventoryScannerModal open={showScanner} onClose={()=>setShowScanner(false)}/>
    </div>
  );
}

function MovementRow({ movement, products, detailed = false }: { movement: InventoryMovement; products: Product[]; detailed?: boolean }) {
  const product = products.find((item) => item.id === movement.product_id);
  const sign = movement.movement_type === "receipt" ? "+" : movement.movement_type === "issue" ? "−" : "";
  return <div className="flex items-center gap-3 px-5 py-3"><div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600"><ClipboardCheck size={17}/></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-bold">{detailed ? movementLabels[movement.movement_type] : product?.name || `מוצר #${movement.product_id}`}</span><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">{movementLabels[movement.movement_type]}</span></div><div className="mt-0.5 text-xs text-slate-400">{dateTime(movement.occurred_at)}{movement.note ? ` · ${movement.note}` : ""}</div></div><div className="text-left"><div className="font-black">{sign}{number(movement.quantity)}</div>{movement.balance_after != null && <div className="text-[10px] text-slate-400">יתרה {number(movement.balance_after)} {unitLabel(product)}</div>}</div></div>;
}
