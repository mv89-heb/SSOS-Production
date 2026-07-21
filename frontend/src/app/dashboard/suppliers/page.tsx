"use client";
import { useState, useMemo } from "react";
import Link from "next/link";
import { Search, Plus, Users, ShoppingCart } from "lucide-react";
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

const EMPTY_FORM = { name: "", contact_name: "", email: "", phone: "" };

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
    (allProducts ?? []).forEach((p) => {
      counts.set(p.supplier_id, (counts.get(p.supplier_id) ?? 0) + 1);
    });
    return counts;
  }, [allProducts]);

  const filtered = useMemo(() => {
    if (!suppliers) return [];
    if (!search) return suppliers;
    return suppliers.filter((s) => s.name.toLowerCase().includes(search.toLowerCase()));
  }, [suppliers, search]);

  const openCreateModal = () => {
    setForm(EMPTY_FORM);
    setFormError(null);
    setModalOpen(true);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!form.name.trim()) return setFormError("שם הספק הוא שדה חובה.");
    createSupplier.mutate(
      {
        name: form.name.trim(),
        contact_name: form.contact_name.trim() || undefined,
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
      },
      { onSuccess: () => setModalOpen(false) }
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">ספקים</h1>
        {canManage && (
          <Button onClick={openCreateModal}>
            <Plus size={16} />
            ספק חדש
          </Button>
        )}
      </div>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
        <Input placeholder="חיפוש ספקים..." value={search} onChange={(e) => setSearch(e.target.value)} className="pr-9" />
      </div>

      {isLoading && (
        <div className="rounded-lg border bg-white shadow-sm">
          <TableSkeleton rows={5} cols={4} />
        </div>
      )}

      {isError && <ErrorState description="טעינת הספקים נכשלה." onRetry={() => refetch()} />}

      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          icon={Users}
          title={suppliers && suppliers.length > 0 ? "לא נמצאו ספקים התואמים לחיפוש" : "אין ספקים עדיין"}
          description={canManage ? "הוסף ספק לפני יצירת מוצרים המשויכים אליו." : undefined}
          actionLabel={canManage && (!suppliers || suppliers.length === 0) ? "ספק חדש" : undefined}
          onAction={openCreateModal}
        />
      )}

      {!isLoading && !isError && filtered.length > 0 && (
        <Table>
          <TableHead>
            <tr>
              <TableHeaderCell>שם</TableHeaderCell>
              <TableHeaderCell>איש קשר</TableHeaderCell>
              <TableHeaderCell>אימייל</TableHeaderCell>
              <TableHeaderCell>מוצרים</TableHeaderCell>
              <TableHeaderCell>סטטוס</TableHeaderCell>
              <TableHeaderCell></TableHeaderCell>
            </tr>
          </TableHead>
          <TableBody>
            {filtered.map((supplier) => (
              <TableRow key={supplier.id}>
                <TableCell className="font-medium text-slate-900">
                  <Link href={`/dashboard/suppliers/${supplier.id}`} className="hover:underline">
                    {supplier.name}
                  </Link>
                </TableCell>
                <TableCell>{supplier.contact_name || "—"}</TableCell>
                <TableCell>{supplier.email || "—"}</TableCell>
                <TableCell>{productCountBySupplier.get(supplier.id) ?? 0}</TableCell>
                <TableCell>
                  <ActiveBadge active={supplier.active} />
                </TableCell>
                <TableCell>
                  <Link
                    href={`/dashboard/orders/new?supplier_id=${supplier.id}`}
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                    title="הזמנה חדשה מספק זה"
                  >
                    <ShoppingCart size={16} />
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="ספק חדש">
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">שם</label>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">איש קשר</label>
            <Input value={form.contact_name} onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">אימייל</label>
              <Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">טלפון</label>
              <Input value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
            </div>
          </div>

          {formError && <p className="text-sm text-red-500">{formError}</p>}

          <div className="flex gap-2 pt-2">
            <Button onClick={handleSubmit} disabled={createSupplier.isPending}>
              {createSupplier.isPending ? "יוצר..." : "יצירת ספק"}
            </Button>
            <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={createSupplier.isPending}>
              ביטול
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
