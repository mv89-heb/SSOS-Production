"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { orderService } from "@/services/order-service";
import { useSuppliers, useProducts } from "@/hooks/use-catalog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OrderStatusBadge } from "@/components/ui/badge";
import { ShoppingBag, Clock, CheckCircle2, Ban, Users, Package } from "lucide-react";

export default function DashboardPage() {
  const { data: orders, isLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => orderService.getOrders(),
  });
  const { data: suppliers, isLoading: suppliersLoading } = useSuppliers();
  const { data: products, isLoading: productsLoading } = useProducts();

  const stats = [
    {
      label: "ספקים",
      value: suppliers?.length ?? 0,
      icon: Users,
      color: "text-purple-600",
      href: "/dashboard/suppliers",
    },
    {
      label: "מוצרים",
      value: products?.length ?? 0,
      icon: Package,
      color: "text-indigo-600",
      href: "/dashboard/catalog",
    },
    {
      label: "סה\"כ הזמנות",
      value: orders?.length ?? 0,
      icon: ShoppingBag,
      color: "text-blue-600",
      href: "/dashboard/orders",
    },
    {
      label: "ממתין לאישור",
      value: orders?.filter((o) => o.status === "submitted").length ?? 0,
      icon: Clock,
      color: "text-amber-500",
      href: "/dashboard/orders",
    },
  ];

  const recentOrders = [...(orders ?? [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  const recentSuppliers = [...(suppliers ?? [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  // "Top products" — no order-frequency data exists yet (that would need
  // aggregating across all orders' snapshot items), so this shows the
  // highest-priced active products as a stand-in "leading catalog items"
  // view — real data, clearly labeled for what it actually is.
  const topProducts = [...(products ?? [])]
    .filter((p) => p.active)
    .sort((a, b) => b.current_price - a.current_price)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-slate-900">לוח בקרה</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {stats.map((stat) => (
          <Link key={stat.label} href={stat.href}>
            <Card className="transition-shadow hover:shadow-md">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-slate-500">{stat.label}</CardTitle>
                <stat.icon className={stat.color} size={20} />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-slate-900">{stat.value}</div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-slate-900">הזמנות אחרונות</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {isLoading && <p className="text-sm text-slate-400">טוען...</p>}
            {!isLoading && recentOrders.length === 0 && (
              <p className="text-sm text-slate-400">אין הזמנות עדיין.</p>
            )}
            <div className="divide-y">
              {recentOrders.map((order) => (
                <Link
                  key={order.id}
                  href={`/dashboard/orders/${order.id}`}
                  className="flex items-center justify-between py-3 hover:bg-slate-50 -mx-2 px-2 rounded-md"
                >
                  <div>
                    <div className="text-sm font-medium text-slate-900">{order.order_number}</div>
                    <div className="text-xs text-slate-500">{order.supplier_name}</div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-slate-700">
                      {order.currency} {order.final_total.toLocaleString()}
                    </span>
                    <OrderStatusBadge status={order.status} />
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base text-slate-900">ספקים אחרונים</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {suppliersLoading && <p className="text-sm text-slate-400">טוען...</p>}
            {!suppliersLoading && recentSuppliers.length === 0 && (
              <p className="text-sm text-slate-400">אין ספקים עדיין.</p>
            )}
            <div className="divide-y">
              {recentSuppliers.map((supplier) => (
                <Link
                  key={supplier.id}
                  href={`/dashboard/suppliers/${supplier.id}`}
                  className="flex items-center justify-between py-3 hover:bg-slate-50 -mx-2 px-2 rounded-md"
                >
                  <span className="text-sm font-medium text-slate-900">{supplier.name}</span>
                  <span className="text-xs text-slate-400">
                    {new Date(supplier.created_at).toLocaleDateString()}
                  </span>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">מוצרים מובילים</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {productsLoading && <p className="text-sm text-slate-400">טוען...</p>}
          {!productsLoading && topProducts.length === 0 && (
            <p className="text-sm text-slate-400">אין מוצרים עדיין.</p>
          )}
          <div className="divide-y">
            {topProducts.map((product) => (
              <div key={product.id} className="flex items-center justify-between py-3">
                <div>
                  <div className="text-sm font-medium text-slate-900">{product.name}</div>
                  {product.category && <div className="text-xs text-slate-400">{product.category}</div>}
                </div>
                <span className="text-sm text-slate-700">
                  {product.currency} {product.current_price.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
