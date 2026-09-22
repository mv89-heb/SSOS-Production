import { apiClient } from "./api-client";
import type { Product } from "@/types";

export type InventoryMovementType = "receipt" | "issue" | "adjustment" | "count";

export interface InventoryMovement {
  id: number;
  product_id: number;
  movement_type: InventoryMovementType;
  quantity: number;
  balance_after: number | null;
  reference_type: string | null;
  reference_id: string | null;
  note: string | null;
  occurred_at: string;
  created_at: string;
}

export interface InventorySummary {
  stats: {
    active_products: number;
    low_stock: number;
    out_of_stock: number;
    without_stock_rule: number;
    movement_count: number;
  };
  products: Product[];
  recent_movements: InventoryMovement[];
}

export interface InventoryPlanningPeriod {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  consumption_multiplier: number;
  order_days: string;
  delivery_days: string;
  order_cutoff_time: string | null;
  active: boolean;
  notes: string | null;
}

export interface LatestInventoryCount {
  success: boolean;
  has_count: boolean;
  count_id: string | null;
  counted_at: string | null;
  counted: number;
  note?: string | null;
  movements: InventoryMovement[];
}

export interface InventoryCountStatus {
  count_weekday: number;
  count_time: string;
  active_products: number;
  counted_products_last_7_days: number;
  completion_percent: number;
  completed: boolean;
  due: boolean;
  next_due_date: string;
  window_start: string;
}

export interface InventoryRecommendation {
  product_id: number;
  product_name: string;
  current_stock: number;
  confirmed_inbound?: number;
  stock_checks_in_period: number;
  observed_days: number;
  estimated_depletion: number;
  average_daily_usage: number;
  base_average_daily_usage?: number;
  holiday_adjusted_demand?: number;
  holiday_adjusted_target_stock?: number;
  lead_time_days: number;
  days_until_next_order: number | null;
  planning_horizon_days: number;
  reorder_point: number;
  recommended_order: number;
  coverage_days: number | null;
  safety_stock: number;
  status: "urgent" | "reorder" | "healthy" | "insufficient_data";
  data_ready: boolean;
  active_planning_periods?: InventoryPlanningPeriod[];
  supplier_schedule: {
    supplier_id: number;
    supplier_name: string | null;
    order_days: number[];
    delivery_days: number[];
    next_order_date: string | null;
    next_delivery_date: string | null;
    recommended_check_date: string | null;
    order_cutoff_time: string | null;
    schedule_ready: boolean;
    schedule_adjusted_for_period?: boolean;
  };
}

export interface BarcodeLabelItem {
  product_id: number;
  quantity: number;
}

const normalizeInventoryProduct = (product: Product): Product => ({
  ...product,
  unit: product.stock_unit === "יחידה" || product.unit === "יחידה" ? "יחידה" : "ארגז",
});

export const inventoryService = {
  getSummary: async () => {
    const data = (await apiClient.get<InventorySummary>("/api/inventory/summary")).data;
    return { ...data, products: data.products.map(normalizeInventoryProduct) };
  },
  lookupProduct: async (value: string) => {
    const product = (await apiClient.get<{ success: boolean; product: Product }>("/api/inventory/products/lookup", { params: { value } })).data.product;
    return normalizeInventoryProduct(product);
  },
  generateBarcodes: async (productIds?: number[]) =>
    (await apiClient.post<{ success: boolean; generated_count: number; skipped_count: number; products: Product[]; skipped_product_ids: number[]; format: string }>("/api/inventory/barcodes/generate", productIds ? { product_ids: productIds } : {})).data,
  printBarcodeLabels: async (items: BarcodeLabelItem[]) => {
    const response = await apiClient.post<Blob>("/api/inventory/barcodes/labels", { items }, { responseType: "blob" });
    return response.data;
  },
  getMovements: async (params?: { product_id?: number; movement_type?: InventoryMovementType; limit?: number }) =>
    (await apiClient.get<{ success: boolean; movements: InventoryMovement[] }>("/api/inventory/movements", { params })).data.movements,
  getProductMovements: async (productId: number, limit = 100) => {
    const data = (await apiClient.get<{ success: boolean; product: Product; movements: InventoryMovement[] }>(`/api/inventory/products/${productId}/movements`, { params: { limit } })).data;
    return { ...data, product: normalizeInventoryProduct(data.product) };
  },
  createMovement: async (input: { product_id: number; movement_type: InventoryMovementType; quantity: number; note?: string; occurred_at?: string }) =>
    (await apiClient.post<{ success: boolean; movement: InventoryMovement }>("/api/inventory/movements", input)).data,
  getRecommendations: async (options?: { lookback_days?: number; safety_days?: number; limit?: number }) =>
    (await apiClient.get<{ success: boolean; recommendations: InventoryRecommendation[] }>("/api/inventory/planning/recommendations", { params: options })).data.recommendations,
  getPlanningPeriods: async () =>
    (await apiClient.get<{ success: boolean; periods: InventoryPlanningPeriod[] }>("/api/inventory/planning/periods")).data.periods,
  seedHolidayPeriods: async () =>
    (await apiClient.post<{ success: boolean; created_count: number; periods: InventoryPlanningPeriod[] }>("/api/inventory/planning/seed-holidays")).data,
  getLatestCount: async () => (await apiClient.get<LatestInventoryCount>("/api/inventory/count/latest")).data,
  getCountStatus: async () =>
    (await apiClient.get<{ success: boolean } & InventoryCountStatus>("/api/inventory/planning/count-status")).data,
};
