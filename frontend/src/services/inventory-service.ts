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

export interface InventoryRecommendation {
  product_id: number;
  product_name: string;
  current_stock: number;
  stock_checks_in_period: number;
  observed_days: number;
  estimated_depletion: number;
  average_daily_usage: number;
  lead_time_days: number;
  days_until_next_order: number | null;
  planning_horizon_days: number;
  reorder_point: number;
  recommended_order: number;
  coverage_days: number | null;
  safety_stock: number;
  status: "urgent" | "reorder" | "healthy" | "insufficient_data";
  data_ready: boolean;
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
  };
}

// Inventory uses cartons by default. Only an explicit "יחידה" product is
// counted as individual pieces. The catalog's original unit value remains
// available elsewhere and is not rewritten by this normalization.
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
  printBarcodeLabels: async (productIds: number[]) => {
    const response = await apiClient.post<Blob>("/api/inventory/barcodes/labels", { product_ids: productIds }, { responseType: "blob" });
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
    (await apiClient.get<{ success: boolean; recommendations: InventoryRecommendation[] }>("/api/price-intelligence/inventory/recommendations", { params: options })).data.recommendations,
};
