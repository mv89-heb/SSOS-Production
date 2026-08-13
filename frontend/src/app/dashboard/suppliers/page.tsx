"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, Package, Pencil, Plus, Search, ShoppingCart, Users, X } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useCreateSupplier, useProducts, useSuppliers, useUpdateSupplier } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { ActiveBadge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import type { Supplier } from "@/types";

const EMPTY_FORM = { name: "", contact_name: "", email: "", phone: "", phone2: "", customer_number: "", delivery_days: "", order_days: "" };
type EditableField = keyof typeof EMPTY_FORM;
type PresenceFilter = "all" | "yes" | "no";
type SupplierStatusFilter = "all" | "active" | "inactive";
type DaysFilter = "all" | "complete" | "missing";
type WeekDay = "ראשון" | "שני" | "שלישי" | "רביעי" | "חמישי" | "שישי" | "שבת";

const DAY_ALIASES: Record<string, WeekDay> = {
  א: "ראשון", "א׳": "ראשון", ראשון: "ראשון",
  ב: "שני", "ב׳": "שני", שני: "שני",
  ג: "שלישי", "ג׳": "שלישי", שלישי: "שלישי",
  ד: "רביעי", "ד׳": "רביעי", רביעי: "רביעי",
  ה: "חמישי", "ה׳": "חמישי", חמישי: "חמישי",
  ו: "שישי", "ו׳": "שישי", שישי: "שישי",
  ש: "שבת", "ש׳": "שבת", שבת: "שבת",
};

const DAY_SHORT: Record<WeekDay, string> = {
  ראשון: "א׳",
  שני: "ב׳",
  שלישי: "ג׳",
  רביעי: "ד׳",
  חמישי: "ה׳",
  שישי: "ו׳",
  שבת: "ש׳",
};

function hasValue(value: unknown) { return String(value ?? "").trim().length > 0; }

function parseSupplierDays(value?: string | null): WeekDay[] {
  if (!value) return [];
  let raw = value;
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) raw = parsed.join(",");
  } catch {
    // Legacy installations store the days as plain comma-separated text.
  }

  const selected = new Set<WeekDay>();
  raw
    .split(/[,|;/]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((part) => {
      const normalized = part.replace(/[׳']/g, "");
      const day = DAY_ALIASES[part] ?? DAY_ALIASES[normalized];
      if (day) selected.add(day);
    });

  return ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"].filter((day) => selected.has(day as WeekDay)) as WeekDay[];
}

function SupplierDays({ value }: { value?: string | null }) {
  const days = parseSupplierDays(value);
  if (!days.length) return <span className="text-slate-400">—</span>;

  return (
    <div
      className="flex max-w-[190px] flex-wrap gap-1"
      title={days.join(", ")}
      aria-label={`ימים: ${days.join(", ")}`}
    >
      {days.map((day) => (
        <span
          key={day}
          className="inline-flex h-6 min-w-6 items-center justify-center rounded-md border border-indigo-100 bg-indigo-50 px-1.5 text-[11px] font-bold text-indigo-700 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-300"
        >
          {DAY_SHORT[day]}
        </span>
      ))}
    </div>
  );
}

function TableFilterInput({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return <div className="relative"><Search className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" /><Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder} className="h-8 min-w-[105px] pr-7 text-xs" /></div>;
}

function TableFilterSelect<T extends string>({ value, onChange, children }: { value: T; onChange: (value: T) => void; children: React.ReactNode }) {
  return <Select value={value} onChange={(e) => onChange(e.target.value as T)} className="h-8 min-w-[105px] text-xs">{children}</Select>;
}

export default function SuppliersPage() {
  const { user } = useAuth(); const canManage = permissions.canManageCatalog(user);
  const [columnSearch, setColumnSearch] = useState(""); const [statusFilter, setStatusFilter] = useState<SupplierStatusFilter>("all"); const [contactFilter, setContactFilter] = useState<PresenceFilter>("all"); const [phoneFilter, setPhoneFilter] = useState<PresenceFilter>("all"); const [emailFilter, setEmailFilter] = useState<PresenceFilter>("all"); const [daysFilter, setDaysFilter] = useState<DaysFilter>("all");
  const [modalOpen, setModalOpen] = useState(false); const [form, setForm] = useState(EMPTY_FORM); const [formError, setFormError] = useState<string | null>(null); const [editing, setEditing] = useState<{ id: number; field: EditableField; value: string } | null>(null);
  const { data: suppliers, isLoading, isError, refetch } = useSuppliers(); const { data: allProducts } = useProducts(); const createSupplier = useCreateSupplier(); const updateSupplier = useUpdateSupplier(editing?.id ?? -1);
  const productCountBySupplier = useMemo(() => { const counts = new Map<number, number>(); (allProducts ?? []).forEach((product) => counts.set(product.supplier_id, (counts.get(product.supplier_id) ?? 0) + 1)); return counts; }, [allProducts]);
  const filtered = useMemo(() => (suppliers ?? []).filter((supplier) => { const query = columnSearch.trim().toLowerCase(); const searchable = [supplier.name, supplier.contact_name, supplier.email, supplier.phone, supplier.phone2, supplier.customer_number, supplier.order_days, supplier.delivery_days].filter(Boolean).map(String).join(" ").toLowerCase(); const matchesSearch = !query || searchable.includes(query); const matchesStatus = statusFilter === "all" || (statusFilter === "active" ? supplier.active : !supplier.active); const matchesContact = contactFilter === "all" || (contactFilter === "yes" ? hasValue(supplier.contact_name) : !hasValue(supplier.contact_name)); const matchesPhone = phoneFilter === "all" || (phoneFilter === "yes" ? hasValue(supplier.phone) || hasValue(supplier.phone2) : !hasValue(supplier.phone) && !hasValue(supplier.phone2)); const matchesEmail = emailFilter === "all" || (emailFilter === "yes" ? hasValue(supplier.email) : !hasValue(supplier.email)); const matchesDays = daysFilter === "all" || (daysFilter === "complete" ? hasValue(supplier.order_days) && hasValue(supplier.delivery_days) : !hasValue(supplier.order_days) || !hasValue(supplier.delivery_days)); return matchesSearch && matchesStatus && matchesContact && matchesPhone && matchesEmail && matchesDays; }), [suppliers, columnSearch, statusFilter, contactFilter, phoneFilter, emailFilter, daysFilter]);
  const activeFilters = [columnSearch, statusFilter, contactFilter, phoneFilter, emailFilter, daysFilter].filter((value) => value && value !== "all").length;
  const clearFilters = () => { setColumnSearch(""); setStatusFilter("all"); setContactFilter("all"); setPhoneFilter("all"); setEmailFilter("all"); setDaysFilter("all"); };
  const openCreateModal = () => { setForm({ ...EMPTY_FORM }); setFormError(null); setModalOpen(true); };
  const startEdit = (supplier: Supplier, field: EditableField) => setEditing({ id: supplier.id, field, value: String(supplier[field] ?? "") }); const cancelEdit = () => setEditing(null);
  const saveEdit = () => { if (!editing) return; const value = editing.value.trim(); if (editing.field === "name" && !value) return; updateSupplier.mutate({ [editing.field]: value }, { onSuccess: () => setEditing(null) }); };
  const cell = (supplier: Supplier, field: EditableField, display: React.ReactNode, className = "") => { const active = editing?.id === supplier.id && editing.field === field; if (!canManage) return <span className={className}>{display}</span>; if (!active) return <button type="button" onClick={() => startEdit(supplier, field)} title="עריכה ישירה" className={`group inline-flex min-h-9 w-full items-center justify-between gap-2 rounded-lg px-2 text-right transition hover:bg-indigo-50 dark:hover:bg-indigo-950/40 ${className}`}><span className="truncate">{display}</span><Pencil className="h-3.5 w-3.5 shrink-0 text-indigo-400 opacity-0 transition group-hover:opacity-100" /></button>; return <div className="flex items-center gap-1"><Input autoFocus value={editing.value} onChange={(e) => setEditing((current) => current ? { ...current, value: e.target.value } : current)} onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") setEditing(null); }} className="h-9 min-w-0" /><button type="button" onClick={saveEdit} disabled={updateSupplier.isPending} className="rounded-md p-1.5 text-emerald-600 hover:bg-emerald-50" aria-label="שמירת שינוי"><Check size={15} /></button><button type="button" onClick={cancelEdit} disabled={updateSupplier.isPending} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100" aria-label="ביטול שינוי"><X size={15} /></button></div>; };
  const handleSubmit = () => { setFormError(null); if (!form.name.trim()) return setFormError("שם הספק הוא שדה חובה."); createSupplier.mutate({ name: form.name.trim(), contact_name: form.contact_name.trim() || undefined, email: form.email.trim() || undefined, phone: form.phone.trim() || undefined, phone2: form.phone2.trim() || undefined, customer_number: form.customer_number.trim() || undefined, delivery_days: form.delivery_days.trim() || undefined, order_days: form.order_days.trim() || undefined }, { onSuccess: () => setModalOpen(false) }); };
  return <div className="space-y-6 pb-8" dir="rtl">
    <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between"><div><div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300"><Users className="h-3.5 w-3.5" />ניהול ספקים</div><h1 className="page-title">ספקים</h1><p className="page-subtitle">הסינון מתבצע ישירות בשורת הסינון של הטבלה. לחץ על שדה בטבלה כדי לערוך אותו ישירות.</p></div>{canManage && <Button onClick={openCreateModal}><Plus size={16} />ספק חדש</Button>}</section>
    <section className="grid grid-cols-2 gap-3 md:grid-cols-4"><SummaryCard icon={Users} label="ספקים" value={suppliers?.length ?? 0} /><SummaryCard icon={Package} label="מוצרים" value={allProducts?.length ?? 0} /><SummaryCard icon={Package} label="ספקים עם קטלוג" value={(suppliers ?? []).filter((s) => (productCountBySupplier.get(s.id) ?? 0) > 0).length} /><SummaryCard icon={ShoppingCart} label="תוצאות" value={filtered.length} /></section>
    {activeFilters > 0 && <div className="flex items-center justify-between rounded-xl border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-xs font-semibold text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-950/20 dark:text-indigo-300"><span>{filtered.length} ספקים תואמים את הסינון</span><button type="button" onClick={clearFilters} className="font-bold hover:underline">נקה סינון</button></div>}
    {isLoading && <div className="overflow-hidden rounded-2xl border bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"><TableSkeleton rows={6} cols={9} /></div>}{isError && <ErrorState description="טעינת הספקים נכשלה." onRetry={() => refetch()} />}
    {!isLoading && !isError && filtered.length === 0 && <EmptyState icon={Users} title={suppliers?.length ? "לא נמצאו ספקים התואמים לסינון" : "אין ספקים עדיין"} description={suppliers?.length ? "נסה לשנות את הסינון בשורת הכותרות של הטבלה." : canManage ? "הוסף ספק לפני יצירת מוצרים והזמנות." : undefined} actionLabel={canManage && !suppliers?.length ? "ספק חדש" : undefined} onAction={openCreateModal} />}
    {!isLoading && !isError && filtered.length > 0 && <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"><Table className="table-fixed min-w-[1180px]"><TableHead><tr><TableHeaderCell className="w-[19%]">ספק</TableHeaderCell><TableHeaderCell className="w-[12%]">איש קשר</TableHeaderCell><TableHeaderCell className="w-[13%]">טלפונים</TableHeaderCell><TableHeaderCell className="w-[11%]">מס' לקוח</TableHeaderCell><TableHeaderCell className="w-[13%]">ימי הזמנות</TableHeaderCell><TableHeaderCell className="w-[13%]">ימי אספקה</TableHeaderCell><TableHeaderCell className="w-[7%]">מוצרים</TableHeaderCell><TableHeaderCell className="w-[7%]">סטטוס</TableHeaderCell><TableHeaderCell className="w-[5%]">פעולה</TableHeaderCell></tr><tr className="border-b border-slate-200 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-950/60"><TableHeaderCell className="w-[19%]"><TableFilterInput value={columnSearch} onChange={setColumnSearch} placeholder="חיפוש ספק..." /></TableHeaderCell><TableHeaderCell className="w-[12%]"><TableFilterSelect value={contactFilter} onChange={setContactFilter}><option value="all">הכל</option><option value="yes">יש איש קשר</option><option value="no">חסר איש קשר</option></TableFilterSelect></TableHeaderCell><TableHeaderCell className="w-[13%]"><TableFilterSelect value={phoneFilter} onChange={setPhoneFilter}><option value="all">הכל</option><option value="yes">יש טלפון</option><option value="no">חסר טלפון</option></TableFilterSelect></TableHeaderCell><TableHeaderCell className="w-[11%]"><span className="block h-8" /></TableHeaderCell><TableHeaderCell className="w-[13%]"><TableFilterSelect value={daysFilter} onChange={setDaysFilter}><option value="all">הכל</option><option value="complete">מוגדרים</option><option value="missing">חסרים</option></TableFilterSelect></TableHeaderCell><TableHeaderCell className="w-[13%]"><TableFilterSelect value={daysFilter} onChange={setDaysFilter}><option value="all">הכל</option><option value="complete">מוגדרים</option><option value="missing">חסרים</option></TableFilterSelect></TableHeaderCell><TableHeaderCell className="w-[7%]" /><TableHeaderCell className="w-[7%]"><TableFilterSelect value={statusFilter} onChange={setStatusFilter}><option value="all">כל הסטטוסים</option><option value="active">פעילים</option><option value="inactive">לא פעילים</option></TableFilterSelect></TableHeaderCell><TableHeaderCell className="w-[5%]" /></tr></TableHead><TableBody>{filtered.map((supplier) => { const productCount = productCountBySupplier.get(supplier.id) ?? 0; return <TableRow key={supplier.id}><TableCell className="w-[19%] align-top"><div className="min-w-0"><Link href={`/dashboard/suppliers/${supplier.id}`} className="truncate font-extrabold text-slate-900 hover:text-indigo-700 dark:text-white">{supplier.name}</Link>{canManage && <button type="button" onClick={() => startEdit(supplier, "name")} className="mr-2 rounded-md p-1 text-indigo-400 hover:bg-indigo-50" aria-label="עריכת שם ספק"><Pencil size={13} /></button>}</div></TableCell><TableCell className="w-[12%] align-top">{cell(supplier, "contact_name", supplier.contact_name || "—")}</TableCell><TableCell className="w-[13%] align-top"><div className="space-y-1 text-xs">{cell(supplier, "phone", supplier.phone || "—")} {supplier.phone2 && cell(supplier, "phone2", supplier.phone2)}</div></TableCell><TableCell className="w-[11%] align-top">{cell(supplier, "customer_number", supplier.customer_number || "—", "font-mono text-slate-500")}</TableCell><TableCell className="w-[13%] align-top">{canManage ? cell(supplier, "order_days", <SupplierDays value={supplier.order_days} />) : <SupplierDays value={supplier.order_days} />}</TableCell><TableCell className="w-[13%] align-top">{canManage ? cell(supplier, "delivery_days", <SupplierDays value={supplier.delivery_days} />) : <SupplierDays value={supplier.delivery_days} />}</TableCell><TableCell className="w-[7%] align-top"><Link href={`/dashboard/catalog?supplier=${supplier.id}`} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/40"><Package size={14} />{productCount}</Link></TableCell><TableCell className="w-[7%] align-top"><ActiveBadge active={supplier.active} /></TableCell><TableCell className="w-[5%] align-top"><Link href={`/dashboard/suppliers/${supplier.id}`} className="rounded-lg px-2 py-1 text-sm font-bold text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/40">פתח</Link></TableCell></TableRow>; })}</TableBody></Table></div>}
    <Modal open={modalOpen} onClose={() => !createSupplier.isPending && setModalOpen(false)} title="ספק חדש"><div className="space-y-3"><div><label className="mb-1 block text-sm font-medium">שם הספק</label><Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} autoFocus /></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-2"><div><label className="mb-1 block text-sm font-medium">איש קשר</label><Input value={form.contact_name} onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium">אימייל</label><Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium">טלפון</label><Input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium">טלפון נוסף</label><Input value={form.phone2} onChange={(e) => setForm((f) => ({ ...f, phone2: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium">מספר לקוח</label><Input value={form.customer_number} onChange={(e) => setForm((f) => ({ ...f, customer_number: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium">ימי הזמנה</label><Input value={form.order_days} onChange={(e) => setForm((f) => ({ ...f, order_days: e.target.value }))} /></div><div><label className="mb-1 block text-sm font-medium">ימי אספקה</label><Input value={form.delivery_days} onChange={(e) => setForm((f) => ({ ...f, delivery_days: e.target.value }))} /></div></div>{formError && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm font-medium text-red-600">{formError}</p>}<div className="flex gap-2 pt-2"><Button onClick={handleSubmit} disabled={createSupplier.isPending}>{createSupplier.isPending ? "שומר..." : "יצירת ספק"}</Button><Button variant="ghost" onClick={() => setModalOpen(false)} disabled={createSupplier.isPending}>ביטול</Button></div></div></Modal>
  </div>;
}
function SummaryCard({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: number }) { return <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"><div className="flex items-center justify-between gap-3"><div><p className="text-xs font-bold text-slate-400">{label}</p><p className="mt-1 text-2xl font-black text-slate-900 dark:text-white">{value.toLocaleString("he-IL")}</p></div><div className="rounded-xl bg-indigo-50 p-2.5 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-300"><Icon size={18} /></div></div></div>; }
