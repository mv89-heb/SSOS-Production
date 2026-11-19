import { apiClient } from "./api-client";
import { CreateOrderInput, Order } from "@/types";

export interface OrderSearchResponse {
  success: boolean;
  orders: (Order & {
    search_provenance?: { matched_fields: string[]; missing_fields: string[] };
  })[];
  pagination: { total: number; limit: number; offset: number; has_more: boolean };
  filters: { q: string; status: string | null; supplier_id: number | null; start_date: string | null; end_date: string | null };
  search_context?: {
    searched_fields: string[];
    active_filters: { key: string; label: string; value: string }[];
    data_quality: { checked_orders: number; incomplete_count: number; scope: "current_page" };
  };
}

export interface OrderSearchParams {
  q?: string;
  status?: string;
  supplier_id?: number;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export interface SavedOrderSearch {
  id: number;
  name: string;
  filters: {
    q: string;
    status: string;
    supplier_id: number | null;
    start_date: string;
    end_date: string;
  };
  created_at: string | null;
  updated_at: string | null;
}

export interface CreateSavedOrderSearchInput {
  name: string;
  filters: {
    q?: string;
    status?: string;
    supplier_id?: number | null;
    start_date?: string;
    end_date?: string;
  };
}

export interface UpdateDraftOrderInput {
  notes?: string;
  planned_order_date?: string | null;
  department?: string | null;
  project?: string | null;
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

export interface OrderBudgetImpactItem {
  budget_id: number; scope_type: "department" | "project"; scope_value: string;
  period_type: "weekly" | "monthly"; period_start: string; period_end: string;
  currency: string; budget_amount: number; committed_before: number; order_amount: number;
  projected_total: number; remaining_after: number; over_budget: boolean; enforcement_mode: "warn" | "block";
}
export interface OrderBudgetImpact {
  order_id: number; order_number: string; department?: string | null; project?: string | null;
  currency: string; budget_date: string; impacts: OrderBudgetImpactItem[];
  over_budget: boolean; assignment_required: boolean; missing_scopes: Array<"department" | "project">; blocked: boolean; warnings: OrderBudgetImpactItem[]; blocks: OrderBudgetImpactItem[];
}
export interface ProcurementBudget {
  id: number; scope_type: "department" | "project"; scope_value: string;
  period_type: "weekly" | "monthly"; period_start: string; amount: number;
  currency: string; enforcement_mode: "warn" | "block"; active: boolean;
  spent_amount: number; remaining_amount: number; created_at: string; updated_at: string;
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

  searchOrders: async (params: OrderSearchParams = {}) => {
    const { data } = await apiClient.get<OrderSearchResponse>("/api/orders/search", { params });
    return data;
  },

  exportOrders: async (params: OrderSearchParams = {}, format: "csv" | "xlsx" = "csv") => {
    const { data } = await apiClient.get<Blob>("/api/orders/search", {
      params: { ...params, format, limit: 5000, offset: 0 },
      responseType: "blob",
    });
    return data;
  },

  getSavedSearches: async () => {
    const { data } = await apiClient.get<{ success: boolean; saved_searches: SavedOrderSearch[] }>("/api/orders/searches");
    return data.saved_searches;
  },

  createSavedSearch: async (payload: CreateSavedOrderSearchInput) => {
    const { data } = await apiClient.post<{ success: boolean; saved_search: SavedOrderSearch }>("/api/orders/searches", payload);
    return data.saved_search;
  },

  deleteSavedSearch: async (id: number) => {
    const { data } = await apiClient.delete<{ success: boolean; deleted_id: number }>(`/api/orders/searches/${id}`);
    return data;
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

  getBudgetImpact: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean; budget_impact: OrderBudgetImpact }>(`/api/procurement-budgets/orders/${id}/impact`);
    return data.budget_impact;
  },

  submitOrder: async (id: number, budgetOverrideReason?: string) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/submit`, { budget_override_reason: budgetOverrideReason });
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

  markOrdersSent: async (orderIds: number[]) => {
    const { data } = await apiClient.post<{ success: boolean; updated_count: number; orders: Order[] }>(
      "/api/orders/bulk/sent",
      { order_ids: orderIds },
    );
    return data;
  },

  markCompleted: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/orders/${id}/complete`);
    return data.order;
  },
};
