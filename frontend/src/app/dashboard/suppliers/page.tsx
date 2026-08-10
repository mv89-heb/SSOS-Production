"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Search, Plus, Users, ShoppingCart, Mail, Phone, Package, ArrowLeft } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useSuppliers, useCreateSupplier, useProducts } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { ActiveBadge } from "@/components/ui/badge";
import { Table, TableHead, TableBody, TableRow, TableHeaderCell, TableCell } from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";

const EMPTY_FORM = {
  name: "",
  contact_name: "",
  email: "",
  phone: "",
  phone2: "",
  customer_number: "",
  delivery_days: "",
  order_days: "",
};

export default function SuppliersPage() {
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: suppliers, isLoading, isError, refetch } = useSuppliers();
  const { data: allProducts } = useProducts();
  const createSupplier = useCreateSupplier();

  const productCountBySupplier = useMemo(() => {
    const counts = new Map<number, number>();
    (allProducts ?? []).forEach((product) => {
      counts.set(product.supplier_id, (counts.get(product.supplier_id) ?? 0) + 1);
    });
    return counts;
  }, [allProducts]);

  const filtered = useMemo(() => {
    const list = suppliers ?? [];
    const query = search.trim().toLowerCase();
    if (!query) return list;
    return list.filter((supplier) => {
      return [supplier.name, supplier.contact_name, supplier.email, supplier.phone, supplier.customer_number]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    });
  }, [suppliers, search]);

  const openCreateModal = () => {
    setForm(EMPTY_FORM);
    setFormError(null);
    setModalOpen(true);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!form.name.trim()) {
      setFormError("שם הספק הוא שדה חובה.");
      return;
    }
    createSupplier.mutate(
      {
        name: form.name.trim(),
        contact_name: form.contact_name.trim() || undefined,
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        phone2: form.phone2.trim() || undefined,
        customer_number: form.customer_number.trim() || undefined,
        delivery_days: form.delivery_days.trim() || undefined,
        order_days: form.order_days.trim() || undefined,
      },
      { onSuccess: () => setModalOpen(false) }
    );
  };

  return (
    <div className="space-y-6 pb-8">
      <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
            <Users className="h-3.5 w-3.5" />
            ניהול ספקים
          </div>
          <h1 className="page-title">ספקים</h1>
          <p className="page-subtitle">ניהול אנשי קשר, תנאי אספקה וקטלוגים לפי ספק.</p>
        </div>
        {canManage && (
          <Button onClick={openCreateModal}>
            <Plus size={16} />
            ספק חדש
          </Button>
        )}
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryCard icon={Users} label="ספקים" value={suppliers?.length ?? 0} />
        <SummaryCard icon={Package} label="מוצרים" value={allProducts?.length ?? 0} />
        <SummaryCard icon={Package} label="ספקים עם קטלוג" value={(suppliers ?? []).filter((s) => (productCountBySupplier.get(s.id) ?? 0) > 0).length} />
        <SummaryCard icon={ShoppingCart} label="תוצאות" value={filtered.length} />
      </section>

      <div className="rounded-2xl border border-slate-200/80 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="relative max-w-xl">
          <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={17} />
          <Input
            placeholder="חיפוש לפי ספק, איש קשר, טלפון, אימייל או מספר לקוח..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="h-11 pr-10"
          />
        </div>
        {search && (
          <div className="mt-2 flex items-center gap-2 px-1 text-xs text-slate-400">
            <span>נמצאו {filtered.length} ספקים</span>
            <button type="button" onClick={() => setSearch("")} className="font-bold text-indigo-600 hover:underline">נקה חיפוש</button>
          </div>
        )}
      </div>

      {isLoading && <div className="overflow-hidden rounded-2xl border bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"><TableSkeleton rows={6} cols={9} /></div>}
      {isError && <ErrorState description="טעינת הספקים נכשלה." onRetry={() => refetch()} />}

      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          icon={Users}
          title={suppliers && suppliers.length > 0 ? "לא נמצאו ספקים התואמים לחיפוש" : "אין ספקים עדיין"}
          description={suppliers && suppliers.length > 0 ? "נסה לשנות את מילות החיפוש." : canManage ? "הוסף ספק לפני יצירת מוצרים והזמנות." : undefined}
          actionLabel={canManage && (!suppliers || suppliers.length === 0) ? "ספק חדש" : undefined}
          onAction={openCreateModal}
        />
      )}

      {!isLoading && !isError && filtered.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <Table>
            <TableHead>
              <tr>
                <TableHeaderCell>ספק</TableHeaderCell>
                <TableHeaderCell>איש קשר</TableHeaderCell>
                <TableHeaderCell>טלפונים</TableHeaderCell>
                <TableHeaderCell>מס' לקוח</TableHeaderCell>
                <TableHeaderCell>ימי הזמנות</TableHeaderCell>
                <TableHeaderCell>ימי אספקה</TableHeaderCell>
                <TableHeaderCell>מוצרים</TableHeaderCell>
                <TableHeaderCell>סטטוס</TableHeaderCell>
                <TableHeaderCell>פעולה</TableHeaderCell>
              </tr>
            </TableHead>
            <TableBody>
              {filtered.map((supplier: any) => {
                const productCount = productCountBySupplier.get(supplier.id) ?? 0;
                return (
                  <TableRow key={supplier.id}>
                    <TableCell>
                      <Link href={`/dashboard/suppliers/${supplier.id}`} className="group flex min-w-[180px] items-center gap-3">
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-sm font-black text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                          {supplier.name.slice(0, 1).toUpperCase()}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-extrabold text-slate-900 group-hover:text-indigo-700 dark:text-white">{supplier.name}</span>
                          {supplier.email && <span className="block truncate text-xs text-slate-400">{supplier.email}</span>}
                        </span>
                      </Link>
                    </TableCell>
                    <TableCell>{supplier.contact_name || "—"}</TableCell>
                    <TableCell>
                      <div className="space-y-1 text-xs">
                        {supplier.phone ? <a href={`tel:${supplier.phone}`} className="flex items-center gap-1.5 font-mono text-slate-600 hover:text-indigo-600 dark:text-slate-300"><Phone size={12} />{supplier.phone}</a> : <span>—</span>}
                        {supplier.phone2 && <a href={`tel:${supplier.phone2}`} className="flex items-center gap-1.5 font-mono text-slate-400 hover:text-indigo-600"><Phone size={12} />{supplier.phone2}</a>}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-slate-500">{supplier.customer_number || "—"}</TableCell>
                    <TableCell>{supplier.order_days || "—"}</TableCell>
                    <TableCell>{supplier.delivery_days || "—"}</TableCell>
                    <TableCell>
                      <Link href={`/dashboard/catalog?supplier_id=${supplier.id}`} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs font-bold text-slate-600 hover:bg-indigo-50 hover:text-indigo-700 dark:bg-slate-800 dark:text-slate-300">
                        <Package size={13} />{productCount}
                      </Link>
                    </TableCell>
                    <TableCell><ActiveBadge active={supplier.active} /></TableCell>
                    <TableCell>
                      <Link href={`/dashboard/orders/new?supplier_id=${supplier.id}`} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-50 px-2.5 py-1.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-300">
                        <ShoppingCart size={14} /> הזמנה
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="ספק חדש">
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">שם</label>
            <Input autoFocus value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">איש קשר</label>
            <Input value={form.contact_name} onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">אימייל</label><Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} /></div>
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">טלפון ראשי</label><Input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} /></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">טלפון נוסף</label><Input value={form.phone2} onChange={(e) => setForm((f) => ({ ...f, phone2: e.target.value }))} /></div>
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">מס' לקוח</label><Input value={form.customer_number} onChange={(e) => setForm((f) => ({ ...f, customer_number: e.target.value }))} /></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">ימי הזמנות</label><Input value={form.order_days} onChange={(e) => setForm((f) => ({ ...f, order_days: e.target.value }))} placeholder="לדוגמה: ראשון, שלישי" /></div>
            <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-200">ימי אספקה</label><Input value={form.delivery_days} onChange={(e) => setForm((f) => ({ ...f, delivery_days: e.target.value }))} placeholder="לדוגמה: שני, רביעי" /></div>
          </div>
          {formError && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-300">{formError}</p>}
          <div className="flex gap-2 pt-2">
            <Button onClick={handleSubmit} disabled={createSupplier.isPending}>{createSupplier.isPending ? "יוצר..." : "יצירת ספק"}</Button>
            <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={createSupplier.isPending}>ביטול</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-bold text-slate-400">{label}</p>
        <div className="rounded-lg bg-slate-50 p-2 text-indigo-600 dark:bg-slate-800"><Icon size={16} /></div>
      </div>
      <p className="mt-2 text-2xl font-black text-slate-950 dark:text-white">{value}</p>
    </div>
  );
}
