"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ShieldCheck, UserRound, Building2, Package, ShoppingBag, FileUp, Ban, Trash2, RefreshCw, Pencil, Check, X } from "lucide-react";
import { adminService, AdminImport, AdminOrder, AdminProduct, AdminSupplier, AdminUser } from "@/services/admin-service";

function roleLabel(role: AdminUser["role"]) { return role === "admin" ? "מנהל מערכת" : role === "manager" ? "מנהל" : "עובד"; }

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [suppliers, setSuppliers] = useState<AdminSupplier[]>([]);
  const [products, setProducts] = useState<AdminProduct[]>([]);
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [imports, setImports] = useState<AdminImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [editUser, setEditUser] = useState<AdminUser | null>(null);
  const [editSupplier, setEditSupplier] = useState<AdminSupplier | null>(null);
  const [userForm, setUserForm] = useState({ full_name: "", email: "", role: "employee" as AdminUser["role"] });
  const [supplierForm, setSupplierForm] = useState({ name: "" });

  async function load() {
    setLoading(true); setError(null);
    try {
      const [u, s, p, o, i] = await Promise.all([
        adminService.listUsers(), adminService.listSuppliers(), adminService.listProducts(), adminService.listOrders(), adminService.listImports(),
      ]);
      setUsers(u); setSuppliers(s); setProducts(p); setOrders(o); setImports(i);
    } catch (err: any) { setError(err?.friendlyMessage || "אין הרשאה או שלא ניתן לטעון את נתוני הניהול."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key); setError(null);
    try { await action(); await load(); } catch (err: any) { setError(err?.friendlyMessage || "הפעולה נכשלה."); }
    finally { setBusy(null); }
  }
  const confirmRun = (message: string, key: string, action: () => Promise<void>) => { if (window.confirm(message)) void run(key, action); };

  return (
    <div dir="rtl" className="space-y-7 pb-10">
      <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div><div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"><ShieldCheck className="h-3.5 w-3.5" /> הרשאות מנהל מערכת</div><h1 className="page-title">מרכז ניהול מערכת</h1><p className="page-subtitle">עריכה, הפעלה, השבתה ומחיקה מבוקרת של נתוני המערכת.</p></div>
        <button onClick={() => void load()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm hover:border-indigo-200 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"><RefreshCw className="h-4 w-4" /> רענון</button>
      </section>
      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">{error}</div>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="משתמשים" value={users.length} icon={UserRound} /><Metric label="ספקים" value={suppliers.length} icon={Building2} /><Metric label="מוצרים" value={products.length} icon={Package} /><Metric label="הזמנות" value={orders.length} icon={ShoppingBag} /><Metric label="ייבואים" value={imports.length} icon={FileUp} />
      </div>

      <section className="grid gap-5 lg:grid-cols-2">
        <Panel title="משתמשים" icon={<UserRound className="h-5 w-5" />}>
          {loading ? <Loading /> : users.map((user) => <Row key={user.id} title={user.full_name} subtitle={`${user.email} · ${roleLabel(user.role)}`} active={user.active}>
            <button onClick={() => { setEditUser(user); setUserForm({ full_name: user.full_name, email: user.email, role: user.role }); }} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="עריכה"><Pencil className="h-4 w-4" /></button>
            {user.active ? <button disabled={busy === `ud${user.id}`} onClick={() => void run(`ud${user.id}`, () => adminService.deactivateUser(user.id).then(() => undefined))} className="rounded-lg p-2 text-amber-600 hover:bg-amber-50 disabled:opacity-40" title="השבת"><Ban className="h-4 w-4" /></button> : <><button disabled={busy === `ua${user.id}`} onClick={() => void run(`ua${user.id}`, () => adminService.activateUser(user.id).then(() => undefined))} className="rounded-lg p-2 text-emerald-600 hover:bg-emerald-50 disabled:opacity-40" title="הפעל"><Check className="h-4 w-4" /></button><button disabled={busy === `ux${user.id}`} onClick={() => confirmRun("למחוק את המשתמש לצמיתות? לא ניתן לשחזר פעולה זו.", `ux${user.id}`, () => adminService.deleteUser(user.id))} className="rounded-lg p-2 text-red-600 hover:bg-red-50 disabled:opacity-40" title="מחיקה"><Trash2 className="h-4 w-4" /></button></>}
          </Row>)}
        </Panel>

        <Panel title="ספקים" icon={<Building2 className="h-5 w-5" />}>
          {loading ? <Loading /> : suppliers.map((supplier) => <Row key={supplier.id} title={supplier.name} subtitle={`מזהה #${supplier.id}`} active={supplier.active}>
            <button onClick={() => { setEditSupplier(supplier); setSupplierForm({ name: supplier.name }); }} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="עריכה"><Pencil className="h-4 w-4" /></button>
            {supplier.active ? <button onClick={() => void run(`sd${supplier.id}`, () => adminService.deactivateSupplier(supplier.id).then(() => undefined))} className="rounded-lg p-2 text-amber-600 hover:bg-amber-50" title="השבת"><Ban className="h-4 w-4" /></button> : <><button onClick={() => void run(`sa${supplier.id}`, () => adminService.activateSupplier(supplier.id).then(() => undefined))} className="rounded-lg p-2 text-emerald-600 hover:bg-emerald-50" title="הפעל"><Check className="h-4 w-4" /></button><button onClick={() => confirmRun("למחוק את הספק לצמיתות? אם קיימות תלות או היסטוריה, השרת ידחה את הפעולה.", `sx${supplier.id}`, () => adminService.deleteSupplier(supplier.id))} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="מחיקה"><Trash2 className="h-4 w-4" /></button></>}
          </Row>)}
        </Panel>

        <Panel title="מוצרים" icon={<Package className="h-5 w-5" />}>
          {loading ? <Loading /> : products.map((product) => <Row key={product.id} title={product.name} subtitle={`${product.sku || "ללא מק״ט"} · ${product.current_price} · ספק #${product.supplier_id}`} active={product.active}>
            {!product.active && <button onClick={() => confirmRun("למחוק את המוצר לצמיתות? יש להסיר הצעות ספק תלויות לפני המחיקה.", `px${product.id}`, () => adminService.deleteProduct(product.id))} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="מחיקה"><Trash2 className="h-4 w-4" /></button>}
          </Row>)}
        </Panel>

        <Panel title="הזמנות" icon={<ShoppingBag className="h-5 w-5" />}>
          {loading ? <Loading /> : orders.map((order) => <Row key={order.id} title={order.order_number} subtitle={`${order.status} · ${order.final_total}`} active={order.status !== "cancelled"}>
            {order.status === "draft" && <button onClick={() => confirmRun("למחוק את טיוטת ההזמנה?", `ox${order.id}`, () => adminService.deleteOrder(order.id))} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="מחיקת טיוטה"><Trash2 className="h-4 w-4" /></button>}
          </Row>)}
        </Panel>
      </section>

      <Panel title="ייבואים" icon={<FileUp className="h-5 w-5" />}>
        {loading ? <Loading /> : imports.map((item) => <Row key={item.id} title={item.filename} subtitle={`#${item.id} · ${item.status} · ${item.row_count ?? 0} שורות`} active={item.status !== "FAILED"}>
          {item.status === "FAILED" && <button onClick={() => confirmRun("למחוק את הייבוא הכושל ואת קובץ המקור?", `ix${item.id}`, () => adminService.deleteImport(item.id))} className="rounded-lg p-2 text-red-600 hover:bg-red-50" title="מחיקת ייבוא"><Trash2 className="h-4 w-4" /></button>}
        </Row>)}
      </Panel>

      {editUser && <Modal title="עריכת משתמש" onClose={() => setEditUser(null)}><label>שם מלא<input value={userForm.full_name} onChange={e => setUserForm(f => ({ ...f, full_name: e.target.value }))} /></label><label>אימייל<input value={userForm.email} onChange={e => setUserForm(f => ({ ...f, email: e.target.value }))} /></label><label>תפקיד<select value={userForm.role} onChange={e => setUserForm(f => ({ ...f, role: e.target.value as AdminUser["role"] }))}><option value="employee">עובד</option><option value="manager">מנהל</option><option value="admin">מנהל מערכת</option></select></label><ModalActions onCancel={() => setEditUser(null)} onSave={() => void run(`ue${editUser.id}`, async () => { await adminService.updateUser(editUser.id, userForm); setEditUser(null); })} /></Modal>}
      {editSupplier && <Modal title="עריכת ספק" onClose={() => setEditSupplier(null)}><label>שם ספק<input value={supplierForm.name} onChange={e => setSupplierForm({ name: e.target.value })} /></label><ModalActions onCancel={() => setEditSupplier(null)} onSave={() => void run(`se${editSupplier.id}`, async () => { await adminService.updateSupplier(editSupplier.id, supplierForm); setEditSupplier(null); })} /></Modal>}
    </div>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: any }) { return <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"><Icon className="h-4 w-4 text-indigo-600" /><div className="mt-2 text-2xl font-black">{value}</div><div className="text-xs text-slate-400">{label}</div></div>; }
function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) { return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900"><div className="mb-2 flex items-center gap-2 text-slate-950 dark:text-white"><span className="text-indigo-600">{icon}</span><h2 className="font-extrabold">{title}</h2></div>{children}</section>; }
function Row({ title, subtitle, active, children }: { title: string; subtitle: string; active: boolean; children: ReactNode }) { return <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-3.5 last:border-0 dark:border-slate-800"><div className="min-w-0"><div className="truncate font-bold text-slate-900 dark:text-white">{title}</div><div className="truncate text-xs text-slate-400">{subtitle}</div></div><div className="flex shrink-0 items-center gap-1"><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{active ? "פעיל" : "מושבת"}</span>{children}</div></div>; }
function Loading() { return <div className="space-y-3 py-5"><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /></div>; }
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) { return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"><div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900"><div className="mb-5 flex items-center justify-between"><h3 className="text-lg font-black">{title}</h3><button onClick={onClose}><X className="h-5 w-5" /></button></div><div className="space-y-4">{children}</div></div></div>; }
function ModalActions({ onCancel, onSave }: { onCancel: () => void; onSave: () => void }) { return <div className="flex justify-end gap-2 pt-2"><button onClick={onCancel} className="rounded-xl border px-4 py-2 text-sm font-bold">ביטול</button><button onClick={onSave} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-bold text-white">שמירה</button></div>; }
