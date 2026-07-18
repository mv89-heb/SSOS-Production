"use client";

import { useQuery } from "@tanstack/react-query";
import { auditService } from "@/services/audit-service";

export function useAuditLogs(limit = 100, offset = 0) {
  return useQuery({
    queryKey: ["audit-logs", limit, offset],
    queryFn: () => auditService.listLogs(limit, offset),
  });
}
