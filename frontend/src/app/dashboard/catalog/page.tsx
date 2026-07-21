"use client";
import { useState, useMemo } from "react";
import { Search, Plus, Pencil, Power, Package, ImageOff, AlertTriangle } from "lucide-react";
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
import { PriceComparison } from "@/components/catalog/price-comparison";
import { Product } from "@/types";

interface ProductFormState {
  supplier_id: string;
  name: string;
  sku: string;
  description: string;
  current_price: string;
  currency: string;
  image_url: string;
  barcode: string;
  category: string;
  unit: string;
  units_per_carton: string;
  supplier_sku: string;
  current_stock: string;
  min_stock: string;
  recommended_stock: string;
}

const EMPTY_FORM: ProductFormState = {
  supplier_id: "",
  name: "",
  sku: "",
  description: "",
  current_price: "",
  currency: "ILS",
  image_url: "",
  barcode: "",
  category: "",
  unit: "",
  units_per_carton: "",
  supplier_sku: "",
  current_stock: "",
  min_stock: "",
  recommended_stock: "",
};

// A blank string means "field not touched" — parse to a number only when
// the user actually typed something, otherwise omit it from the payload
// entirely (so we never send 0 where the user meant "leave empty").
function parseOptionalInt(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? Math.trunc(n) : undefined;
}

export default function CatalogPage() {
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [showMoreFields, setShowMoreFields] = useState(false);
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

  const categories = useMemo(() => {
    const set = new Set<string>();
    products?.forEach((p) => {
      if (p.category) set.add(p.category);
    });
    return Array.from(set).sort();
  }, [products]);

  const filtered = useMemo(() => {
    if (!products) return [];
    return products.filter((p) => {
      const matchesSearch =
        !search ||
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        (p.sku ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (p.barcode ?? "").includes(search);
      const matchesStatus =
        statusFilter === "all" || (statusFilter === "active" ? p.active : !p.active);
      const matchesCategory = categoryFilter === "all" || p.category === categoryFilter;
      return matchesSearch && matchesStatus && matchesCategory;
    });
  }, [products, search, statusFilter, categoryFilter]);

  const isLowStock = (p: Product) =>
    p.current_stock != null && p.min_stock != null && p.current_stock < p.min_stock;

  const openCreateModal = () => {
    setEditingProduct(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setShowMoreFields(false);
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
      image_url: product.image_url ?? "",
      barcode: product.barcode ?? "",
      category: product.category ?? "",
      unit: product.unit ?? "",
      units_per_carton: product.units_per_carton != null ? String(product.units_per_carton) : "",
      supplier_sku: product.supplier_sku ?? "",
      current_stock: product.current_stock != null ? String(product.current_stock) : "",
      min_stock: product.min_stock != null ? String(product.min_stock) : "",
      recommended_stock: product.recommended_stock != null ? String(product.recommended_stock) : "",
    });
    setFormError(null);
    setShowMoreFields(false);
    setModalOpen(true);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!form.supplier_id) return setFormError("בחר ספק.");
    if (!form.name.trim()) return setFormError("שם המוצר הוא שדה חובה.");
    const price = Number(form.current_price);
    if (!Number.isFinite(price) || price < 0) return setFormError("הזן מחיר תקין.");

    if (form.barcode.trim() && !/^\d+$/.test(form.barcode.trim())) {
      return setFormError("ברקוד יכול להכיל ספרות בלבד.");
    }
    for (const [label, value] of [
      ["יחידות בקרטון", form.units_per_carton],
      ["מלאי קיים", form.current_stock],
      ["מלאי מינימום", form.min_stock],
      ["מלאי מומלץ", form.recommended_stock],
    ] as const) {
      if (value.trim() && (!Number.isFinite(Number(value)) || Number(value) < 0)) {
        return setFormError(`${label}: יש להזין מספר שלם חיובי.`);
      }
    }

    const payload = {
      supplier_id: Number(form.supplier_id),
      name: form.name.trim(),
      sku: form.sku.trim() || undefined,
      description: form.description.trim() || undefined,
      current_price: price,
      currency: form.currency,
      image_url: form.image_url.trim() || undefined,
      barcode: form.barcode.trim() || undefined,
      category: form.category.trim() || undefined,
      unit: form.unit.trim() || undefined,
      units_per_carton: parseOptionalInt(form.units_per_carton),
      supplier_sku: form.supplier_sku.trim() || undefined,
      current_stock: parseOptionalInt(form.current_stock),
      min_stock: parseOptionalInt(form.min_stock),
      recommended_stock: parseOptionalInt(form.recommended_stock),
    };

    if (editingProduct) {
      updateProduct.mutate(payload, { onSuccess: () => setModalOpen(false) });
    } else {
      createProduct.mutate(payload, { onSuccess: () => setModalOpen(false) });
    }
  };

  const isSaving = createProduct.isPending || updateProduct.isPending;
  const inputClass =
    "block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-primary focus:ring-2 focus:ring-primary/20";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">קטלוג</h1>
        {canManage && (
          <Button onClick={openCreateModal}>
            <Plus size={16} />
            מוצר חדש
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input
            placeholder='חיפוש לפי שם, מק"ט או ברקוד...'
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pr-9"
          />
        </div>
        {categories.length > 0 && (
          <Select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="w-44">
            <option value="all">כל הקטגוריות</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        )}
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)} className="w-40">
          <option value="all">כל הסטטוסים</option>
          <option value="active">פעילים בלבד</option>
          <option value="inactive">לא פעילים בלבד</option>
        </Select>
      </div>

      {isLoading && (
        <div className="rounded-lg border bg-white shadow-sm">
          <TableSkeleton rows={5} cols={5} />
        </div>
      )}

      {isError && <ErrorState description="טעינת הקטלוג נכשלה." onRetry={() => refetch()} />}

      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          icon={Package}
          title={products && products.length > 0 ? "לא נמצאו מוצרים התואמים לסינון" : "אין מוצרים עדיין"}
          description={
            products && products.length > 0
              ? "נסה חיפוש או סינון אחר."
              : canManage
              ? "צור את המוצר הראשון שלך כדי להתחיל ליצור הזמנות."
              : undefined
          }
          actionLabel={canManage && (!products || products.length === 0) ? "מוצר חדש" : undefined}
          onAction={openCreateModal}
        />
      )}

      {!isLoading && !isError && filtered.length > 0 && (
        <Table>
          <TableHead>
            <tr>
              <TableHeaderCell></TableHeaderCell>
              <TableHeaderCell>מק"ט</TableHeaderCell>
              <TableHeaderCell>שם</TableHeaderCell>
              <TableHeaderCell>קטגוריה</TableHeaderCell>
              <TableHeaderCell>ספק</TableHeaderCell>
              <TableHeaderCell>מחיר</TableHeaderCell>
              <TableHeaderCell>מלאי</TableHeaderCell>
              <TableHeaderCell>סטטוס</TableHeaderCell>
              {canManage && <TableHeaderCell>פעולות</TableHeaderCell>}
            </tr>
          </TableHead>
          <TableBody>
            {filtered.map((product) => (
              <TableRow key={product.id}>
                <TableCell>
                  {product.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={product.image_url}
                      alt={product.name}
                      className="h-8 w-8 rounded object-cover bg-slate-100"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                  ) : (
                    <div className="flex h-8 w-8 items-center justify-center rounded bg-slate-100 text-slate-300">
                      <ImageOff size={14} />
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-slate-500">{product.sku || "—"}</TableCell>
                <TableCell className="font-medium text-slate-900">{product.name}</TableCell>
                <TableCell className="text-slate-500">{product.category || "—"}</TableCell>
                <TableCell>{supplierName(product.supplier_id)}</TableCell>
                <TableCell>
                  {product.currency} {product.current_price.toLocaleString()}
                  {product.unit && <span className="text-slate-400"> / {product.unit}</span>}
                </TableCell>
                <TableCell>
                  {product.current_stock != null ? (
                    <span
                      className={
                        isLowStock(product)
                          ? "inline-flex items-center gap-1 font-medium text-red-600"
                          : "text-slate-700"
                      }
                      title={isLowStock(product) ? "מלאי נמוך ממלאי המינימום שהוגדר" : undefined}
                    >
                      {isLowStock(product) && <AlertTriangle size={14} />}
                      {product.current_stock}
                    </span>
                  ) : (
                    "—"
                  )}
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
                        aria-label="עריכת מוצר"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => {
                          setEditingProduct(product);
                          toggleActive.mutate(!product.active);
                        }}
                        className="text-slate-400 hover:text-slate-700"
                        aria-label={product.active ? "השבתת מוצר" : "הפעלת מוצר"}
                        title={product.active ? "השבתה (מחיקה רכה)" : "הפעלה"}
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
        title={editingProduct ? "עריכת מוצר" : "מוצר חדש"}
      >
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">ספק</label>
            <Select
              value={form.supplier_id}
              onChange={(e) => setForm((f) => ({ ...f, supplier_id: e.target.value }))}
            >
              <option value="">בחר ספק...</option>
              {suppliers?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">שם</label>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">מק"ט</label>
              <Input value={form.sku} onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">מחיר</label>
              <Input
                type="number"
                min={0}
                step="0.01"
                value={form.current_price}
                onChange={(e) => setForm((f) => ({ ...f, current_price: e.target.value }))}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">קטגוריה</label>
              <Input
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                placeholder="לדוגמה: משקאות"
                list="catalog-categories"
              />
              <datalist id="catalog-categories">
                {categories.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">יחידת מכירה</label>
              <Input
                value={form.unit}
                onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))}
                placeholder='לדוגמה: יחידה, קילו, ארגז'
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">תיאור</label>
            <textarea
              className={inputClass}
              rows={2}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>

          <button
            type="button"
            onClick={() => setShowMoreFields((v) => !v)}
            className="text-sm font-medium text-primary hover:underline"
          >
            {showMoreFields ? "הסתר פרטים נוספים" : "פרטים נוספים (תמונה, ברקוד, מלאי...)"}
          </button>

          {showMoreFields && (
            <div className="space-y-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">כתובת תמונה</label>
                <Input
                  value={form.image_url}
                  onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value }))}
                  placeholder="https://..."
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">ברקוד</label>
                  <Input
                    value={form.barcode}
                    onChange={(e) => setForm((f) => ({ ...f, barcode: e.target.value }))}
                    inputMode="numeric"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">קוד מוצר של הספק</label>
                  <Input
                    value={form.supplier_sku}
                    onChange={(e) => setForm((f) => ({ ...f, supplier_sku: e.target.value }))}
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">יחידות בקרטון</label>
                <Input
                  type="number"
                  min={0}
                  value={form.units_per_carton}
                  onChange={(e) => setForm((f) => ({ ...f, units_per_carton: e.target.value }))}
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">מלאי קיים</label>
                  <Input
                    type="number"
                    min={0}
                    value={form.current_stock}
                    onChange={(e) => setForm((f) => ({ ...f, current_stock: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">מלאי מינימום</label>
                  <Input
                    type="number"
                    min={0}
                    value={form.min_stock}
                    onChange={(e) => setForm((f) => ({ ...f, min_stock: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-700">מלאי מומלץ</label>
                  <Input
                    type="number"
                    min={0}
                    value={form.recommended_stock}
                    onChange={(e) => setForm((f) => ({ ...f, recommended_stock: e.target.value }))}
                  />
                </div>
              </div>
            </div>
          )}

          {editingProduct && (
            <PriceComparison
              productId={editingProduct.id}
              primarySupplierId={editingProduct.supplier_id}
              primarySupplierName={supplierName(editingProduct.supplier_id)}
              primaryPrice={editingProduct.current_price}
              currency={editingProduct.currency}
              suppliers={suppliers}
              canManage={canManage}
            />
          )}

          {editingProduct && (
            <p className="text-xs text-slate-400">
              שינוי המחיר משפיע רק על הזמנות עתידיות — הזמנות שכבר בוצעו שומרות על המחיר
              שבו נוצרו (שמירת תמונת מצב).
            </p>
          )}

          {formError && <p className="text-sm text-red-500">{formError}</p>}

          <div className="flex gap-2 pt-2">
            <Button onClick={handleSubmit} disabled={isSaving}>
              {isSaving ? "שומר..." : editingProduct ? "שמירת שינויים" : "יצירת מוצר"}
            </Button>
            <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={isSaving}>
              ביטול
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
