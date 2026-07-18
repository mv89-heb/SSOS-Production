import { apiClient } from "./api-client";
import { Product, Supplier } from "@/types";

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
}

export interface UpdateProductInput {
  name?: string;
  sku?: string;
  description?: string;
  current_price?: number;
  currency?: string;
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
};
