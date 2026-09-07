"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { reminderService } from "@/services/reminder-service";

const REMINDERS_KEY = ["order-reminders"] as const;
const orderKey = (id: number) => ["order", id] as const;

export function useOpenReminders() {
  return useQuery({
    queryKey: REMINDERS_KEY,
    queryFn: reminderService.getOpen,
  });
}

export function useActivateOrderReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: number) => reminderService.activate(orderId),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.id), order);
      queryClient.invalidateQueries({ queryKey: REMINDERS_KEY });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}
