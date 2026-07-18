"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { orderService } from "@/services/order-service";
import { OrderStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

export default function OrdersPage() {
  const { data: orders, isLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => orderService.getOrders(),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Purchase Orders</h1>
        <Link href="/dashboard/orders/new">
          <Button>
            <Plus size={16} />
            New Order
          </Button>
        </Link>
      </div>

      <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
        <table className="w-full text-left">
          <thead className="border-b bg-slate-50">
            <tr>
              <th className="p-4 text-sm font-semibold text-slate-600">Order #</th>
              <th className="p-4 text-sm font-semibold text-slate-600">Supplier</th>
              <th className="p-4 text-sm font-semibold text-slate-600">Status</th>
              <th className="p-4 text-sm font-semibold text-slate-600">Total</th>
              <th className="p-4 text-sm font-semibold text-slate-600">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && (
              <tr>
                <td colSpan={5} className="p-4 text-sm text-slate-400">
                  Loading orders…
                </td>
              </tr>
            )}
            {!isLoading && orders?.length === 0 && (
              <tr>
                <td colSpan={5} className="p-4 text-sm text-slate-400">
                  No orders yet — create the first one.
                </td>
              </tr>
            )}
            {orders?.map((order) => (
              <tr key={order.id} className="hover:bg-slate-50">
                <td className="p-4 font-medium text-slate-900">
                  <Link href={`/dashboard/orders/${order.id}`} className="hover:underline">
                    {order.order_number}
                  </Link>
                </td>
                <td className="p-4 text-slate-700">{order.supplier_name}</td>
                <td className="p-4">
                  <OrderStatusBadge status={order.status} />
                </td>
                <td className="p-4 text-slate-700">
                  {order.currency} {order.final_total.toLocaleString()}
                </td>
                <td className="p-4 text-slate-500">
                  {new Date(order.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
