import { apiClient } from "./api-client";

export interface RegulatedEggPrice {
  id: number;
  size_code: "M" | "L" | "XL";
  pack_size: number;
  max_consumer_price: number;
  effective_date: string;
  published_at: string | null;
  change_percent: number | null;
  verification_status: string;
  source_url: string;
  source_title: string;
  created_at: string | null;
}
export interface RegulatedEggProductMatch {
  product_id: number;
  product_name: string;
  supplier_id: number;
  supplier_name: string | null;
  size_code: "M" | "L" | "XL" | null;
  size_label: string | null;
  regulated: boolean;
  exclusion_reason: string | null;
  max_consumer_price: number | null;
  product_current_price: number | null;
  note: string;
}
export interface RegulatedEggPricesResponse {
  success: boolean;
  current_release: RegulatedEggPrice[];
  history: RegulatedEggPrice[];
  matched_products: RegulatedEggProductMatch[];
  effective_date: string | null;
  source_scope: string;
  monitor: { last_article_url: string | null; last_article_title: string | null; last_published_at: string | null; last_checked_at: string | null; last_error: string | null } | null;
}
export const regulatoryPricesService = {
  getEggPrices: async () => (await apiClient.get<RegulatedEggPricesResponse>("/api/regulatory-prices/eggs")).data,
  addEggRelease: async (payload: {
    effective_date: string;
    published_at?: string;
    source_url: string;
    source_title: string;
    change_percent?: number;
    verified_official?: boolean;
    items: Array<{ size_code: "M" | "L" | "XL"; max_consumer_price: number }>;
  }) => (await apiClient.post("/api/regulatory-prices/eggs/releases", payload)).data,
};
