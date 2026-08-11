import { apiClient } from "./api-client";

export type AdminUser = { id: number; email: string; full_name: string; role: "admin" | "manager" | "employee"; active: boolean; created_at: string };
export type AdminSupplier = { id: number; name: string; contact_name?: string | null; email?: string | null; phone?: string | null; phone2?: string | null; customer_number?: string | null; delivery_days?: string | null; order_days?: string | null; active: boolean; created_at: string };
export type AdminProduct = { id: number; name: string; sku?: string | null; active: boolean; current_price: number; supplier_id: number };
export type AdminOrder = { id: number; order_number: string; status: string; final_total: number; created_at: string; notes?: string | null };
export type AdminImport = { id: number; filename: string; status: string; row_count?: number | null; created_at: string };
export type AdminAuditLog = { id: number; action: string; title: string; metadata?: Record<string, unknown>; user_id?: number | null; created_at: string; hash?: string | null };

export const adminService = {
  async listUsers() { const { data } = await apiClient.get<{ success: boolean; users: AdminUser[] }>("/api/users"); return data.users; },
  async updateUser(id: number, payload: Record<string, unknown>) { const { data } = await apiClient.put<{ success: boolean; user: AdminUser }>(`/api/users/${id}`, payload); return data.user; },
  async activateUser(id: number) { const { data } = await apiClient.post<{ success: boolean; user: AdminUser }>(`/api/admin/users/${id}/activate`); return data.user; },
  async deactivateUser(id: number) { const { data } = await apiClient.post<{ success: boolean; user: AdminUser }>(`/api/admin/users/${id}/deactivate`); return data.user; },
  async deleteUser(id: number) { await apiClient.delete(`/api/admin/users/${id}`); },

  async listSuppliers() { const { data } = await apiClient.get<{ success: boolean; suppliers: AdminSupplier[] }>("/api/catalog/suppliers"); return data.suppliers; },
  async updateSupplier(id: number, payload: Record<string, unknown>) { const { data } = await apiClient.put<{ success: boolean; supplier: AdminSupplier }>(`/api/catalog/suppliers/${id}`, payload); return data.supplier; },
  async activateSupplier(id: number) { const { data } = await apiClient.post<{ success: boolean; supplier: AdminSupplier }>(`/api/admin/suppliers/${id}/activate`); return data.supplier; },
  async deactivateSupplier(id: number) { const { data } = await apiClient.post<{ success: boolean; supplier: AdminSupplier }>(`/api/admin/suppliers/${id}/deactivate`); return data.supplier; },
  async deleteSupplier(id: number) { await apiClient.delete(`/api/admin/suppliers/${id}`); },

  async listProducts() { const { data } = await apiClient.get<{ success: boolean; products: AdminProduct[] }>("/api/catalog/products", { params: { active: "false", limit: 500 } }); return data.products; },
  async updateProduct(id: number, payload: Record<string, unknown>) { const { data } = await apiClient.put<{ success: boolean; product: AdminProduct }>(`/api/catalog/products/${id}`, payload); return data.product; },
  async deleteProduct(id: number) { await apiClient.delete(`/api/admin/products/${id}`); },

  async listOrders() { const { data } = await apiClient.get<{ success: boolean; orders: AdminOrder[] }>("/api/orders", { params: { limit: 200, offset: 0 } }); return data.orders; },
  async getOrder(id: number) { const { data } = await apiClient.get<{ success: boolean; order: AdminOrder }>(`/api/admin/orders/${id}`); return data.order; },
  async updateOrder(id: number, payload: { status?: string; notes?: string | null }) { const { data } = await apiClient.patch<{ success: boolean; order: AdminOrder }>(`/api/admin/orders/${id}`, payload); return data.order; },
  async deleteOrder(id: number) { await apiClient.delete(`/api/admin/orders/${id}`); },

  async listImports() { const { data } = await apiClient.get<{ success: boolean; sessions: AdminImport[] }>("/api/imports", { params: { limit: 200 } }); return data.sessions; },
  async deleteImport(id: number) { await apiClient.delete(`/api/admin/imports/${id}`); },

  async listAudit(params?: { limit?: number; offset?: number; action?: string }) {
    const { data } = await apiClient.get<{ success: boolean; logs: AdminAuditLog[]; audit_chain_valid: boolean; first_broken_log_id?: number | null }>("/api/admin/audit", { params });
    return data;
  },
};
