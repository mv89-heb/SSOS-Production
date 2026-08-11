"use client";

import { useEffect, useState } from "react";
import { Ban, Check, Package, RefreshCw, ShieldCheck, ShoppingBag, Trash2, UserRound, Building2, FileUp } from "lucide-react";
import { adminService, AdminImport, AdminOrder, AdminProduct, AdminSupplier, AdminUser } from "@/services/admin-service";

const roleLabel = (r: AdminUser["role"]) => r === "admin" ? "מנהל מערכת" : r === "manager" ? "מנהל" : "עובד";

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]), [suppliers, setSuppliers] = useState<AdminSupplier[]>([]), [products, setProducts] = useState<AdminProduct[]>([]), [orders, setOrders] = useState<AdminOrder[]>([]), [imports, setImports] = useState<AdminImport[]>([]);
  const [loading, setLoading] = useState(true), [error, setError] = useState<string | null>(null), [busy, setBusy] = useState<string | null>(null);

  async function load() {
    setLoading(true); setError(null);
    try {
      const [u, s, p, o, i] = await Promise.all([adminService.listUsers(), adminService.listSuppliers(), adminService.listProducts(), adminService.listOrders(), adminService.listImports()]);
      setUsers(u); setSuppliers(s); setProducts(p); setOrders(o); setImports(i);
    } catch (e: any) { setError(e?.friendlyMessage || e?.response?.data?.message || "לא ניתן לטעון את נתוני הניהול."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function action(key: string, fn: () => Promise<void>, confirmation: string) {
    if (!window.confirm(confirmation)) return;
    setBusy(key); setError(null);
    try { await fn(); await load(); } catch (e: any) { setError(e?.friendlyMessage || e?.response?.data?.message || "הפעולה נכשלה."); }
    finally { setBusy(null); }
  }

  return <div dir="rtl" className="space-y-7 pb-10">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"><ShieldCheck size={14}/> מנהל מערכת</div><h1 className="text-3xl font-black text-slate-950 dark:text-white">מרכז ניהול</h1><p className="mt-1 text-sm text-slate-500">כאן נמצאות פעולות העריכה, ההפעלה, ההשבתה והמחיקה של המערכת.</p></div>
      <button onClick={() => void load()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold dark:border-slate-700 dark:bg-slate-900"><RefreshCw size={16}/> רענון</button>
    </header>
    {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">{error}</div>}
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5"><Metric icon={UserRound} label="משתמשים" value={users.length}/><Metric icon={Building2} label="ספקים" value={suppliers.length}/><Metric icon={Package} label="מוצרים" value={products.length}/><Metric icon={ShoppingBag} label="הזמנות" value={orders.length}/><Metric icon={FileUp} label="ייבואים" value={imports.length}/></div>

    <Panel title="משתמשים" icon={UserRound} loading={loading}>
      {users.map(u => <Row key={u.id} title={u.full_name} sub={`${u.email} · ${roleLabel(u.role)}`}><Status active={u.active}/>{u.active ? <IconButton title="השבת" icon={Ban} tone="amber" disabled={busy === `uoff${u.id}`} onClick={() => void action(`uoff${u.id}`, () => adminService.deactivateUser(u.id).then(() => undefined), "להשבית את המשתמש?")}/> : <><IconButton title="הפעל" icon={Check} tone="green" onClick={() => void action(`uon${u.id}`, () => adminService.activateUser(u.id).then(() => undefined), "להפעיל את המשתמש?")}/><IconButton title="מחיקה לצמיתות" icon={Trash2} tone="red" onClick={() => void action(`udel${u.id}`, () => adminService.deleteUser(u.id), "למחוק את המשתמש לצמיתות? לא ניתן לשחזר פעולה זו.")}/></>}</Row>)}
    </Panel>

    <Panel title="ספקים" icon={Building2} loading={loading}>
      {suppliers.map(s => <Row key={s.id} title={s.name} sub={`מזהה #${s.id}`}><Status active={s.active}/>{s.active ? <IconButton title="השבת" icon={Ban} tone="amber" onClick={() => void action(`soff${s.id}`, () => adminService.deactivateSupplier(s.id).then(() => undefined), "להשבית את הספק?")}/> : <><IconButton title="הפעל" icon={Check} tone="green" onClick={() => void action(`son${s.id}`, () => adminService.activateSupplier(s.id).then(() => undefined), "להפעיל את הספק?")}/><IconButton title="מחיקה לצמיתות" icon={Trash2} tone="red" onClick={() => void action(`sdel${s.id}`, () => adminService.deleteSupplier(s.id), "למחוק את הספק לצמיתות? אם קיימים נתונים תלויים, המחיקה תיחסם.")}/></>}</Row>)}
    </Panel>

    <Panel title="מוצרים" icon={Package} loading={loading}>
      {products.map(p => <Row key={p.id} title={p.name} sub={`${p.sku || "ללא מק״ט"} · ${p.current_price} · ספק #${p.supplier_id}`}><Status active={p.active}/><IconButton title="מחיקה לצמיתות" icon={Trash2} tone="red" onClick={() => void action(`pdel${p.id}`, () => adminService.deleteProduct(p.id), `למחוק את המוצר "${p.name}" לצמיתות? הצעות ספק ימחקו יחד איתו.`)}/></Row>)}
    </Panel>

    <Panel title="הזמנות" icon={ShoppingBag} loading={loading}>
      {orders.map(o => <Row key={o.id} title={o.order_number} sub={`${o.status} · ${o.final_total}`}><Status active={o.status !== "cancelled"}/><IconButton title="מחיקה לצמיתות" icon={Trash2} tone="red" onClick={() => void action(`odel${o.id}`, () => adminService.deleteOrder(o.id), `למחוק את ההזמנה ${o.order_number} לצמיתות? פעולה זו תסיר את ההזמנה אך תשאיר Audit Log.`)}/></Row>)}
    </Panel>

    <Panel title="ייבואים" icon={FileUp} loading={loading}>
      {imports.map(i => <Row key={i.id} title={i.filename} sub={`#${i.id} · ${i.status} · ${i.row_count ?? 0} שורות`}><Status active={i.status !== "FAILED"}/>{i.status === "FAILED" && <IconButton title="מחיקה לצמיתות" icon={Trash2} tone="red" onClick={() => void action(`idel${i.id}`, () => adminService.deleteImport(i.id), "למחוק את הייבוא הכושל ואת קובץ המקור?")}/>}</Row>)}
    </Panel>
  </div>;
}

function Metric({ icon: Icon, label, value }: { icon: any; label: string; value: number }) { return <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><Icon size={17} className="text-indigo-600"/><div className="mt-2 text-2xl font-black">{value}</div><div className="text-xs font-semibold text-slate-400">{label}</div></div>; }
function Panel({ title, icon: Icon, children, loading }: { title: string; icon: any; children: React.ReactNode; loading: boolean }) { return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"><h2 className="mb-2 flex items-center gap-2 font-black"><Icon size={18} className="text-indigo-600"/>{title}</h2>{loading ? <div className="space-y-2 py-4"><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800"/><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800"/></div> : children}</section>; }
function Row({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) { return <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-3.5 last:border-0 dark:border-slate-800"><div className="min-w-0"><div className="truncate font-bold text-slate-900 dark:text-white">{title}</div><div className="truncate text-xs text-slate-400">{sub}</div></div><div className="flex shrink-0 items-center gap-1">{children}</div></div>; }
function Status({ active }: { active: boolean }) { return <span className={`rounded-full px-2 py-1 text-[10px] font-bold ${active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{active ? "פעיל" : "מושבת"}</span>; }
function IconButton({ title, icon: Icon, tone, onClick, disabled }: { title: string; icon: any; tone: "red" | "amber" | "green"; onClick: () => void; disabled?: boolean }) { const cls = tone === "red" ? "text-red-600 hover:bg-red-50" : tone === "amber" ? "text-amber-600 hover:bg-amber-50" : "text-emerald-600 hover:bg-emerald-50"; return <button type="button" title={title} aria-label={title} disabled={disabled} onClick={onClick} className={`rounded-lg p-2 ${cls} disabled:opacity-40`}><Icon size={17}/></button>; }
