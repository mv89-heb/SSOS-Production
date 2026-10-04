import { apiClient } from "./api-client";

export type PriceCompletionResult = {
  status: "updated" | "unresolved" | "error";
  product_id: number;
  product_name: string;
  old_price?: number | null;
  new_price?: number | null;
  currency?: string;
  confidence?: number;
  match_type?: string;
  package_description?: string;
  evidence?: string;
  sources?: string[];
  reason?: string;
  model?: string;
};

export type PriceCompletionStatus = {
  total_active: number;
  priced: number;
  missing_price: number;
  missing_product_ids: number[];
};

export type PriceCompletionBatch = PriceCompletionStatus & {
  total_missing: number;
  processed: number;
  remaining: number;
  updated: number;
  unresolved: number;
  errors: number;
  results: PriceCompletionResult[];
};

export const geminiPriceCompletionService = {
  status: async () =>
    (await apiClient.get<{ success: boolean } & PriceCompletionStatus>("/api/price-intelligence/price-completion/status")).data,

  run: async (productIds: number[], batchSize = 5) =>
    (await apiClient.post<{ success: boolean } & PriceCompletionBatch>("/api/price-intelligence/price-completion/run", {
      product_ids: productIds,
      batch_size: batchSize,
    })).data,
};
