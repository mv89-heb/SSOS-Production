"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  catalogService,
  CreateSupplierInput,
  UpdateSupplierInput,
  CreateProductInput,
  UpdateProductInput,
} from "@/services/catalog-service";

const SUPPLIERS_KEY = ["suppliers"] as const;
const PRODUCTS_KEY = ["products"] as const;
const supplierKey = (id: number) => ["supplier", id] as const;
const productKey = (id: number) => ["product", id] as const;

// Suppliers
export function useSuppliers(activeOnly = false) {
  return useQuery({
    queryKey: [...SUPPLIERS_KEY, activeOnly],
    queryFn: () => catalogService.listSuppliers(activeOnly),
  });
}

export function useSupplier(id: number) {
  return useQuery({
    queryKey: supplierKey(id),
    queryFn: () => catalogService.getSupplierById(id),
    enabled: Number.isFinite(id),
  });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateSupplierInput) => catalogService.createSupplier(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SUPPLIERS_KEY }),
  });
}

export function useUpdateSupplier(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateSupplierInput) => catalogService.updateSupplier(id, input),
    onSuccess: (supplier) => {
      queryClient.setQueryData(supplierKey(id), supplier);
      queryClient.invalidateQueries({ queryKey: SUPPLIERS_KEY });
    },
  });
}

// Products
export function useProducts(supplierId?: number, activeOnly = false) {
  return useQuery({
    queryKey: [...PRODUCTS_KEY, supplierId ?? "all", activeOnly],
    queryFn: () => catalogService.listProducts(supplierId, activeOnly),
  });
}

export function useProduct(id: number) {
  return useQuery({
    queryKey: productKey(id),
    queryFn: () => catalogService.getProductById(id),
    enabled: Number.isFinite(id),
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateProductInput) => catalogService.createProduct(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PRODUCTS_KEY }),
  });
}

export function useUpdateProduct(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateProductInput) => catalogService.updateProduct(id, input),
    onSuccess: (product) => {
      queryClient.setQueryData(productKey(id), product);
      queryClient.invalidateQueries({ queryKey: PRODUCTS_KEY });
    },
  });
}

export function useToggleProductActive(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (active: boolean) =>
      active ? catalogService.activateProduct(id) : catalogService.deactivateProduct(id),
    onSuccess: (product) => {
      queryClient.setQueryData(productKey(id), product);
      queryClient.invalidateQueries({ queryKey: PRODUCTS_KEY });
    },
  });
}
