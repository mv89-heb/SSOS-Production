import { apiClient } from "./api-client";
import { CreateOrderInput, Order } from "@/types";

export interface UpdateDraftOrderInput {
  notes?: string;
  items?: { product_id: number; quantity: number }[];
}

export const orderService = {
  getOrders: async (status?: string) => {
    const { data } = await apiClient.get<{ success: boolean; orders: Order[] }>("/api/orders", {
      params: { status },
    });
    return data.orders;
  },

  getOrderById: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean; order: Order }>(`/api/orders/${id}`);
    return data.order;
  },

  createOrder: async (orderData: CreateOrderInput) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>("/api/orders", orderData);
    return data.order;
  },

  // Draft-only content edits (notes/items). The backend rejects any `status`
  // field on this endpoint — lifecycle transitions each have their own
  // dedicated endpoint below instead of PUT /api/orders/{id}.
  updateDraftOrder: async (id: number, payload: UpdateDraftOrderInput) => {
    const { data } = await apiClient.put<{ success: boolean; order: Order }>(`/api/orders/${id}`, payload);
    return data.order;
  },

  submitOrder: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/submit`);
    return data.order;
  },

  approveOrder: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/approve`);
    return data.order;
  },

  rejectOrder: async (id: number, reason?: string) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/reject`, {
      reason,
    });
    return data.order;
  },

  markSent: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/sent`);
    return data.order;
  },

  markCompleted: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/complete`);
    return data.order;
  },

  deleteOrder: async (id: number) => {
    const { data } = await apiClient.delete<{ success: boolean }>(`/api/orders/${id}`);
    return data;
  },
};
