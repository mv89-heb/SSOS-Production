"use client";
import { use, useState } from "react";
import Link from "next/link";
import { OrderStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { ArrowLeft, Loader2 } from "lucide-react";
import {
  useOrder,
  useUpdateDraftOrder,
  useSubmitOrder,
  useApproveOrder,
  useRejectOrder,
  useMarkSentOrder,
  useCompleteOrder,
} from "@/hooks/use-orders";

export default function OrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const orderId = Number(id);
  const { user } = useAuth();

  const { data: order, isLoading, isError, error } = useOrder(orderId);

  const [isEditingDraft, setIsEditingDraft] = useState(false);
  const [notesDraft, setNotesDraft] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [isRejecting, setIsRejecting] = useState(false);

  const updateDraft = useUpdateDraftOrder(orderId);
  const submit = useSubmitOrder(orderId);
  const approve = useApproveOrder(orderId);
  const reject = useRejectOrder(orderId);
  const markSent = useMarkSentOrder(orderId);
  const complete = useCompleteOrder(orderId);

  const isMutating =
    updateDraft.isPending ||
    submit.isPending ||
    approve.isPending ||
    reject.isPending ||
    markSent.isPending ||
    complete.isPending;

  const canCreateOrEdit = permissions.canCreateOrders(user);
  const isManagerOrAdmin = permissions.canApproveOrders(user);

  const startEditingDraft = () => {
    setNotesDraft(order?.notes ?? "");
    setIsEditingDraft(true);
  };

  const saveDraft = () => {
    updateDraft.mutate(
      { notes: notesDraft },
      { onSuccess: () => setIsEditingDraft(false) }
    );
  };

  const handleReject = () => {
    reject.mutate(rejectReason, {
      onSuccess: () => {
        setIsRejecting(false);
        setRejectReason("");
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Loader2 className="animate-spin" size={16} />
        Loading order…
      </div>
    );
  }

  if (isError) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 404) {
      return <p className="text-sm text-slate-400">Order not found</p>;
    }
    return <p className="text-sm text-red-500">Server error</p>;
  }

  if (!order) return <p className="text-sm text-slate-400">Order not found</p>;

  return (
    <div className="space-y-6">
      <Link
        href="/dashboard/orders"
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft size={16} />
        Back to orders
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{order.order_number}</h1>
          <p className="text-sm text-slate-500">{order.supplier_name}</p>
          <p className="text-xs text-slate-400">
            Created {new Date(order.created_at).toLocaleString()}
          </p>
        </div>
        <OrderStatusBadge status={order.status} />
      </div>

      {/* Actions by role */}
      <div className="flex flex-wrap items-center gap-3">
        {canCreateOrEdit && order.status === "draft" && !isEditingDraft && (
          <Button variant="secondary" onClick={startEditingDraft} disabled={isMutating}>
            Edit Draft
          </Button>
        )}
        {canCreateOrEdit && order.status === "draft" && (
          <Button onClick={() => submit.mutate()} disabled={isMutating}>
            {submit.isPending ? "Submitting…" : "Submit"}
          </Button>
        )}

        {isManagerOrAdmin && order.status === "submitted" && !isRejecting && (
          <>
            <Button onClick={() => approve.mutate()} disabled={isMutating}>
              {approve.isPending ? "Approving…" : "Approve"}
            </Button>
            <Button variant="danger" onClick={() => setIsRejecting(true)} disabled={isMutating}>
              Reject
            </Button>
          </>
        )}

        {/* Backend requires approved -> sent -> completed; exposed here so
            the full lifecycle can actually be driven from this page. */}
        {isManagerOrAdmin && order.status === "approved" && (
          <Button onClick={() => markSent.mutate()} disabled={isMutating}>
            {markSent.isPending ? "Marking sent…" : "Mark Sent"}
          </Button>
        )}
        {isManagerOrAdmin && order.status === "sent" && (
          <Button onClick={() => complete.mutate()} disabled={isMutating}>
            {complete.isPending ? "Completing…" : "Complete"}
          </Button>
        )}
      </div>

      {isRejecting && (
        <Card>
          <CardContent className="pt-6 space-y-3">
            <label className="block text-sm font-medium text-slate-700">Rejection reason</label>
            <textarea
              className="block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-primary focus:ring-2 focus:ring-primary/20"
              rows={2}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
            <div className="flex gap-2">
              <Button variant="danger" onClick={handleReject} disabled={isMutating}>
                {reject.isPending ? "Rejecting…" : "Confirm Reject"}
              </Button>
              <Button variant="ghost" onClick={() => setIsRejecting(false)} disabled={isMutating}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {isEditingDraft && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-slate-900">Edit Draft — Notes</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 space-y-3">
            <textarea
              className="block w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-primary focus:ring-2 focus:ring-primary/20"
              rows={3}
              value={notesDraft}
              onChange={(e) => setNotesDraft(e.target.value)}
            />
            <div className="flex gap-2">
              <Button onClick={saveDraft} disabled={isMutating}>
                {updateDraft.isPending ? "Saving…" : "Save"}
              </Button>
              <Button variant="ghost" onClick={() => setIsEditingDraft(false)} disabled={isMutating}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Snapshot line items — rendered straight from order.items, never
          re-fetched from the live Catalog, so this always reflects what the
          order actually charged even if the product changed or was deleted
          afterward. */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base text-slate-900">Line Items (Snapshot)</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-slate-500">
              <tr>
                <th className="py-2 font-medium">SKU</th>
                <th className="py-2 font-medium">Product</th>
                <th className="py-2 font-medium">Qty</th>
                <th className="py-2 font-medium">Frozen Unit Price</th>
                <th className="py-2 font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {order.items.map((item, idx) => (
                <tr key={`${item.product_id}-${idx}`}>
                  <td className="py-2 text-slate-500">{item.sku}</td>
                  <td className="py-2 text-slate-900">{item.product_name}</td>
                  <td className="py-2">{item.quantity}</td>
                  <td className="py-2">
                    {order.currency} {item.unit_price.toLocaleString()}
                  </td>
                  <td className="py-2 font-medium">
                    {order.currency} {item.total_price.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="mt-4 ml-auto w-64 space-y-1 text-sm">
            <div className="flex justify-between text-slate-500">
              <span>Subtotal</span>
              <span>{order.currency} {order.subtotal.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Discount</span>
              <span>-{order.currency} {order.discount_total.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Tax</span>
              <span>{order.currency} {order.tax_total.toLocaleString()}</span>
            </div>
            <div className="flex justify-between border-t pt-1 font-semibold text-slate-900">
              <span>Total</span>
              <span>{order.currency} {order.final_total.toLocaleString()}</span>
            </div>
          </div>

          {order.notes && !isEditingDraft && (
            <p className="mt-4 rounded-md bg-slate-50 p-3 text-sm text-slate-600 whitespace-pre-line">
              {order.notes}
            </p>
          )}

          {order.snapshot_taken_at && (
            <p className="mt-2 text-xs text-slate-400">
              Snapshot frozen at {new Date(order.snapshot_taken_at).toLocaleString()} — later catalog
              or price changes do not affect this order.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
