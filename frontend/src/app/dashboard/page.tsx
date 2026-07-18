"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { orderService } from "@/services/order-service";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OrderStatusBadge } from "@/components/ui/badge";
import { ShoppingBag, Clock, CheckCircle2, Ban } from "lucide-react";

export default function DashboardPage() {
  const { data: orders, isLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => orderService.getOrders(),
  });

  const stats = [
    {
      label: "Total Orders",
      value: orders?.length ?? 0,
      icon: ShoppingBag,
      color: "text-blue-600",
    },
    {
      label: "Pending Approval",
      value: orders?.filter((o) => o.status === "submitted").length ?? 0,
      icon: Clock,
      color: "text-amber-500",
    },
    {
      label: "Completed",
      value: orders?.filter((o) => o.status === "completed").length ?? 0,
      icon: CheckCircle2,
      color: "text-green-600",
    },
    {
      label: "Cancelled",
      value: orders?.filter((o) => o.status === "cancelled").length ?? 0,
      icon: Ban,
      color: "text-red-500",
    },
  ];

  const recentOrders = [...(orders ?? [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-slate-500">{stat.label}</CardTitle>
              <stat.icon className={stat.color} size={20} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">{stat.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">Recent Orders</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
          {!isLoading && recentOrders.length === 0 && (
            <p className="text-sm text-slate-400">No orders yet.</p>
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
    </div>
  );
}
