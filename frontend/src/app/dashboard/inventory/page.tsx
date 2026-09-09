"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowDownToLine, ArrowUpFromLine, ClipboardCheck, Package, RefreshCw, Search, Smartphone, Warehouse } from "lucide-react";
import { catalogService } from "@/services/catalog-service";
import { priceIntelligenceService, type InventoryRecommendation } from "@/services/price-intelligence-service";

const n = (v: number | null | undefined) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 1 }).format(Number(v ?? 0));

export default function InventoryPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const products = useQuery({ queryKey: ["inventory", "products"], queryFn: () => catalogService.listProducts(undefined, true) });
  const recommendations = useQuery({ queryKey: ["inventory", "recommendations"], queryFn: () => priceIntelligenceService.getInventoryRecommendations({ limit: 100 }) });
  const rows = useMemo(() => (products.data ?? []).filter((p) => p.name.toLowerCase().includes(search.toLowerCase()) || String(p.sku ?? "").toLowerCase().includes(search.toLowerCase())).slice(0, 30), [products.data, search]);
  const selected = (products.data ?? []).find((p) => p.id === selectedId);

  const saveCount = async () => {
    const qty = Number(quantity);
    if (!selected || !Number.isInteger(qty) || qty < 0) return setMessage("הזן כמות שלמה ואפס ומעלה.");
    setBusy(true); setMessage(null);
    try {
      await priceIntelligenceService.recordStockCheck(selected.id, qty, note || undefined);
      setQuantity(""); setNote("");
      setMessage(`המלאי של ${selected.name} עודכן ל־${n(qty)}.`);
      await Promise.all([qc.invalidateQueries({ queryKey: ["inventory"] }), qc.invalidateQueries({ queryKey: ["procurement-intelligence"] })]);
    } catch (e) { setMessage(e instanceof Error ? e.message : "העדכון נכשל."); }
    finally { setBusy(false); }
  };

  return (
    <div dir="rtl" className="space-y-5 pb-10">
      <header className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950 sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div><div className="mb-2 flex items-center gap-2 text-indigo-600"><Warehouse size={18}/><span className="text-sm font-bold">מחסן ומלאי</span></div><h1 className="text-3xl font-black">מחסן ומלאי</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">ספירה מהטלפון, עדכון מיידי במערכת, והמלצות רכש שמתבססות על הספירות והתנועה בפועל.</p></div>
          <div className="hidden rounded-2xl bg-indigo-50 p-4 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300 sm:block"><Smartphone size={28}/><div className="mt-1 text-xs font-bold">מותאם לעבודה מהמחסן</div></div>
        </div>
      </header>

      <section className="rounded-3xl border border-indigo-200 bg-white p-4 shadow-sm dark:border-indigo-900 dark:bg-slate-950 sm:p-6">
        <div className="flex items-center gap-2"><ClipboardCheck className="text-indigo-600" size={20}/><h2 className="text-xl font-black">ספירת מלאי מהירה</h2></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_180px_auto]">
          <label className="relative block"><Search className="absolute right-3 top-3.5 text-slate-400" size={18}/><input value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="חפש מוצר או מק״ט…" className="w-full rounded-xl border border-slate-200 bg-white py-3 pr-10 pl-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900" /></label>
          <select value={selectedId ?? ""} onChange={(e)=>setSelectedId(e.target.value ? Number(e.target.value) : null)} className="rounded-xl border border-slate-200 bg-white px-3 py-3 dark:border-slate-700 dark:bg-slate-900"><option value="">בחר מוצר…</option>{rows.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
          <button onClick={()=>selected && setQuantity(String(selected.current_stock ?? 0))} disabled={!selected} className="rounded-xl border border-slate-200 px-4 py-3 font-bold disabled:opacity-40 dark:border-slate-700">מלא את הכמות הקיימת</button>
        </div>
        {selected && <div className="mt-4 rounded-2xl bg-slate-50 p-4 dark:bg-slate-900"><div className="flex flex-wrap items-end gap-3"><div className="min-w-[180px] flex-1"><div className="text-xs text-slate-500">מלאי במערכת</div><div className="text-2xl font-black">{n(selected.current_stock)}</div></div><div className="min-w-[180px] flex-1"><label className="text-xs font-bold text-slate-600 dark:text-slate-300">כמה יש בפועל?</label><input inputMode="numeric" type="number" min="0" step="1" value={quantity} onChange={(e)=>setQuantity(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-4 py-4 text-2xl font-black outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-950" /></div><button onClick={saveCount} disabled={busy || quantity === ""} className="min-h-[56px] rounded-xl bg-indigo-600 px-6 font-black text-white shadow-lg shadow-indigo-200 disabled:opacity-50 dark:shadow-none">{busy ? "מעדכן…" : "✓ עדכן מלאי"}</button></div><input value={note} onChange={(e)=>setNote(e.target.value)} placeholder="הערה (אופציונלי)" className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950" /></div>}
        {message && <div className="mt-3 rounded-xl bg-emerald-50 p-3 text-sm font-bold text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300">{message}</div>}
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><div className="rounded-2xl border bg-white p-5 dark:border-slate-800 dark:bg-slate-950"><Package className="text-indigo-500"/><div className="mt-3 text-xs text-slate-500">מוצרים פעילים</div><div className="text-2xl font-black">{n(products.data?.length)}</div></div><div className="rounded-2xl border bg-white p-5 dark:border-slate-800 dark:bg-slate-950"><AlertTriangle className="text-amber-500"/><div className="mt-3 text-xs text-slate-500">ממתינים לנתוני ספירה</div><div className="text-2xl font-black">{n((recommendations.data?.recommendations ?? []).filter(r=>r.status === "insufficient_data").length)}</div></div><div className="rounded-2xl border bg-white p-5 dark:border-slate-800 dark:bg-slate-950"><RefreshCw className="text-emerald-500"/><div className="mt-3 text-xs text-slate-500">המלצות רכש זמינות</div><div className="text-2xl font-black">{n((recommendations.data?.recommendations ?? []).filter(r=>r.status === "urgent" || r.status === "reorder").length)}</div></div></section>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="border-b p-5 dark:border-slate-800"><h2 className="font-black">המלצות לפי המלאי הנוכחי</h2><p className="mt-1 text-xs text-slate-500">לאחר שתי ספירות ומעלה, המערכת מתחילה לחשב קצב צריכה והמלצת הזמנה.</p></div><div className="overflow-x-auto"><table className="w-full text-right text-sm"><thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-5 py-3">מוצר</th><th className="px-5 py-3">מלאי</th><th className="px-5 py-3">צריכה יומית</th><th className="px-5 py-3">נקודת הזמנה</th><th className="px-5 py-3">להזמין</th><th className="px-5 py-3">סטטוס</th></tr></thead><tbody className="divide-y dark:divide-slate-800">{(recommendations.data?.recommendations ?? []).slice(0,50).map((r: InventoryRecommendation)=><tr key={r.product_id}><td className="px-5 py-4 font-bold">{r.product_name}</td><td className="px-5 py-4">{n(r.current_stock)}</td><td className="px-5 py-4">{r.data_ready ? n(r.average_daily_usage) : "—"}</td><td className="px-5 py-4">{r.data_ready ? n(r.reorder_point) : "—"}</td><td className="px-5 py-4 font-black">{r.data_ready ? n(r.recommended_order) : "—"}</td><td className="px-5 py-4">{r.status === "urgent" ? "🔴 דחוף" : r.status === "reorder" ? "🟠 להזמין" : r.status === "healthy" ? "🟢 תקין" : "⚪ חסרה היסטוריה"}</td></tr>)}</tbody></table></div></section>
    </div>
  );
}
