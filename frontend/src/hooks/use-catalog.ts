"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { catalogService, CreateSupplierInput, UpdateSupplierInput, CreateProductInput, UpdateProductInput, CreateOfferInput, UpdateOfferInput } from "@/services/catalog-service";

const SUPPLIERS_KEY = ["suppliers"] as const;
const PRODUCTS_KEY = ["products"] as const;
const CATEGORIES_KEY = ["product-categories"] as const;
const supplierKey = (id: number) => ["supplier", id] as const;
const productKey = (id: number) => ["product", id] as const;
const offersKey = (productId: number) => ["offers", productId] as const;

export function useSuppliers(activeOnly = false) { return useQuery({ queryKey: [...SUPPLIERS_KEY, activeOnly], queryFn: () => catalogService.listSuppliers(activeOnly) }); }
export function useSupplier(id: number) { return useQuery({ queryKey: supplierKey(id), queryFn: () => catalogService.getSupplierById(id), enabled: Number.isFinite(id) }); }
export function useCreateSupplier() { const q = useQueryClient(); return useMutation({ mutationFn: (input: CreateSupplierInput) => catalogService.createSupplier(input), onSuccess: () => q.invalidateQueries({ queryKey: SUPPLIERS_KEY }) }); }
export function useUpdateSupplier(id: number) { const q = useQueryClient(); return useMutation({ mutationFn: (input: UpdateSupplierInput) => catalogService.updateSupplier(id, input), onSuccess: (supplier) => { q.setQueryData(supplierKey(id), supplier); q.invalidateQueries({ queryKey: SUPPLIERS_KEY }); } }); }
export function useProducts(supplierId?: number, activeOnly = false) { return useQuery({ queryKey: [...PRODUCTS_KEY, supplierId ?? "all", activeOnly], queryFn: () => catalogService.listProducts(supplierId, activeOnly) }); }
export function useProduct(id: number) { return useQuery({ queryKey: productKey(id), queryFn: () => catalogService.getProductById(id), enabled: Number.isFinite(id) }); }
export function useCreateProduct() { const q = useQueryClient(); return useMutation({ mutationFn: (input: CreateProductInput) => catalogService.createProduct(input), onSuccess: () => q.invalidateQueries({ queryKey: PRODUCTS_KEY }) }); }
export function useUpdateProduct(id: number) { const q = useQueryClient(); return useMutation({ mutationFn: (input: UpdateProductInput) => catalogService.updateProduct(id, input), onSuccess: (product) => { q.setQueryData(productKey(id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useUpdateProductById() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, input }: { id: number; input: UpdateProductInput }) => { if (!Number.isFinite(id) || id <= 0) throw new Error("Invalid product id"); return catalogService.updateProduct(id, input); }, onSuccess: (product) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useToggleProductActive() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, active }: { id: number; active: boolean }) => active ? catalogService.activateProduct(id) : catalogService.deactivateProduct(id), onSuccess: (product) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useCategories() { return useQuery({ queryKey: CATEGORIES_KEY, queryFn: () => catalogService.listCategories(), staleTime: 1000 * 60 * 60 }); }
export function useClassifyProduct() { const q = useQueryClient(); return useMutation({ mutationFn: (id: number) => catalogService.classifyProduct(id), onSuccess: ({ product }) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useCategoryFeedback() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, category }: { id: number; category: string }) => catalogService.saveCategoryFeedback(id, category), onSuccess: (product) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useOffers(productId: number) { return useQuery({ queryKey: offersKey(productId), queryFn: () => catalogService.listOffers(productId), enabled: Number.isFinite(productId) && productId > 0 }); }
export function useCreateOffer(productId: number) { const q = useQueryClient(); return useMutation({ mutationFn: (input: CreateOfferInput) => catalogService.createOffer(productId, input), onSuccess: () => q.invalidateQueries({ queryKey: offersKey(productId) }) }); }
export function useUpdateOffer(productId: number) { const q = useQueryClient(); return useMutation({ mutationFn: ({ offerId, input }: { offerId: number; input: UpdateOfferInput }) => catalogService.updateOffer(productId, offerId, input), onSuccess: () => q.invalidateQueries({ queryKey: offersKey(productId) }) }); }
export function useDeleteOffer(productId: number) { const q = useQueryClient(); return useMutation({ mutationFn: (offerId: number) => catalogService.deleteOffer(productId, offerId), onSuccess: () => q.invalidateQueries({ queryKey: offersKey(productId) }) }); }
