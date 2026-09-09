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
  incomparable_reason?: string;
}

export interface ProductComparison {
  success?: boolean;
  product: { id: number; name: string; current_price: number; currency: string; supplier_id: number; sku?: string | null };
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

export interface BasketAnalysis {
  current_cost: number;
  optimized_cost: number;
  savings: number;
  savings_percent: number;
  supplier_count: number;
  suppliers: Array<{
    supplier_id: number;
    supplier_name: string | null;
    items: Array<{
      product_id: number;
      quantity: number;
      supplier_id: number;
      supplier_name: string | null;
      unit_price: number;
      line_total: number;
    }>;
  }>;
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

export interface GeminiInsight {
  recommendation: string | null;
  confidence: number;
  reasons: string[];
  risks: string[];
  trend: string;
  actions: string[];
}

export interface PortfolioOpportunity {
  product_id: number;
  product_name: string;
  sku?: string | null;
  current_supplier: string | null;
  best_supplier: string | null;
  current_price: number;
  best_price: number;
  savings_per_unit: number;
  savings_percent: number;
  currency: string;
}

export interface PortfolioSummary {
  products_analyzed: number;
  products_with_comparable_alternatives: number;
  opportunity_products: number;
  current_unit_total: number;
  best_unit_total: number;
  potential_savings: number;
  potential_savings_percent: number;
  top_opportunities: PortfolioOpportunity[];
  recent_changes: PriceHistoryRow[];
}

export interface SupplierPriceScore {
  supplier_id: number;
  supplier_name: string | null;
  participation: number;
  wins: number;
  coverage_percent: number;
  win_rate_percent: number;
  score: number;
}

export interface SupplierScoreResult {
  products_analyzed: number;
  suppliers: SupplierPriceScore[];
}

export interface ProcurementBriefing {
  headline: string;
  highlights: string[];
  risks: string[];
  actions: string[];
}

export interface ProcurementDataReadiness {
  products: {
    active: number;
    priced: number;
    categorized: number;
    missing_units: number;
    with_stock_rules: number;
  };
  supplier_offers: {
    active: number;
    products_covered: number;
    suppliers_covered: number;
  };
  suppliers: { active: number };
  price_intelligence: { history_rows: number; observation_rows: number };
  documents: { analyses: number };
  orders: { total: number; with_realized_value: number };
  readiness: {
    catalog: boolean;
    supplier_comparison: boolean;
    historical_prices: boolean;
    realized_spend: boolean;
    stock_risk: boolean;
  };
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
  optimizeBasket: async (items: Array<{ product_id: number; quantity: number }>, max_suppliers?: number) => {
    const { data } = await apiClient.post<{ success: boolean } & BasketAnalysis>("/api/price-intelligence/basket/analyze", { items, max_suppliers });
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
  getPortfolioSummary: async (limit = 10) => {
    const { data } = await apiClient.get<{ success: boolean } & PortfolioSummary>("/api/price-intelligence/summary", { params: { limit } });
    return data;
  },
  getSupplierScores: async (limit = 10) => {
    const { data } = await apiClient.get<{ success: boolean } & SupplierScoreResult>("/api/price-intelligence/supplier-scores", { params: { limit } });
    return data;
  },
  getDataReadiness: async () => {
    const { data } = await apiClient.get<{ success: boolean } & ProcurementDataReadiness>("/api/price-intelligence/data-readiness");
    return data;
  },
  getAiBriefing: async () => {
    const { data } = await apiClient.post<{ success: boolean; provider: string; model: string; briefing: ProcurementBriefing }>("/api/price-intelligence/ai-briefing");
    return data;
  },
  getGeminiInsight: async (productId: number, quantity: number) => {
    const { data } = await apiClient.post<{ success: boolean; provider: string; model: string; insight: GeminiInsight }>(
      `/api/price-intelligence/products/${productId}/ai-insight`,
      { quantity },
    );
    return data;
  },
};
