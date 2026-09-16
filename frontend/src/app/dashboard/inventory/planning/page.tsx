"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Plus, Save, Trash2 } from "lucide-react";
import { inventoryService, type InventoryPlanningPeriod } from "@/services/inventory-service";
import { apiClient } from "@/services/api-client";

const emptyForm = { name: "", start_date: "", end_date: "", consumption_multiplier: "1.25", order_days: "", delivery_days: "", order_cutoff_time: "", notes: "" };

export default function InventoryPlanningPage() {
  const qc = useQueryClient();
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const periods = useQuery({ queryKey: ["inventory", "planning-periods"], queryFn: inventoryService.getPlanningPeriods });

  const reset = () => { setEditingId(null); setForm(emptyForm); };
  const edit = (period: InventoryPlanningPeriod) => setForm({ name: period.name, start_date: period.start_date, end_date: period.end_date, consumption_multiplier: String(period.consumption_multiplier), order_days: period.order_days || "", delivery_days: period.delivery_days || "", order_cutoff_time: period.order_cutoff_time || "", notes: period.notes || "" });
  const save = async () => {
    if (!form.name || !form.start_date || !form.end_date) return setMessage("יש למלא שם ותאריכים.");
    try {
      if (editingId) await apiClient.put(`/api/inventory/planning/periods/${editingId}`, { ...form, consumption_multiplier: Number(form.consumption_multiplier) });
      else await apiClient.post("/api/inventory/planning/periods", { ...form, consumption_multiplier: Number(form.consumption_multiplier) });
      setMessage("התקופה נשמרה."); reset(); await qc.invalidateQueries({ queryKey: ["inventory", "planning-periods"] }); await qc.invalidateQueries({ queryKey: ["inventory", "recommendations"] });
    } catch (error) { setMessage(error instanceof Error ? error.message : "שמירת התקופה נכשלה."); }
  };
  const remove = async (id: number) => {
    if (!window.confirm("למחוק את התקופה?")) return;
    try { await apiClient.delete(`/api/inventory/planning/periods/${id}`); setMessage("התקופה נמחקה."); await qc.invalidateQueries({ queryKey: ["inventory", "planning-periods"] }); await qc.invalidateQueries({ queryKey: ["inventory", "recommendations"] }); } catch (error) { setMessage(error instanceof Error ? error.message : "מחיקת התקופה נכשלה."); }
  };

  return <div dir="rtl" className="mx-auto max-w-5xl space-y-5 pb-12">
    <header className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <a href="/dashboard/inventory" className="inline-flex items-center gap-2 text-sm font-bold text-indigo-600"><ArrowRight size={17}/> חזרה למלאי</a>
      <div className="mt-4 flex items-center gap-3"><CalendarDays className="text-indigo-600"/><div><h1 className="text-3xl font-black">תקופות מיוחדות ותכנון חגים</h1><p className="mt-1 text-sm text-slate-500">הגדר מכפיל צריכה ואת ימי ההזמנה/אספקה כאשר החג משנה את ההתנהלות הרגילה.</p></div></div>
    </header>
    {message && <div className="rounded-2xl bg-indigo-50 p-4 text-sm font-black text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">{message}</div>}
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center justify-between"><h2 className="text-xl font-black">{editingId ? "עריכת תקופה" : "הוספת תקופה"}</h2>{editingId ? <button onClick={reset} className="text-sm font-bold text-slate-500">ביטול</button> : null}</div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <input value={form.name} onChange={(e)=>setForm({...form,name:e.target.value})} placeholder="שם התקופה, למשל פסח" className="rounded-xl border p-3 dark:border-slate-700 dark:bg-slate-900"/>
        <input value={form.consumption_multiplier} onChange={(e)=>setForm({...form,consumption_multiplier:e.target.value})} type="number" min="0.01" max="10" step="0.05" placeholder="מכפיל צריכה" className="rounded-xl border p-3 dark:border-slate-700 dark:bg-slate-900"/>
        <label className="text-xs font-bold text-slate-500">מתאריך<input value={form.start_date} onChange={(e)=>setForm({...form,start_date:e.target.value})} type="date" className="mt-1 w-full rounded-xl border p-3 text-sm dark:border-slate-700 dark:bg-slate-900"/></label>
        <label className="text-xs font-bold text-slate-500">עד תאריך<input value={form.end_date} onChange={(e)=>setForm({...form,end_date:e.target.value})} type="date" className="mt-1 w-full rounded-xl border p-3 text-sm dark:border-slate-700 dark:bg-slate-900"/></label>
        <input value={form.order_days} onChange={(e)=>setForm({...form,order_days:e.target.value})} placeholder="ימי הזמנה בחג: ראשון,שלישי" className="rounded-xl border p-3 dark:border-slate-700 dark:bg-slate-900"/>
        <input value={form.delivery_days} onChange={(e)=>setForm({...form,delivery_days:e.target.value})} placeholder="ימי אספקה בחג: שני,רביעי" className="rounded-xl border p-3 dark:border-slate-700 dark:bg-slate-900"/>
        <input value={form.order_cutoff_time} onChange={(e)=>setForm({...form,order_cutoff_time:e.target.value})} placeholder="שעת חיתוך להזמנה, למשל 12:00" className="rounded-xl border p-3 dark:border-slate-700 dark:bg-slate-900"/>
        <textarea value={form.notes} onChange={(e)=>setForm({...form,notes:e.target.value})} placeholder="הערות" className="min-h-24 rounded-xl border p-3 dark:border-slate-700 dark:bg-slate-900"/>
      </div>
      <button onClick={save} className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-xl bg-indigo-600 px-5 text-sm font-black text-white"><Save size={17}/> שמור תקופה</button>
    </section>
    <section className="space-y-3">{(periods.data ?? []).map((period) => <article key={period.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-black">{period.name}</h3><span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-black text-amber-700">×{period.consumption_multiplier}</span></div><div className="mt-1 text-sm text-slate-500">{period.start_date} – {period.end_date}</div><div className="mt-2 text-xs text-slate-500">הזמנה: {period.order_days || "לפי הספק"} · אספקה: {period.delivery_days || "לפי הספק"}{period.order_cutoff_time ? ` · חיתוך: ${period.order_cutoff_time}` : ""}</div></div><div className="flex gap-2"><button onClick={()=>{setEditingId(period.id);edit(period);window.scrollTo({top:0,behavior:"smooth"});}} className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-black text-slate-700">ערוך</button><button onClick={()=>remove(period.id)} className="rounded-xl bg-red-50 p-2 text-red-700"><Trash2 size={18}/></button></div></div></article>)}{!periods.isLoading && !(periods.data ?? []).length && <div className="rounded-2xl border border-dashed p-10 text-center text-sm text-slate-500">אין עדיין תקופות מיוחדות. אפשר להוסיף או לחזור למסך המלאי וללחוץ „הוסף תקופות חגים”.</div>}</section>
  </div>;
}
