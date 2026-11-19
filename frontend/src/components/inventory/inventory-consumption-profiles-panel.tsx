"use client";

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Link2, Plus, Save, X } from "lucide-react";
import { inventoryService, type InventoryConsumptionProfile } from "@/services/inventory-service";

type ProfileForm = {
  name: string; category: string; supplier_ids: number[]; product_ids: number[];
  min_order_quantity: string; max_order_quantity: string; average_order_quantity: string;
  regular_weekly_consumption: string; reinforced_weekly_consumption: string;
  reinforcement_cycle_weeks: string; safety_stock: string; order_status: "healthy" | "reorder";
};
const blankForm: ProfileForm = {
  name: "", category: "", supplier_ids: [], product_ids: [], min_order_quantity: "1",
  max_order_quantity: "1", average_order_quantity: "1", regular_weekly_consumption: "0",
  reinforced_weekly_consumption: "0", reinforcement_cycle_weeks: "3", safety_stock: "0",
  order_status: "healthy",
};
const fromProfile = (p: InventoryConsumptionProfile): ProfileForm => ({
  name: p.name, category: p.category, supplier_ids: p.supplier_ids, product_ids: p.product_ids,
  min_order_quantity: String(p.min_order_quantity), max_order_quantity: String(p.max_order_quantity),
  average_order_quantity: String(p.average_order_quantity), regular_weekly_consumption: String(p.regular_weekly_consumption),
  reinforced_weekly_consumption: String(p.reinforced_weekly_consumption),
  reinforcement_cycle_weeks: String(p.reinforcement_cycle_weeks), safety_stock: String(p.safety_stock),
  order_status: p.order_status,
});
const number = (v: string) => Number(v || 0);
const qty = (v: number) => new Intl.NumberFormat("he-IL", { maximumFractionDigits: 3 }).format(v);

export default function InventoryConsumptionProfilesPanel() {
  const qc = useQueryClient();
  const profiles = useQuery({ queryKey: ["inventory", "consumption-profiles"], queryFn: inventoryService.getConsumptionProfiles });
  const options = useQuery({ queryKey: ["inventory", "consumption-profile-options"], queryFn: inventoryService.getConsumptionProfileOptions });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProfileForm>(blankForm);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const availableProducts = useMemo(() => (options.data?.products ?? []).filter(p => form.supplier_ids.includes(p.supplier_id)), [options.data, form.supplier_ids]);
  const weighted = form.reinforcement_cycle_weeks && number(form.reinforcement_cycle_weeks) >= 1
    ? (number(form.regular_weekly_consumption) * (number(form.reinforcement_cycle_weeks) - 1) + number(form.reinforced_weekly_consumption)) / number(form.reinforcement_cycle_weeks)
    : 0;

  const reset = () => { setEditingId(null); setForm(blankForm); };
  const save = async () => {
    if (!form.name.trim() || !form.category.trim()) { setMessage("יש למלא שם מוצר וקטגוריה."); return; }
    if (form.max_order_quantity !== "" && number(form.max_order_quantity) < number(form.min_order_quantity)) { setMessage("הכמות המרבית חייבת להיות גדולה או שווה לכמות המינימלית."); return; }
    if (number(form.reinforcement_cycle_weeks) < 1) { setMessage("מחזור התגבור חייב להיות שבוע אחד לפחות."); return; }
    setBusy(true); setMessage(null);
    const payload = {
      ...form,
      min_order_quantity: number(form.min_order_quantity), max_order_quantity: number(form.max_order_quantity),
      average_order_quantity: number(form.average_order_quantity), regular_weekly_consumption: number(form.regular_weekly_consumption),
      reinforced_weekly_consumption: number(form.reinforced_weekly_consumption),
      reinforcement_cycle_weeks: number(form.reinforcement_cycle_weeks), safety_stock: number(form.safety_stock),
    };
    try {
      if (editingId) await inventoryService.updateConsumptionProfile(editingId, payload);
      else await inventoryService.createConsumptionProfile(payload);
      setMessage(editingId ? "פרופיל הצריכה עודכן." : "פרופיל הצריכה נוסף.");
      reset();
      await qc.invalidateQueries({ queryKey: ["inventory", "consumption-profiles"] });
    } catch (error) { setMessage(error instanceof Error ? error.message : "שמירת פרופיל הצריכה נכשלה."); }
    finally { setBusy(false); }
  };
  const archive = async (p: InventoryConsumptionProfile) => {
    if (!window.confirm(`להעביר את "${p.name}" לארכיון? נתוני התכנון לא יימחקו מהיסטוריית המערכת.`)) return;
    try { await inventoryService.archiveConsumptionProfile(p.id); setMessage("הפרופיל הועבר לארכיון."); await qc.invalidateQueries({ queryKey: ["inventory", "consumption-profiles"] }); }
    catch (error) { setMessage(error instanceof Error ? error.message : "העברת הפרופיל לארכיון נכשלה."); }
  };
  const inputClass = "w-full rounded-xl border border-slate-200 bg-white p-2.5 text-sm dark:border-slate-700 dark:bg-slate-900";
  const labelClass = "grid gap-1 text-xs font-bold text-slate-600 dark:text-slate-300";

  return <section dir="rtl" className="space-y-4 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950 sm:p-5">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-xl font-black">מעקב צריכה ותגבור שבתות</h2><p className="mt-1 text-sm text-slate-500">פרופילי תכנון עצמאיים לחד־פעמי, נייר, ניקיון וציוד. ניתן להוסיף מוצרים ולקשר אותם לקטלוג בהמשך.</p></div>
      <button onClick={reset} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-black text-white"><Plus size={16}/> מוצר לתכנון</button>
    </header>
    {message && <div role="status" className="rounded-xl bg-indigo-50 p-3 text-sm font-bold text-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-200">{message}</div>}
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">פרופילים פעילים</div><div className="text-2xl font-black">{profiles.data?.length ?? 0}</div></div>
      <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">ממתינים לשיוך לקטלוג</div><div className="text-2xl font-black">{profiles.data?.filter(p => p.mapping_status === "pending").length ?? 0}</div></div>
      <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">מחזור תגבור</div><div className="text-2xl font-black">כל 3 שבועות</div></div>
      <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-900"><div className="text-xs text-slate-500">המרת חודש תכנון</div><div className="text-2xl font-black">4 שבועות</div></div>
    </div>

    {(editingId !== null || form.name !== "") && <div className="space-y-3 rounded-2xl border border-indigo-200 bg-indigo-50/50 p-4 dark:border-indigo-900 dark:bg-indigo-950/20">
      <div className="flex items-center justify-between"><h3 className="font-black">{editingId ? "עריכת פרופיל צריכה" : "הוספת פרופיל צריכה"}</h3><button onClick={reset} aria-label="סגירה" className="rounded-lg p-2"><X size={17}/></button></div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label className={labelClass}>שם מוצר / קבוצת מוצרים<input className={inputClass} value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="למשל: מגשי אלומיניום"/></label>
        <label className={labelClass}>קטגוריה<input className={inputClass} value={form.category} onChange={e=>setForm({...form,category:e.target.value})} placeholder="חד״פ / ניקיון / ציוד"/></label>
        <label className={labelClass}>ספקים אפשריים<select multiple className={inputClass+" min-h-24"} value={form.supplier_ids.map(String)} onChange={e=>{const ids=Array.from(e.target.selectedOptions,o=>Number(o.value));setForm({...form,supplier_ids:ids,product_ids:form.product_ids.filter(id=>(options.data?.products??[]).some(p=>p.id===id&&ids.includes(p.supplier_id)))});}}>{(options.data?.suppliers??[]).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><span className="font-normal text-slate-500">אפשר לבחור כמה ספקים באמצעות Ctrl.</span></label>
        <label className={labelClass}>מוצרים מקושרים בקטלוג<select multiple className={inputClass+" min-h-24"} value={form.product_ids.map(String)} onChange={e=>setForm({...form,product_ids:Array.from(e.target.selectedOptions,o=>Number(o.value))})}>{availableProducts.map(p=><option key={p.id} value={p.id}>{p.name} · {p.unit||"יחידה"}</option>)}</select><span className="font-normal text-slate-500">מוצגים רק מוצרים של הספקים שנבחרו. אפשר להשאיר ללא שיוך.</span></label>
        <label className={labelClass}>כמות מינימלית להזמנה<input type="number" min="0" step="0.001" className={inputClass} value={form.min_order_quantity} onChange={e=>setForm({...form,min_order_quantity:e.target.value})}/></label>
        <label className={labelClass}>כמות מקסימלית להזמנה<input type="number" min="0" step="0.001" className={inputClass} value={form.max_order_quantity} onChange={e=>setForm({...form,max_order_quantity:e.target.value})}/></label>
        <label className={labelClass}>ממוצע להזמנה<input type="number" min="0" step="0.001" className={inputClass} value={form.average_order_quantity} onChange={e=>setForm({...form,average_order_quantity:e.target.value})}/></label>
        <label className={labelClass}>צריכה בשבוע רגיל<input type="number" min="0" step="0.001" className={inputClass} value={form.regular_weekly_consumption} onChange={e=>setForm({...form,regular_weekly_consumption:e.target.value})}/></label>
        <label className={labelClass}>צריכה בשבת מתוגברת<input type="number" min="0" step="0.001" className={inputClass} value={form.reinforced_weekly_consumption} onChange={e=>setForm({...form,reinforced_weekly_consumption:e.target.value})}/></label>
        <label className={labelClass}>מחזור תגבור (שבועות)<input type="number" min="1" step="1" className={inputClass} value={form.reinforcement_cycle_weeks} onChange={e=>setForm({...form,reinforcement_cycle_weeks:e.target.value})}/></label>
        <label className={labelClass}>מלאי ביטחון מומלץ<input type="number" min="0" step="0.001" className={inputClass} value={form.safety_stock} onChange={e=>setForm({...form,safety_stock:e.target.value})}/></label>
        <label className={labelClass}>סטטוס התחלתי<select className={inputClass} value={form.order_status} onChange={e=>setForm({...form,order_status:e.target.value as "healthy"|"reorder"})}><option value="healthy">תקין</option><option value="reorder">להזמנה</option></select></label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white p-3 text-sm dark:bg-slate-900"><span>צריכה שבועית משוקללת מחושבת: <strong>{qty(weighted)}</strong></span><span>חודש תכנון (4 שבועות): <strong>{qty(weighted*4)}</strong></span></div>
      <div className="flex gap-2"><button disabled={busy} onClick={save} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-black text-white disabled:opacity-50"><Save size={16}/>{busy?"שומר…":"שמור פרופיל"}</button><button onClick={reset} className="rounded-xl border px-4 text-sm font-bold dark:border-slate-700">ביטול</button></div>
    </div>}

    {profiles.isLoading ? <div className="p-8 text-center text-sm text-slate-500">טוען פרופילי צריכה…</div> : profiles.isError ? <div className="p-5 text-sm text-red-600">לא ניתן לטעון את פרופילי הצריכה.</div> : <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
      <table className="w-full min-w-[1050px] text-right text-sm">
        <thead className="bg-slate-50 text-xs text-slate-500 dark:bg-slate-900"><tr>{["מוצר","ספקים","מינ׳ / מקס׳ / ממוצע","שבוע רגיל","שבת מתוגברת","קצב שבועי","קצב חודשי","ביטחון","שיוך לקטלוג","פעולות"].map(x=><th key={x} className="whitespace-nowrap px-3 py-3 font-black">{x}</th>)}</tr></thead>
        <tbody>{(profiles.data??[]).map(p=><tr key={p.id} className="border-t border-slate-100 dark:border-slate-800">
          <td className="px-3 py-3"><div className="font-black">{p.name}</div><div className="text-xs text-slate-500">{p.category}</div></td>
          <td className="px-3 py-3 text-xs">{p.supplier_ids.map(id=>p.supplier_names[id]??id).join(" / ")||"לא הוגדר"}</td>
          <td className="px-3 py-3 tabular-nums">{qty(p.min_order_quantity)} / {qty(p.max_order_quantity)} / {qty(p.average_order_quantity)}</td>
          <td className="px-3 py-3 tabular-nums">{qty(p.regular_weekly_consumption)}</td><td className="px-3 py-3 tabular-nums">{qty(p.reinforced_weekly_consumption)}</td>
          <td className="px-3 py-3 font-black tabular-nums">{qty(p.weighted_weekly_consumption)}</td><td className="px-3 py-3 tabular-nums">{qty(p.monthly_consumption)}</td><td className="px-3 py-3 tabular-nums">{qty(p.safety_stock)}</td>
          <td className="px-3 py-3"><span className={p.mapping_status==="mapped"?"text-emerald-700":"text-amber-700"}>{p.mapping_status==="mapped"?`${p.product_ids.length} מוצרים`:"ממתין לשיוך"}</span></td>
          <td className="px-3 py-3"><div className="flex gap-1"><button onClick={()=>{setEditingId(p.id);setForm(fromProfile(p));}} title="עריכה" className="rounded-lg bg-slate-100 p-2 dark:bg-slate-800"><Link2 size={15}/></button><button onClick={()=>archive(p)} title="העברה לארכיון" className="rounded-lg bg-slate-100 p-2 text-red-600 dark:bg-slate-800"><Archive size={15}/></button></div></td>
        </tr>)}</tbody>
      </table>
      {!(profiles.data??[]).length&&<div className="p-8 text-center text-sm text-slate-500">אין עדיין פרופילי צריכה. הוסף מוצר ראשון לתכנון.</div>}
    </div>}
    <p className="text-xs leading-5 text-slate-500">הנתונים הם תכנון צריכה ולא ספירת מלאי. קישור לקטלוג אינו משנה מלאי פיזי, מחיר, ספק ברירת מחדל או היסטוריית הזמנות. פרופילים חדשים ניתן להוסיף בכל עת.</p>
  </section>;
}
