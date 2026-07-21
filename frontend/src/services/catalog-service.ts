import { apiClient } from "./api-client";
import { Product, Supplier, SupplierOffer } from "@/types";

export interface CreateSupplierInput {
  name: string;
  contact_name?: string;
  email?: string;
  phone?: string;
}

export interface UpdateSupplierInput {
  name?: string;
  contact_name?: string;
  email?: string;
  phone?: string;
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

export interface CreateOfferInput {
  supplier_id: number;
  price: number;
  currency?: string;
  supplier_sku?: string;
  unit?: string;
  units_per_carton?: number;
}

export interface UpdateOfferInput {
  price?: number;
  currency?: string;
  supplier_sku?: string;
  unit?: string;
  units_per_carton?: number;
  active?: boolean;
}

export const catalogService = {
  // Suppliers
  listSuppliers: async (activeOnly = false) => {
    const { data } = await apiClient.get<{ success: boolean; suppliers: Supplier[] }>(
      "/api/catalog/suppliers",
      { params: { active: activeOnly ? "true" : undefined } }
    );
    return data.suppliers;
  },
  getSupplierById: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean; supplier: Supplier }>(
      `/api/catalog/suppliers/${id}`
    );
    return data.supplier;
  },
  createSupplier: async (input: CreateSupplierInput) => {
    const { data } = await apiClient.post<{ success: boolean; supplier: Supplier }>(
      "/api/catalog/suppliers",
      input
    );
    return data.supplier;
  },
  updateSupplier: async (id: number, input: UpdateSupplierInput) => {
    const { data } = await apiClient.put<{ success: boolean; supplier: Supplier }>(
      `/api/catalog/suppliers/${id}`,
      input
    );
    return data.supplier;
  },

  // Products
  listProducts: async (supplierId?: number, activeOnly = false) => {
    const { data } = await apiClient.get<{ success: boolean; products: Product[] }>(
      "/api/catalog/products",
      { params: { supplier_id: supplierId, active: activeOnly ? "true" : undefined } }
    );
    return data.products;
  },
  getProductById: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean; product: Product }>(
      `/api/catalog/products/${id}`
    );
    return data.product;
  },
  createProduct: async (input: CreateProductInput) => {
    const { data } = await apiClient.post<{ success: boolean; product: Product }>(
      "/api/catalog/products",
      input
    );
    return data.product;
  },
  updateProduct: async (id: number, input: UpdateProductInput) => {
    const { data } = await apiClient.put<{ success: boolean; product: Product }>(
      `/api/catalog/products/${id}`,
      input
    );
    return data.product;
  },
  // "Delete" in the UI is always a soft delete (active:false) to preserve
  // Snapshot Integrity — orders already keep their own copy of product data
  // regardless, but we never offer a destructive hard-delete from the UI.
  deactivateProduct: async (id: number) => {
    const { data } = await apiClient.put<{ success: boolean; product: Product }>(
      `/api/catalog/products/${id}`,
      { active: false }
    );
    return data.product;
  },
  activateProduct: async (id: number) => {
    const { data } = await apiClient.put<{ success: boolean; product: Product }>(
      `/api/catalog/products/${id}`,
      { active: true }
    );
    return data.product;
  },

  // Phase 2: alternate-supplier price offers (comparison data — does not
  // affect order creation, which always uses the product's own price).
  listOffers: async (productId: number) => {
    const { data } = await apiClient.get<{ success: boolean; offers: SupplierOffer[] }>(
      `/api/catalog/products/${productId}/offers`
    );
    return data.offers;
  },
  createOffer: async (productId: number, input: CreateOfferInput) => {
    const { data } = await apiClient.post<{ success: boolean; offer: SupplierOffer }>(
      `/api/catalog/products/${productId}/offers`,
      input
    );
    return data.offer;
  },
  updateOffer: async (productId: number, offerId: number, input: UpdateOfferInput) => {
    const { data } = await apiClient.put<{ success: boolean; offer: SupplierOffer }>(
      `/api/catalog/products/${productId}/offers/${offerId}`,
      input
    );
    return data.offer;
  },
  deleteOffer: async (productId: number, offerId: number) => {
    await apiClient.delete(`/api/catalog/products/${productId}/offers/${offerId}`);
  },
};
