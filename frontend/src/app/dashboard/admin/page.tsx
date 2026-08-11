"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ShieldCheck, UserRound, Building2, Ban, Trash2, RefreshCw } from "lucide-react";
import { adminService, AdminSupplier, AdminUser } from "@/services/admin-service";

function roleLabel(role: AdminUser["role"]) {
  return role === "admin" ? "מנהל מערכת" : role === "manager" ? "מנהל" : "עובד";
}

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [suppliers, setSuppliers] = useState<AdminSupplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [nextUsers, nextSuppliers] = await Promise.all([
        adminService.listUsers(),
        adminService.listSuppliers(),
      ]);
      setUsers(nextUsers);
      setSuppliers(nextSuppliers);
    } catch (err: any) {
      setError(err?.friendlyMessage || "אין הרשאה או שלא ניתן לטעון את נתוני הניהול.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function run(key: string, action: () => Promise<void>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      await load();
    } catch (err: any) {
      setError(err?.friendlyMessage || "הפעולה נכשלה.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div dir="rtl" className="space-y-8 pb-10">
      <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
            <ShieldCheck className="h-3.5 w-3.5" /> הרשאות מנהל מערכת
          </div>
          <h1 className="page-title">מרכז ניהול מערכת</h1>
          <p className="page-subtitle">ניהול משתמשים וספקים עם הגנות מפני מחיקה מסוכנת.</p>
        </div>
        <button onClick={() => void load()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm hover:border-indigo-200 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
          <RefreshCw className="h-4 w-4" /> רענון
        </button>
      </section>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">{error}</div>}

      <section className="grid gap-5 lg:grid-cols-2">
        <Panel title="משתמשים" icon={<UserRound className="h-5 w-5" />}>
          {loading ? <Loading /> : users.map((user) => (
            <div key={user.id} className="flex items-center justify-between gap-4 border-b border-slate-100 py-4 last:border-0 dark:border-slate-800">
              <div className="min-w-0">
                <div className="truncate font-bold text-slate-900 dark:text-white">{user.full_name}</div>
                <div className="truncate text-xs text-slate-400">{user.email} · {roleLabel(user.role)}</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${user.active ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800"}`}>
                  {user.active ? "פעיל" : "מושבת"}
                </span>
                {user.active && <button disabled={busy === `u-deactivate-${user.id}`} onClick={() => void run(`u-deactivate-${user.id}`, () => adminService.deactivateUser(user.id).then(() => undefined))} className="rounded-lg p-2 text-amber-600 hover:bg-amber-50 disabled:opacity-40 dark:hover:bg-amber-950/30" title="השבת משתמש"><Ban className="h-4 w-4" /></button>}
                {!user.active && <button disabled={busy === `u-delete-${user.id}`} onClick={() => { if (window.confirm("למחוק את המשתמש לצמיתות? פעולה זו אינה הפיכה.")) void run(`u-delete-${user.id}`, () => adminService.deleteUser(user.id)); }} className="rounded-lg p-2 text-red-600 hover:bg-red-50 disabled:opacity-40 dark:hover:bg-red-950/30" title="מחיקה לצמיתות"><Trash2 className="h-4 w-4" /></button>}
              </div>
            </div>
          ))}
        </Panel>

        <Panel title="ספקים" icon={<Building2 className="h-5 w-5" />}>
          {loading ? <Loading /> : suppliers.map((supplier) => (
            <div key={supplier.id} className="flex items-center justify-between gap-4 border-b border-slate-100 py-4 last:border-0 dark:border-slate-800">
              <div className="min-w-0"><div className="truncate font-bold text-slate-900 dark:text-white">{supplier.name}</div><div className="text-xs text-slate-400">מזהה #{supplier.id}</div></div>
              <div className="flex shrink-0 items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${supplier.active ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300" : "bg-slate-100 text-slate-500 dark:bg-slate-800"}`}>{supplier.active ? "פעיל" : "מושבת"}</span>
                {supplier.active && <button disabled={busy === `s-deactivate-${supplier.id}`} onClick={() => void run(`s-deactivate-${supplier.id}`, () => adminService.deactivateSupplier(supplier.id).then(() => undefined))} className="rounded-lg p-2 text-amber-600 hover:bg-amber-50 disabled:opacity-40 dark:hover:bg-amber-950/30" title="השבת ספק"><Ban className="h-4 w-4" /></button>}
                {!supplier.active && <button disabled={busy === `s-delete-${supplier.id}`} onClick={() => { if (window.confirm("למחוק את הספק לצמיתות? אם קיימים נתוני קטלוג, הפעולה תידחה.")) void run(`s-delete-${supplier.id}`, () => adminService.deleteSupplier(supplier.id)); }} className="rounded-lg p-2 text-red-600 hover:bg-red-50 disabled:opacity-40 dark:hover:bg-red-950/30" title="מחיקה לצמיתות"><Trash2 className="h-4 w-4" /></button>}
              </div>
            </div>
          ))}
        </Panel>
      </section>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900"><div className="mb-2 flex items-center gap-2 text-slate-950 dark:text-white"><span className="text-indigo-600">{icon}</span><h2 className="font-extrabold">{title}</h2></div>{children}</section>;
}

function Loading() {
  return <div className="space-y-3 py-5"><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /><div className="h-12 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" /></div>;
}
