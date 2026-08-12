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
};
