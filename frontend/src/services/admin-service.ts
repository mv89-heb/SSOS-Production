import { apiClient } from "./api-client";

export type AdminUser = {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "manager" | "employee";
  active: boolean;
  created_at: string;
};

export type AdminSupplier = {
  id: number;
  name: string;
  active: boolean;
  created_at: string;
};

export const adminService = {
  async listUsers() {
    const { data } = await apiClient.get<{ success: boolean; users: AdminUser[] }>("/api/users");
    return data.users;
  },
  async listSuppliers() {
    const { data } = await apiClient.get<{ success: boolean; suppliers: AdminSupplier[] }>("/api/catalog/suppliers");
    return data.suppliers;
  },
  async deactivateUser(id: number) {
    const { data } = await apiClient.post<{ success: boolean; user: AdminUser }>(`/api/admin/users/${id}/deactivate`);
    return data.user;
  },
  async deleteUser(id: number) {
    await apiClient.delete(`/api/admin/users/${id}`);
  },
  async deactivateSupplier(id: number) {
    const { data } = await apiClient.post<{ success: boolean; supplier: AdminSupplier }>(`/api/admin/suppliers/${id}/deactivate`);
    return data.supplier;
  },
  async deleteSupplier(id: number) {
    await apiClient.delete(`/api/admin/suppliers/${id}`);
  },
};
