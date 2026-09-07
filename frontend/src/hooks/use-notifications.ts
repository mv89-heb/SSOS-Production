"use client";

import { useQuery } from "@tanstack/react-query";
import { notificationService } from "@/services/notification-service";

export function useUnreadNotifications() {
  return useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => notificationService.get(true),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 10_000,
  });
}
