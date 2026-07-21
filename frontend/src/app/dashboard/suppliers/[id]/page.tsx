"use client";
import { use, useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Search, ShoppingCart, ImageOff } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { useSupplier, useUpdateSupplier, useProducts } from "@/hooks/use-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ActiveBadge } from "@/components/ui/badge";
import { Table, TableHead, TableBody, TableRow, TableHeaderCell, TableCell } from "@/components/ui/table";

export default function SupplierDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const supplierId = Number(id);
  const { user } = useAuth();
  const canManage = permissions.canManageCatalog(user);

  const { data: supplier, isLoading, isError } = useSupplier(supplierId);
  const { data: products } = useProducts(supplierId);
  const updateSupplier = useUpdateSupplier(supplierId);

  const [search, setSearch] = useState("");
  const filteredProducts = useMemo(() => {
    if (!products) return [];
    if (!search) return products;
    const q = search.toLowerCase();
    return products.filter(
      (p) => p.name.toLowerCase().includes(q) || (p.sku ?? "").toLowerCase().includes(q)
    );
  }, [products, search]);

  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState({ name: "", contact_name: "", email: "", phone: "" });

  useEffect(() => {
    if (supplier) {
      setForm({
        name: supplier.name,
        contact_name: supplier.contact_name ?? "",
        email: supplier.email ?? "",
        phone: supplier.phone ?? "",
      });
    }
  }, [supplier]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="animate-spin" size={16} />
        טוען ספק...
      </div>
    );
  }

  if (isError || !supplier) return <p className="text-sm text-slate-400">הספק לא נמצא</p>;

  const save = () => {
    updateSupplier.mutate(form, { onSuccess: () => setIsEditing(false) });
  };

  const toggleActive = () => {
    updateSupplier.mutate({ active: !supplier.active });
  };

  return (
    <div className="space-y-6">
      <Link href="/dashboard/suppliers" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
        <ArrowLeft size={16} />
        חזרה לספקים
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{supplier.name}</h1>
          <div className="mt-1">
            <ActiveBadge active={supplier.active} />
          </div>
        </div>
        {canManage && !isEditing && (
          <div className="flex gap-2">
            <Link href={`/dashboard/orders/new?supplier_id=${supplier.id}`}>
              <Button variant="secondary">
                <ShoppingCart size={16} />
                הזמנה חדשה
              </Button>
            </Link>
            <Button variant="secondary" onClick={() => setIsEditing(true)}>
              עריכה
            </Button>
            <Button variant={supplier.active ? "danger" : "primary"} onClick={toggleActive} disabled={updateSupplier.isPending}>
              {supplier.active ? "השבתה" : "הפעלה"}
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">פרטים</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {isEditing ? (
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
              <div className="flex gap-2 pt-2">
                <Button onClick={save} disabled={updateSupplier.isPending}>
                  {updateSupplier.isPending ? "שומר..." : "שמירת שינויים"}
                </Button>
                <Button variant="ghost" onClick={() => setIsEditing(false)} disabled={updateSupplier.isPending}>
                  ביטול
                </Button>
              </div>
            </div>
          ) : (
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-slate-500">איש קשר</dt>
                <dd className="text-slate-900">{supplier.contact_name || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">אימייל</dt>
                <dd className="text-slate-900">{supplier.email || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">טלפון</dt>
                <dd className="text-slate-900">{supplier.phone || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">נוסף בתאריך</dt>
                <dd className="text-slate-900">{new Date(supplier.created_at).toLocaleDateString()}</dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">מוצרים מספק זה</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-4">
          {products && products.length > 0 && (
            <div className="relative max-w-sm">
              <Search className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <Input
                placeholder="חיפוש מוצר..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pr-9"
              />
            </div>
          )}

          {!products || products.length === 0 ? (
            <p className="text-sm text-slate-400">אין מוצרים עדיין.</p>
          ) : filteredProducts.length === 0 ? (
            <p className="text-sm text-slate-400">לא נמצאו מוצרים התואמים לחיפוש.</p>
          ) : (
            <Table>
              <TableHead>
                <tr>
                  <TableHeaderCell></TableHeaderCell>
                  <TableHeaderCell>מק"ט</TableHeaderCell>
                  <TableHeaderCell>שם</TableHeaderCell>
                  <TableHeaderCell>קטגוריה</TableHeaderCell>
                  <TableHeaderCell>יחידה</TableHeaderCell>
                  <TableHeaderCell>מחיר</TableHeaderCell>
                  <TableHeaderCell>סטטוס</TableHeaderCell>
                </tr>
              </TableHead>
              <TableBody>
                {filteredProducts.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      {p.image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={p.image_url}
                          alt={p.name}
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
                    <TableCell className="text-slate-500">{p.sku || "—"}</TableCell>
                    <TableCell className="font-medium text-slate-900">{p.name}</TableCell>
                    <TableCell className="text-slate-500">{p.category || "—"}</TableCell>
                    <TableCell className="text-slate-500">{p.unit || "—"}</TableCell>
                    <TableCell>
                      {p.currency} {p.current_price.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <ActiveBadge active={p.active} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
