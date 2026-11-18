import { apiClient } from "./api-client";
import { CreateOrderInput, Order } from "@/types";

export interface UpdateDraftOrderInput {
  notes?: string;
  planned_order_date?: string | null;
  items?: { product_id: number; quantity: number }[];
}

export interface SupplierHistoryForecastProduct {
  product_id: number;
  product_name: string;
  unit: string;
  units_per_carton: number | null;
  order_count: number;
  weeks_with_orders: number;
  normal_weekly_average: number;
  boosted_weekly_forecast: number;
  average_weekly_forecast: number;
  recommended_quantity: number;
  target_week_multiplier: number;
  data_ready: boolean;
  readiness_reason: string | null;
  unit_conversion_issues: number;
}

export interface SupplierHistoryForecast {
  supplier_id: number;
  period: { start_date: string; end_date: string };
  target_date: string;
  source: string;
  order_count: number;
  seasonality: {
    cycle_weeks: number;
    normal_weeks: number;
    boosted_weeks: number;
    boosted_week_multiplier: number;
    target_week_multiplier: number;
  };
  products: SupplierHistoryForecastProduct[];
}

export const orderService = {
  getSupplierHistoryForecast: async (supplierId: number, targetDate?: string) => {
    const { data } = await apiClient.get<{ success: boolean; forecast: SupplierHistoryForecast }>(
      "/api/orders/supplier-history-forecast",
      { params: { supplier_id: supplierId, target_date: targetDate || undefined } },
    );
    return data.forecast;
  },

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

  duplicateOrder: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/duplicate`);
    return data.order;
  },

  updateDraftOrder: async (id: number, payload: UpdateDraftOrderInput) => {
    const { data } = await apiClient.put<{ success: boolean; order: Order }>(`/api/orders/${id}`, payload);
    return data.order;
  },

  deleteOrder: async (id: number) => {
    const { data } = await apiClient.delete<{ success: boolean; calendar_event_deleted?: boolean }>(`/api/orders/${id}`);
    return data;
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
};
