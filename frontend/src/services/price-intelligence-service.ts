import { apiClient } from "./api-client";

export interface PriceOfferComparison {
  supplier_id: number;
  supplier_name: string | null;
  price: number;
  currency: string;
  unit: string | null;
  comparison_unit: string | null;
  normalized_price: number;
  primary: boolean;
}

export interface ProductComparison {
  success?: boolean;
  product: { id: number; name: string; current_price: number; currency: string; supplier_id: number };
  current: PriceOfferComparison | null;
  offers: PriceOfferComparison[];
  incomparable_offers: PriceOfferComparison[];
  best_offer: PriceOfferComparison | null;
  saving_per_unit: number;
  saving_percent: number;
}

export interface SavingsResult {
  product_id: number;
  quantity: number;
  current_cost: number;
  best_cost: number;
  savings: number;
  savings_percent: number;
  best_supplier_id: number | null;
  best_supplier_name?: string | null;
}

export interface PriceHistoryRow {
  id: number;
  product_id: number;
  supplier_id: number;
  supplier_name: string | null;
  old_price: number | null;
  new_price: number;
  currency: string;
  unit: string | null;
  source_type: string;
  source_document_id: number | null;
  effective_at: string;
  created_at: string;
  change_percent: number | null;
}

export const priceIntelligenceService = {
  compareProduct: async (productId: number) => {
    const { data } = await apiClient.get<ProductComparison>(`/api/price-intelligence/products/${productId}/comparison`);
    return data;
  },
  calculateSavings: async (productId: number, quantity: number) => {
    const { data } = await apiClient.get<SavingsResult>(`/api/price-intelligence/products/${productId}/savings`, { params: { quantity } });
    return data;
  },
  getHistory: async (productId: number, supplierId?: number) => {
    const { data } = await apiClient.get<{ success: boolean; history: PriceHistoryRow[] }>(`/api/price-intelligence/products/${productId}/history`, { params: supplierId ? { supplier_id: supplierId } : undefined });
    return data.history;
  },
  getChanges: async (limit = 100) => {
    const { data } = await apiClient.get<{ success: boolean; changes: PriceHistoryRow[] }>("/api/price-intelligence/changes", { params: { limit } });
    return data.changes;
  },
};
