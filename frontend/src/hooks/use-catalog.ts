import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { catalogService, CreateSupplierInput, UpdateSupplierInput, CreateProductInput, UpdateProductInput, CreateOfferInput, UpdateOfferInput } from "@/services/catalog-service";
import type { Product, Supplier } from "@/types";

const SUPPLIERS_KEY = ["suppliers"] as const;
const PRODUCTS_KEY = ["products"] as const;
const CATEGORIES_KEY = ["product-categories"] as const;
const supplierKey = (id: number) => ["supplier", id] as const;
const productKey = (id: number) => ["product", id] as const;
const offersKey = (productId: number) => ["offers", productId] as const;

function getGlobalFilters() {
  if (typeof window === "undefined") return new URLSearchParams();
  return new URLSearchParams(window.location.search);
}

function filterSuppliers(items: Supplier[], activeOnly: boolean) {
  const params = getGlobalFilters();
  const status = params.get("gf_status");
  const contact = params.get("gf_contact");
  const phone = params.get("gf_phone");
  const email = params.get("gf_email");
  const days = params.get("gf_days");
  return items.filter((supplier) => {
    if (activeOnly && !supplier.active) return false;
    if (status === "active" && !supplier.active) return false;
    if (status === "inactive" && supplier.active) return false;
    const hasContact = Boolean(String(supplier.contact_name ?? "").trim());
    const hasPhone = Boolean(String(supplier.phone ?? "").trim() || String(supplier.phone2 ?? "").trim());
    const hasEmail = Boolean(String(supplier.email ?? "").trim());
    const hasDays = Boolean(String(supplier.order_days ?? "").trim() || String(supplier.delivery_days ?? "").trim());
    if (contact === "yes" && !hasContact) return false;
    if (contact === "no" && hasContact) return false;
    if (phone === "yes" && !hasPhone) return false;
    if (phone === "no" && hasPhone) return false;
    if (email === "yes" && !hasEmail) return false;
    if (email === "no" && hasEmail) return false;
    if (days === "complete" && !hasDays) return false;
    if (days === "missing" && hasDays) return false;
    return true;
  });
}

function filterProducts(items: Product[], supplierId?: number, activeOnly = false) {
  const params = getGlobalFilters();
  const globalSupplier = Number(params.get("gf_supplier"));
  const status = params.get("gf_status");
  const stock = params.get("gf_stock");
  const unit = params.get("gf_unit");
  const missing = params.get("gf_missing");
  const category = params.get("gf_category");
  const minPrice = Number(params.get("gf_price_min"));
  const maxPrice = Number(params.get("gf_price_max"));
  const hasMinPrice = params.has("gf_price_min") && Number.isFinite(minPrice);
  const hasMaxPrice = params.has("gf_price_max") && Number.isFinite(maxPrice);
  return items.filter((product) => {
    if (supplierId !== undefined && product.supplier_id !== supplierId) return false;
    if (Number.isFinite(globalSupplier) && globalSupplier > 0 && product.supplier_id !== globalSupplier) return false;
    if (activeOnly && !product.active) return false;
    if (status === "active" && !product.active) return false;
    if (status === "inactive" && product.active) return false;
    if (category && category !== "all" && (product.category ?? "") !== category) return false;
    if (unit && unit !== "all" && (product.unit ?? "").trim().toLowerCase() !== unit.trim().toLowerCase()) return false;
    if (hasMinPrice && Number(product.current_price) < minPrice) return false;
    if (hasMaxPrice && Number(product.current_price) > maxPrice) return false;
    const hasStockData = product.current_stock != null && product.min_stock != null;
    const isLow = hasStockData && product.current_stock! < product.min_stock!;
    if (stock === "low" && !isLow) return false;
    if (stock === "healthy" && (!hasStockData || isLow)) return false;
    if (stock === "missing" && hasStockData) return false;
    if (missing === "price" && product.current_price != null) return false;
    if (missing === "category" && String(product.category ?? "").trim()) return false;
    if (missing === "unit" && String(product.unit ?? "").trim()) return false;
    if (missing === "sku" && String(product.sku ?? "").trim()) return false;
    if (missing === "barcode" && String(product.barcode ?? "").trim()) return false;
    return true;
  });
}

function globalFilterKey() {
  if (typeof window === "undefined") return "";
  const params = new URLSearchParams(window.location.search);
  return ["gf_supplier", "gf_status", "gf_stock", "gf_price_min", "gf_price_max", "gf_unit", "gf_missing", "gf_category", "gf_contact", "gf_phone", "gf_email", "gf_days"].map((key) => `${key}=${params.get(key) ?? ""}`).join("&");
}

export function useSuppliers(activeOnly = false) {
  const filterKey = globalFilterKey();
  return useQuery({ queryKey: [...SUPPLIERS_KEY, activeOnly, filterKey], queryFn: async () => filterSuppliers(await catalogService.listSuppliers(activeOnly), activeOnly) });
}
export function useSupplier(id: number) { return useQuery({ queryKey: supplierKey(id), queryFn: () => catalogService.getSupplierById(id), enabled: Number.isFinite(id) }); }
export function useCreateSupplier() { const q = useQueryClient(); return useMutation({ mutationFn: (input: CreateSupplierInput) => catalogService.createSupplier(input), onSuccess: () => q.invalidateQueries({ queryKey: SUPPLIERS_KEY }) }); }
export function useUpdateSupplier(id: number) { const q = useQueryClient(); return useMutation({ mutationFn: (input: UpdateSupplierInput) => catalogService.updateSupplier(id, input), onSuccess: (supplier) => { q.setQueryData(supplierKey(id), supplier); q.invalidateQueries({ queryKey: SUPPLIERS_KEY }); } }); }
export function useProducts(supplierId?: number, activeOnly = false) {
  const filterKey = globalFilterKey();
  return useQuery({ queryKey: [...PRODUCTS_KEY, supplierId ?? "all", activeOnly, filterKey], queryFn: async () => filterProducts(await catalogService.listProducts(supplierId, activeOnly), supplierId, activeOnly) });
}
export function useProduct(id: number) { return useQuery({ queryKey: productKey(id), queryFn: () => catalogService.getProductById(id), enabled: Number.isFinite(id) }); }
export function useCreateProduct() { const q = useQueryClient(); return useMutation({ mutationFn: async (input: CreateProductInput) => { const product = await catalogService.createProduct(input); if (input.category?.trim()) return catalogService.saveCategoryFeedback(product.id, input.category.trim()); return product; }, onSuccess: (product) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useUpdateProduct(id: number) { const q = useQueryClient(); return useMutation({ mutationFn: async (input: UpdateProductInput) => { const product = await catalogService.updateProduct(id, input); if (input.category !== undefined && input.category.trim()) return catalogService.saveCategoryFeedback(id, input.category.trim()); return product; }, onSuccess: (product) => { q.setQueryData(productKey(id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useUpdateProductById() { const q = useQueryClient(); return useMutation({ mutationFn: async ({ id, input }: { id: number; input: UpdateProductInput }) => { if (!Number.isFinite(id) || id <= 0) throw new Error("Invalid product id"); const product = await catalogService.updateProduct(id, input); if (input.category !== undefined && input.category.trim()) return catalogService.saveCategoryFeedback(id, input.category.trim()); return product; }, onSuccess: (product) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useToggleProductActive() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, active }: { id: number; active: boolean }) => active ? catalogService.activateProduct(id) : catalogService.deactivateProduct(id), onSuccess: (product) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useCategories() { return useQuery({ queryKey: CATEGORIES_KEY, queryFn: () => catalogService.listCategories(), staleTime: 1000 * 60 * 60 }); }
export function useClassifyProduct() { const q = useQueryClient(); return useMutation({ mutationFn: (id: number) => catalogService.classifyProduct(id), onSuccess: ({ product }) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useAutoClassifyProducts() { const q = useQueryClient(); return useMutation({ mutationFn: (input: { limit?: number } = {}) => catalogService.autoClassifyProducts(input.limit), onSuccess: () => q.invalidateQueries({ queryKey: PRODUCTS_KEY }) }); }
export function useCategoryFeedback() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, category }: { id: number; category: string }) => catalogService.saveCategoryFeedback(id, category), onSuccess: (product) => { q.setQueryData(productKey(product.id), product); q.invalidateQueries({ queryKey: PRODUCTS_KEY }); } }); }
export function useOffers(productId: number) { return useQuery({ queryKey: offersKey(productId), queryFn: () => catalogService.listOffers(productId), enabled: Number.isFinite(productId) && productId > 0 }); }
export function useCreateOffer(productId: number) { const q = useQueryClient(); return useMutation({ mutationFn: (input: CreateOfferInput) => catalogService.createOffer(productId, input), onSuccess: () => q.invalidateQueries({ queryKey: offersKey(productId) }) }); }
export function useUpdateOffer(productId: number) { const q = useQueryClient(); return useMutation({ mutationFn: ({ offerId, input }: { offerId: number; input: UpdateOfferInput }) => catalogService.updateOffer(productId, offerId, input), onSuccess: () => q.invalidateQueries({ queryKey: offersKey(productId) }) }); }
export function useDeleteOffer(productId: number) { const q = useQueryClient(); return useMutation({ mutationFn: (offerId: number) => catalogService.deleteOffer(productId, offerId), onSuccess: () => q.invalidateQueries({ queryKey: offersKey(productId) }) }); }
