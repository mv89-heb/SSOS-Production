import { apiClient } from "./api-client";
import { Product, Supplier, SupplierOffer } from "@/types";

export interface CreateSupplierInput {
  name: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  phone2?: string;
  customer_number?: string;
  delivery_days?: string;
  order_days?: string;
}

export interface UpdateSupplierInput {
  name?: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  phone2?: string;
  customer_number?: string;
  delivery_days?: string;
  order_days?: string;
  active?: boolean;
}

export interface CreateProductInput {
  supplier_id: number;
  name: string;
  sku?: string;
  description?: string;
  current_price: number;
  currency?: string;
  image_url?: string;
  barcode?: string;
  category?: string;
  unit?: string;
  units_per_carton?: number;
  supplier_sku?: string;
  current_stock?: number;
  min_stock?: number;
  recommended_stock?: number;
}

export interface UpdateProductInput {
  supplier_id?: number;
  name?: string;
  sku?: string;
  description?: string;
  current_price?: number;
  currency?: string;
  active?: boolean;
  image_url?: string;
  barcode?: string;
  category?: string;
  unit?: string;
  units_per_carton?: number;
  supplier_sku?: string;
  current_stock?: number;
  min_stock?: number;
  recommended_stock?: number;
}

export interface CreateOfferInput { supplier_id: number; price: number; currency?: string; supplier_sku?: string; unit?: string; units_per_carton?: number; }
export interface UpdateOfferInput { price?: number; currency?: string; supplier_sku?: string; unit?: string; units_per_carton?: number; active?: boolean; }

export interface MasterProductRecord {
  id: number; canonical_name: string; brand?: string | null; category?: string | null;
  barcode?: string | null; base_unit?: string | null; package_size?: number | null; package_unit?: string | null;
  supplier_count?: number; listing_count?: number; current_price?: number | null; currency?: string | null; comparison_unit?: string | null; comparable_supplier_count?: number; best_supplier_name?: string | null; has_price?: boolean;
}
export interface SupplierProductListing {
  id: number; supplier_id: number; supplier_name: string; supplier_company_name?: string | null;
  supplier_sku?: string | null; barcode?: string | null; description?: string | null;
  price?: number | null; currency: string; unit?: string | null; units_per_carton?: number | null;
  match_status: "PENDING" | "APPROVED" | "REJECTED"; master_product_id?: number | null;
  suggested_master_product_id?: number | null; suggested_master_product?: MasterProductRecord | null;
  match_confidence?: number | null; match_method?: string | null;
}
export interface MasterMatchSuggestion {
  master_product: MasterProductRecord; confidence: number; method: string; decision: string;
}
export interface SupplierProductIntakeInput {
  supplier_id: number; supplier_name: string; description?: string; supplier_sku?: string;
  barcode?: string; price?: number; currency?: string; unit?: string; units_per_carton?: number;
}
export interface MasterProductPriceOffer {
  supplier_id: number; supplier_name?: string | null; supplier_product_id: number | null;
  supplier_sku?: string | null; supplier_product_name: string; price: number; currency: string;
  unit?: string | null; comparison_unit?: string | null; normalized_price: number; source_type?: string; observed_at?: string | null; source_document_id?: number | null; match_confidence?: number | null;
}
export interface MasterProductPriceComparison {
  master_product: MasterProductRecord;
  groups: Array<{ currency: string; comparison_unit: string; offers: MasterProductPriceOffer[]; best_offer?: MasterProductPriceOffer }>;
  incomplete_offers: Array<SupplierProductListing & { incomparable_reason?: string }>;
  supplier_product_count: number;
}

export const catalogService = {
  listSuppliers: async (activeOnly = false) => {
    const { data } = await apiClient.get<{ success: boolean; suppliers: Supplier[] }>("/api/catalog/suppliers", { params: { active: activeOnly ? "true" : "false" } });
    return data.suppliers;
  },
  getSupplierById: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean; supplier: Supplier }>(`/api/catalog/suppliers/${id}`);
    return data.supplier;
  },
  createSupplier: async (input: CreateSupplierInput) => {
    const { data } = await apiClient.post<{ success: boolean; supplier: Supplier }>("/api/catalog/suppliers", input);
    return data.supplier;
  },
  updateSupplier: async (id: number, input: UpdateSupplierInput) => {
    const { data } = await apiClient.put<{ success: boolean; supplier: Supplier }>(`/api/catalog/suppliers/${id}`, input);
    return data.supplier;
  },
  listProducts: async (supplierId?: number, activeOnly = false) => {
    const params: Record<string, unknown> = {};
    if (supplierId !== undefined) params.supplier_id = supplierId;
    if (activeOnly) params.active = "true";
    const { data } = await apiClient.get<{ success: boolean; products: Product[] }>("/api/catalog/products", { params });
    return data.products;
  },
  getProductById: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean; product: Product }>(`/api/catalog/products/${id}`);
    return data.product;
  },
  createProduct: async (input: CreateProductInput) => {
    const { data } = await apiClient.post<{ success: boolean; product: Product }>("/api/catalog/products", input);
    return data.product;
  },
  updateProduct: async (id: number, input: UpdateProductInput) => {
    const { data } = await apiClient.put<{ success: boolean; product: Product }>(`/api/catalog/products/${id}`, input);
    return data.product;
  },
  activateProduct: async (id: number) => {
    const { data } = await apiClient.put<{ success: boolean; product: Product }>(`/api/catalog/products/${id}`, { active: true });
    return data.product;
  },
  deactivateProduct: async (id: number) => {
    const { data } = await apiClient.put<{ success: boolean; product: Product }>(`/api/catalog/products/${id}`, { active: false });
    return data.product;
  },
  listCategories: async () => {
    const { data } = await apiClient.get<{ success: boolean; categories: string[] }>("/api/catalog/categories");
    return data.categories;
  },
  classifyProduct: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; classification: { category: string; confidence: number; source: string }; product: Product }>(`/api/catalog/products/${id}/classify`);
    return data;
  },
  autoClassifyProducts: async (limit = 1000) => {
    const { data } = await apiClient.post<{
      success: boolean;
      counts: { classified: number; review_needed: number; skipped: number };
      examples: Array<{ id: number; name: string; category: string; confidence: number; source: string }>;
      remaining_uncategorized: number;
    }>("/api/catalog/products/auto-classify", { limit });
    return data;
  },
  saveCategoryFeedback: async (id: number, category: string) => {
    const { data } = await apiClient.post<{ success: boolean; product: Product }>(`/api/catalog/products/${id}/category-feedback`, { category });
    return data.product;
  },
  listOffers: async (productId: number) => {
    const { data } = await apiClient.get<{ success: boolean; offers: SupplierOffer[] }>(`/api/catalog/products/${productId}/offers`);
    return data.offers;
  },
  createOffer: async (productId: number, input: CreateOfferInput) => {
    const { data } = await apiClient.post<{ success: boolean; offer: SupplierOffer }>(`/api/catalog/products/${productId}/offers`, input);
    return data.offer;
  },
  updateOffer: async (productId: number, offerId: number, input: UpdateOfferInput) => {
    const { data } = await apiClient.put<{ success: boolean; offer: SupplierOffer }>(`/api/catalog/products/${productId}/offers/${offerId}`, input);
    return data.offer;
  },
  deleteOffer: async (productId: number, offerId: number) => {
    await apiClient.delete(`/api/catalog/products/${productId}/offers/${offerId}`);
  },
  listMasterProducts: async (query = "", limit = 100) => {
    const { data } = await apiClient.get<{ success: boolean; master_products: MasterProductRecord[] }>("/api/catalog/master-products", { params: { q: query, limit } });
    return data.master_products;
  },
  compareMasterProduct: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean } & MasterProductPriceComparison>(`/api/catalog/master-products/${id}/comparison`);
    return data;
  },
  listPendingSupplierProducts: async () => {
    const { data } = await apiClient.get<{ success: boolean; supplier_products: SupplierProductListing[] }>("/api/catalog/supplier-products/pending");
    return data.supplier_products;
  },
  suggestMasterProducts: async (name: string, barcode?: string) => {
    const { data } = await apiClient.post<{ success: boolean; suggestions: MasterMatchSuggestion[] }>("/api/catalog/master-products/match-suggestions", { name, barcode, limit: 8 });
    return data.suggestions;
  },
  intakeSupplierProduct: async (input: SupplierProductIntakeInput) => {
    const { data } = await apiClient.post<{ success: boolean; supplier_product: SupplierProductListing; suggestions: MasterMatchSuggestion[] }>("/api/catalog/supplier-products/intake", input);
    return data;
  },
  approveSupplierProduct: async (id: number, masterProductId: number) => {
    const { data } = await apiClient.post<{ success: boolean; supplier_product: SupplierProductListing }>(`/api/catalog/supplier-products/${id}/approve`, { master_product_id: masterProductId });
    return data.supplier_product;
  },
  createMasterAndApproveSupplierProduct: async (id: number, input: { canonical_name: string; brand?: string; category?: string; barcode?: string; base_unit?: string; package_size?: number; package_unit?: string }) => {
    const { data } = await apiClient.post<{ success: boolean; supplier_product: SupplierProductListing; master_product: MasterProductRecord }>(`/api/catalog/supplier-products/${id}/approve`, { create_master_product: input });
    return data;
  },
  rejectSupplierProduct: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; supplier_product: SupplierProductListing }>(`/api/catalog/supplier-products/${id}/reject`);
    return data.supplier_product;
  },
};
