"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, Package, Pencil, Plus, Search, ShoppingCart, Users, X } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useCreateSupplier, useProducts, useSuppliers, useUpdateSupplier } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { ActiveBadge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import type { Supplier } from "@/types";

const EMPTY_FORM = { name: "", contact_name: "", email: "", phone: "", phone2: "", customer_number: "", delivery_days: "", order_days: "" };
type EditableField = keyof typeof EMPTY_FORM;

export default function SuppliersPage() {
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);
  const [search, setSearch] = useState(""); const [modalOpen, setModalOpen] = useState(false); const [form, setForm] = useState(EMPTY_FORM); const [formError, setFormError] = useState<string | null>(null); const [editing, setEditing] = useState<{ id: number; field: EditableField; value: string } | null>(null);
  const { data: suppliers, isLoading, isError, refetch } = useSuppliers(); const { data: allProducts } = useProducts(); const createSupplier = useCreateSupplier(); const updateSupplier = useUpdateSupplier(editing?.id ?? -1);
  const productCountBySupplier = useMemo(() => { const counts = new Map<number, number>(); (allProducts ?? []).forEach((product) => counts.set(product.supplier_id, (counts.get(product.supplier_id) ?? 0) + 1)); return counts; }, [allProducts]);
  const filtered = useMemo(() => { const query = search.trim().toLowerCase(); return (suppliers ?? []).filter((supplier) => !query || [supplier.name, supplier.contact_name, supplier.email, supplier.phone, supplier.customer_number, supplier.order_days, supplier.delivery_days].filter(Boolean).some((value) => String(value).toLowerCase().includes(query))); }, [suppliers, search]);
  const openCreateModal = () => { setForm({ ...EMPTY_FORM }); setFormError(null); setModalOpen(true); };
  const startEdit = (supplier: Supplier, field: EditableField) => setEditing({ id: supplier.id, field, value: String(supplier[field] ?? "") });
  const cancelEdit = () => setEditing(null);
  const saveEdit = () => { if (!editing) return; const value = editing.value.trim(); if (editing.field === "name" && !value) return; updateSupplier.mutate({ [editing.field]: value || undefined }, { onSuccess: () => setEditing(null) }); };
  const cell = (supplier: Supplier, field: EditableField, display: React.ReactNode, className = "") => { const active = editing?.id === supplier.id && editing.field === field; if (!canManage) return <span className={className}>{display}</span>; if (!active) return <button type="button" onClick={() => startEdit(supplier, field)} title="עריכה ישירה" className={`group inline-flex min-h-9 w-full items-center justify-between gap-2 rounded-lg px-2 text-right transition hover:bg-indigo-50 dark:hover:bg-indigo-950/40 ${className}`}><span className="truncate">{display}</span><Pencil className="h-3.5 w-3.5 shrink-0 text-indigo-400 opacity-0 transition group-hover:opacity-100" /></button>; return <div className="flex items-center gap-1"><Input autoFocus value={editing.value} onChange={(e) => setEditing((current) => current ? { ...current, value: e.target.value } : current)} onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") cancelEdit(); }} className="h-9 min-w-0" /><button type="button" onClick={saveEdit} disabled={updateSupplier.isPending} className="rounded-md p-1.5 text-emerald-600 hover:bg-emerald-50" aria-label="שמירת שינוי"><Check size={15} /></button><button type="button" onClick={cancelEdit} disabled={updateSupplier.isPending} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100" aria-label="ביטול שינוי"><X size={15} /></button></div>; };
  const handleSubmit = () => { setFormError(null); if (!form.name.trim()) return setFormError("שם הספק הוא שדה חובה."); createSupplier.mutate({ name: form.name.trim(), contact_name: form.contact_name.trim() || undefined, email: form.email.trim() || undefined, phone: form.phone.trim() || undefined, phone2: form.phone2.trim() || undefined, customer_number: form.customer_number.trim() || undefined, delivery_days: form.delivery_days.trim() || undefined, order_days: form.order_days.trim() || undefined }, { onSuccess: () => setModalOpen(false) }); };

  return <div className="space-y-6 pb-8" dir="rtl">
    <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between"><div><div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"><Users className="h-3.5 w-3.5" />ניהול ספקים</div><h1 className="page-title">ספקים</h1><p className="page-subtitle">לחץ על שדה בטבלה כדי לערוך אותו ישירות. Enter לשמירה, Esc לביטול.</p></div>{canManage && <Button onClick={openCreateModal}><Plus size={16} />ספק חדש</Button>}</section>
    <section className="grid grid-cols-2 gap-3 md:grid-cols-4"><SummaryCard icon={Users} label="ספקים" value={suppliers?.length ?? 0} /><SummaryCard icon={Package} label="מוצרים" value={allProducts?.length ?? 0} /><SummaryCard icon={Package} label="ספקים עם קטלוג" value={(suppliers ?? []).filter((s) => (productCountBySupplier.get(s.id) ?? 0) > 0).length} /><SummaryCard icon={ShoppingCart} label="תוצאות" value={filtered.length} /></section>
    <div className="rounded-2xl border border-slate-200/80 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900"><div className="relative max-w-xl"><Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} /><Input placeholder="חיפוש לפי ספק, איש קשר, טלפון, אימייל או מספר לקוח..." value={search} onChange={(e) => setSearch(e.target.value)} className="h-11 pr-10" /></div></div>
    {isLoading && <div className="overflow-hidden rounded-2xl border bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"><TableSkeleton rows={6} cols={9} /></div>}{isError && <ErrorState description="טעינת הספקים נכשלה." onRetry={() => refetch()} />}
    {!isLoading && !isError && filtered.length === 0 && <EmptyState icon={Users} title={suppliers?.length ? "לא נמצאו ספקים התואמים לחיפוש" : "אין ספקים עדיין"} description={suppliers?.length ? "נסה לשנות את מילות החיפוש." : canManage ? "הוסף ספק לפני יצירת מוצרים והזמנות." : undefined} actionLabel={canManage && !suppliers?.length ? "ספק חדש" : undefined} onAction={openCreateModal} />}
    {!isLoading && !isError && filtered.length > 0 && <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"><Table><TableHead><tr><TableHeaderCell>ספק</TableHeaderCell><TableHeaderCell>איש קשר</TableHeaderCell><TableHeaderCell>טלפונים</TableHeaderCell><TableHeaderCell>מס' לקוח</TableHeaderCell><TableHeaderCell>ימי הזמנות</TableHeaderCell><TableHeaderCell>ימי אספקה</TableHeaderCell><TableHeaderCell>מוצרים</TableHeaderCell><TableHeaderCell>סטטוס</TableHeaderCell><TableHeaderCell>פעולה</TableHeaderCell></tr></TableHead><TableBody>{filtered.map((supplier) => { const productCount = productCountBySupplier.get(supplier.id) ?? 0; return <TableRow key={supplier.id}>
      <TableCell><div className="min-w-[180px]"><Link href={`/dashboard/suppliers/${supplier.id}`} className="font-extrabold text-slate-900 hover:text-indigo-700 dark:text-white">{supplier.name}</Link>{canManage && <button type="button" onClick={() => startEdit(supplier, "name")} className="mr-2 rounded-md p-1 text-indigo-400 hover:bg-indigo-50" aria-label="עריכת שם ספק"><Pencil size={13} /></button>}</div></TableCell>
      <TableCell>{cell(supplier, "contact_name", supplier.contact_name || "—")}</TableCell>
      <TableCell><div className="space-y-1 text-xs">{cell(supplier, "phone", supplier.phone || "—")} {supplier.phone2 && cell(supplier, "phone2", supplier.phone2)}</div></TableCell>
      <TableCell>{cell(supplier, "customer_number", supplier.customer_number || "—", "font-mono text-slate-500")}</TableCell>
      <TableCell>{cell(supplier, "order_days", supplier.order_days || "—")}</TableCell>
      <TableCell>{cell(supplier, "delivery_days", supplier.delivery_days || "—")}</TableCell>
      <TableCell><Link href={`/dashboard/catalog?supplier_id=${supplier.id}`} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs font-bold text-slate-600 hover:bg-indigo-50 hover:text-indigo-700 dark:bg-slate-800 dark:text-slate-300"><Package size={13} />{productCount}</Link></TableCell>
      <TableCell><ActiveBadge active={supplier.active} /></TableCell><TableCell><Link href={`/dashboard/orders/new?supplier_id=${supplier.id}`} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-50 px-2.5 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-300"><ShoppingCart size={14} />הזמנה</Link></TableCell>
    </TableRow>; })}</TableBody></Table></div>}
    <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="ספק חדש"><div className="space-y-3">{Object.entries({ name: "שם", contact_name: "איש קשר", email: "אימייל", phone: "טלפון ראשי", phone2: "טלפון נוסף", customer_number: "מס' לקוח", order_days: "ימי הזמנות", delivery_days: "ימי אספקה" }).map(([key, label]) => <div key={key}><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">{label}</label><Input autoFocus={key === "name"} type={key === "email" ? "email" : "text"} value={form[key as keyof typeof form]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} /></div>)}{formError && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/30">{formError}</p>}<div className="flex gap-2 pt-2"><Button onClick={handleSubmit} disabled={createSupplier.isPending}>{createSupplier.isPending ? "יוצר..." : "יצירת ספק"}</Button><Button variant="ghost" onClick={() => setModalOpen(false)}>ביטול</Button></div></div></Modal>
  </div>;
}

function SummaryCard({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: number }) { return <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center justify-between"><p className="text-xs font-bold text-slate-400">{label}</p><div className="rounded-lg bg-slate-50 p-2 text-indigo-600 dark:bg-slate-800"><Icon size={16} /></div></div><p className="mt-2 text-2xl font-black text-slate-900 dark:text-white">{value}</p></div>; }
