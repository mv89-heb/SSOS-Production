import { apiClient } from "./api-client";
import { AuditLogEntry } from "@/types";

export const auditService = {
  // Requires manager/admin — the backend returns 403 for employees, which the
  // shared axios interceptor already turns into a "No permission" toast.
  listLogs: async (limit = 100, offset = 0) => {
    const { data } = await apiClient.get<{ success: boolean; logs: AuditLogEntry[] }>("/api/audit", {
      params: { limit, offset },
    });
    return data.logs;
  },
};
