"use client";
import { useState, useMemo } from "react";
import { Search, Plus, Pencil, Power, Package } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useProducts, useSuppliers, useCreateProduct, useUpdateProduct, useToggleProductActive } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { ActiveBadge } from "@/components/ui/badge";
import { Table, TableHead, TableBody, TableRow, TableHeaderCell, TableCell } from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Product } from "@/types";

interface ProductFormState {
  supplier_id: string;
  name: string;
  sku: string;
  description: string;
  current_price: string;
  currency: string;
}

const EMPTY_FORM: ProductFormState = {
  supplier_id: "",
  name: "",
  sku: "",
  description: "",
  current_price: "",
  currency: "ILS",
};

export default function CatalogPage() {
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: products, isLoading, isError, refetch } = useProducts();
  const { data: suppliers } = useSuppliers();
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct(editingProduct?.id ?? -1);
  const toggleActive = useToggleProductActive(editingProduct?.id ?? -1);

  const supplierName = (supplierId: number) =>
    suppliers?.find((s) => s.id === supplierId)?.name ?? `#${supplierId}`;

  const filtered = useMemo(() => {
    if (!products) return [];
    return products.filter((p) => {
      const matchesSearch =
        !search ||
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        (p.sku ?? "").toLowerCase().includes(search.toLowerCase());
      const matchesStatus =
        statusFilter === "all" || (statusFilter === "active" ? p.active : !p.active);
      return matchesSearch && matchesStatus;
    });
  }, [products, search, statusFilter]);

  const openCreateModal = () => {
    setEditingProduct(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setModalOpen(true);
  };

  const openEditModal = (product: Product) => {
    setEditingProduct(product);
    setForm({
      supplier_id: String(product.supplier_id),
      name: product.name,
      sku: product.sku ?? "",
      description: product.description ?? "",
      current_price: String(product.current_price),
      currency: product.currency,
    });
    setFormError(null);
    setModalOpen(true);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!form.supplier_id) return setFormError("Select a supplier.");
    if (!form.name.trim()) return setFormError("Product name is required.");
    const price = Number(form.current_price);
    if (!Number.isFinite(price) || price < 0) return setFormError("Enter a valid price.");

    const payload = {
      supplier_id: Number(form.supplier_id),
      name: form.name.trim(),
      sku: form.sku.trim() || undefined,
      description: form.description.trim() || undefined,
      current_price: price,
      currency: form.currency,
    };

    if (editingProduct) {
      updateProduct.mutate(payload, { onSuccess: () => setModalOpen(false) });
    } else {
      createProduct.mutate(payload, { onSuccess: () => setModalOpen(false) });
    }
  };

  const isSaving = createProduct.isPending || updateProduct.isPending;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Catalog</h1>
        {canManage && (
          <Button onClick={openCreateModal}>
            <Plus size={16} />
            New Product
          </Button>
        )}
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input
            placeholder="Search by name or SKU…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)} className="w-40">
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </Select>
      </div>

      {isLoading && (
        <div className="rounded-lg border bg-white shadow-sm">
          <TableSkeleton rows={5} cols={5} />
        </div>
      )}

      {isError && <ErrorState description="Could not load the catalog." onRetry={() => refetch()} />}

      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          icon={Package}
          title={products && products.length > 0 ? "No products match your filters" : "No products yet"}
          description={
            products && products.length > 0
              ? "Try a different search or status filter."
              : canManage
              ? "Create your first product to start building orders against it."
              : undefined
          }
          actionLabel={canManage && (!products || products.length === 0) ? "New Product" : undefined}
          onAction={openCreateModal}
        />
      )}

      {!isLoading && !isError && filtered.length > 0 && (
        <Table>
          <TableHead>
            <tr>
              <TableHeaderCell>SKU</TableHeaderCell>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Supplier</TableHeaderCell>
              <TableHeaderCell>Price</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              {canManage && <TableHeaderCell>Actions</TableHeaderCell>}
            </tr>
          </TableHead>
          <TableBody>
            {filtered.map((product) => (
              <TableRow key={product.id}>
                <TableCell className="text-slate-500">{product.sku || "—"}</TableCell>
                <TableCell className="font-medium text-slate-900">{product.name}</TableCell>
                <TableCell>{supplierName(product.supplier_id)}</TableCell>
                <TableCell>
                  {product.currency} {product.current_price.toLocaleString()}
                </TableCell>
                <TableCell>
                  <ActiveBadge active={product.active} />
                </TableCell>
                {canManage && (
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => openEditModal(product)}
                        className="text-slate-400 hover:text-slate-700"
                        aria-label="Edit product"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => {
                          setEditingProduct(product);
                          toggleActive.mutate(!product.active);
                        }}
                        className="text-slate-400 hover:text-slate-700"
                        aria-label={product.active ? "Deactivate product" : "Activate product"}
                        title={product.active ? "Deactivate (soft delete)" : "Activate"}
                      >
                        <Power size={16} />
                      </button>
                    </div>
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingProduct ? "Edit Product" : "New Product"}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Supplier</label>
            <Select
              value={form.supplier_id}
              onChange={(e) => setForm((f) => ({ ...f, supplier_id: e.target.value }))}
            >
              <option value="">Select a supplier…</option>
              {suppliers?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">SKU</label>
              <Input value={form.sku} onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Price</label>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={form.current_price}
                onChange={(e) => setForm((f) => ({ ...f, current_price: e.target.value }))}
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Description</label>
            <textarea
              className="block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-primary focus:ring-2 focus:ring-primary/20"
              rows={2}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>

          {editingProduct && (
            <p className="text-xs text-slate-400">
              Changing the price only affects future orders — orders already placed keep the price
              they were created with (Snapshot Integrity).
            </p>
          )}

          {formError && <p className="text-sm text-red-500">{formError}</p>}

          <div className="flex gap-2 pt-2">
            <Button onClick={handleSubmit} disabled={isSaving}>
              {isSaving ? "Saving…" : editingProduct ? "Save Changes" : "Create Product"}
            </Button>
            <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={isSaving}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
