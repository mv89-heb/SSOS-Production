"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ClipboardCheck, Loader2, Search, Warehouse } from "lucide-react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/services/api-client";
import { inventoryService } from "@/services/inventory-service";
import type { Product } from "@/types";

const fmt = (value: number) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 }).format(value);

export default function InventoryCountPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [quantities, setQuantities] = useState<Record<number, string>>({});
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["inventory", "summary"], queryFn: inventoryService.getSummary, staleTime: 10_000 });
  const products = data?.products ?? [];

  const rows = useMemo(() => {
    const q = search.trim().toLocaleLowerCase("he");
    return products.filter((p) => !q || [p.name, p.sku, p.barcode, p.category].filter(Boolean).some((v) => String(v).toLocaleLowerCase("he").includes(q)));
  }, [products, search]);

  const setQuantity = (product: Product, value: string) => setQuantities((current) => ({ ...current, [product.id]: value }));
  const filled = rows.filter((p) => quantities[p.id] !== undefined && quantities[p.id] !== "");

  const save = async () => {
    if (!filled.length || saving) return;
    setSaving(true);
    setMessage(null);
    try {
      const items = filled.map((p) => ({ product_id: p.id, quantity: Number(quantities[p.id]) }));
      if (items.some((item) => !Number.isInteger(item.quantity) || item.quantity < 0)) throw new Error("יש להזין כמויות שלמות שאינן שליליות.");
      const result = await apiClient.post<{ success: boolean; counted: number }>("/api/inventory/count/bulk", { items, note: note.trim() || undefined });
      setMessage("נשמרה ספירה עבור " + result.data.counted + " מוצרים. המלאי עודכן במערכת.");
      setQuantities({});
      setNote("");
      await qc.invalidateQueries({ queryKey: ["inventory"] });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "שמירת הספירה נכשלה.");
    } finally {
      setSaving(false);
    }
  };

  return <div dir="rtl" className="space-y-5 pb-12">
    <header className="rounded-3xl bg-gradient-to-l from-indigo-700 to-blue-600 p-6 text-white shadow-sm sm:p-8">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-bold text-indigo-100"><Warehouse size={18}/> מחסן ומלאי</div>
          <h1 className="mt-2 text-3xl font-black sm:text-4xl">דיווח ספירת מלאי</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-indigo-100">מסך ייעודי לספירה פיזית. מזינים רק את מה שבאמת נספר; בעת השמירה הכמות הופכת ליתרת המלאי החדשה.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => router.push("/dashboard/inventory")} className="min-h-12 rounded-xl bg-white/10 px-5 font-black ring-1 ring-white/20">חזרה למחסן</button>
          <div className="rounded-xl bg-white px-5 py-3 text-center text-indigo-700"><div className="text-xs font-bold">מוצרים להזנה</div><div className="text-2xl font-black">{filled.length}</div></div>
        </div>
      </div>
    </header>

    {message && <div className="flex items-center gap-2 rounded-2xl bg-emerald-50 p-4 text-sm font-black text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300"><CheckCircle2 size={18}/>{message}</div>}

    <section className="sticky top-2 z-20 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
      <div className="flex flex-col gap-3 lg:flex-row">
        <label className="relative flex-1"><Search className="absolute right-3 top-3.5 text-slate-400" size={18}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="חפש מוצר, מק״ט, ברקוד או קטגוריה..." className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pr-10 pl-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900"/></label>
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="הערה לספירה (אופציונלי)" className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900 lg:w-72"/>
        <button disabled={!filled.length || saving} onClick={save} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-indigo-600 px-6 font-black text-white disabled:opacity-50">{saving ? <Loader2 className="animate-spin" size={18}/> : <ClipboardCheck size={18}/>} {saving ? "שומר..." : "עדכן " + filled.length + " מוצרים"}</button>
      </div>
    </section>

    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="border-b border-slate-200 p-5 dark:border-slate-800"><h2 className="text-xl font-black">רשימת ספירה</h2><p className="mt-1 text-xs text-slate-500">מוצגים {rows.length} מוצרים. שדה ריק משאיר את המוצר ללא שינוי.</p></div>
      {isLoading ? <div className="p-10 text-center text-sm text-slate-500">טוען קטלוג...</div> : <div className="overflow-x-auto">
        <table className="w-full text-right text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr><th className="px-4 py-3">מוצר</th><th className="px-4 py-3">מק״ט</th><th className="px-4 py-3">מלאי במערכת</th><th className="w-48 px-4 py-3">כמות שנספרה</th><th className="px-4 py-3">שינוי</th></tr></thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {rows.map((product) => {
              const raw = quantities[product.id];
              const next = raw === undefined || raw === "" ? null : Number(raw);
              const delta = next === null ? null : next - Number(product.current_stock ?? 0);
              return <tr key={product.id} className={raw !== undefined && raw !== "" ? "bg-indigo-50/50 dark:bg-indigo-950/20" : ""}>
                <td className="px-4 py-3 font-black">{product.name}<span className="mt-0.5 block text-xs font-normal text-slate-400">{product.category || ""}</span></td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{product.sku || "—"}</td>
                <td className="px-4 py-3 font-black">{fmt(Number(product.current_stock ?? 0))} <span className="text-xs font-normal text-slate-400">{product.unit === "יחידה" ? "יחידות" : "ארגזים"}</span></td>
                <td className="px-4 py-3"><input inputMode="numeric" type="number" min="0" step="1" value={raw ?? ""} onChange={(e) => setQuantity(product, e.target.value)} placeholder={String(product.current_stock ?? 0)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-lg font-black outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-900"/></td>
                <td className={"px-4 py-3 font-black " + (delta === null ? "text-slate-300" : delta > 0 ? "text-emerald-600" : delta < 0 ? "text-red-600" : "text-slate-400")}>{delta === null ? "—" : (delta > 0 ? "+" : "") + fmt(delta)}</td>
              </tr>;
            })}
          </tbody>
        </table>
        {!rows.length && <div className="p-10 text-center text-sm text-slate-500">לא נמצאו מוצרים.</div>}
      </div>}
    </section>
  </div>;
}
