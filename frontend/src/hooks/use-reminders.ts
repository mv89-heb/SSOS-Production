"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { reminderService } from "@/services/reminder-service";

const REMINDERS_KEY = ["order-reminders"] as const;
const orderKey = (id: number) => ["order", id] as const;

function useReminderMutation(mutationFn: (orderId: number) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (order) => {
      const typedOrder = order as { id: number };
      queryClient.setQueryData(orderKey(typedOrder.id), order);
      queryClient.invalidateQueries({ queryKey: REMINDERS_KEY });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

export function useOpenReminders() {
  return useQuery({
    queryKey: REMINDERS_KEY,
    queryFn: reminderService.getOpen,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useReminderConfiguration(orderId: number, enabled = true) {
  return useQuery({
    queryKey: ["order-reminder-configuration", orderId],
    queryFn: () => reminderService.getConfiguration(orderId),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useActivateOrderReminder() {
  return useReminderMutation(reminderService.activate);
}

export function useCreateManualOrderReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, reminderAt, note }: { orderId: number; reminderAt: string; note: string }) =>
      reminderService.createManual(orderId, reminderAt, note),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.id), order);
      queryClient.invalidateQueries({ queryKey: REMINDERS_KEY });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

export function useCompleteOrderReminder() {
  return useReminderMutation(reminderService.complete);
}

export function useSnoozeOrderReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, minutes }: { orderId: number; minutes: number }) => reminderService.snooze(orderId, minutes),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.id), order);
      queryClient.invalidateQueries({ queryKey: REMINDERS_KEY });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}
