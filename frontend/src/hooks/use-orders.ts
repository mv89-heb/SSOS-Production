"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { orderService, UpdateDraftOrderInput } from "@/services/order-service";
import { CreateOrderInput } from "@/types";

const ORDERS_KEY = ["orders"] as const;
const orderKey = (id: number) => ["order", id] as const;

export function useOrders(status?: string) {
  return useQuery({
    queryKey: status ? [...ORDERS_KEY, status] : ORDERS_KEY,
    queryFn: () => orderService.getOrders(status),
  });
}

export function useOrder(id: number) {
  return useQuery({
    queryKey: orderKey(id),
    queryFn: () => orderService.getOrderById(id),
    enabled: Number.isFinite(id),
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateOrderInput) => orderService.createOrder(input),
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
      queryClient.setQueryData(orderKey(order.id), order);
    },
  });
}

export function useUpdateDraftOrder(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateDraftOrderInput) => orderService.updateDraftOrder(id, payload),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(id), order);
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
    },
  });
}

export function useDeleteOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => orderService.deleteOrder(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: orderKey(id) });
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
      queryClient.invalidateQueries({ queryKey: ["order-reminders"] });
    },
  });
}

export function useSubmitOrder(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => orderService.submitOrder(id),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(id), order);
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
    },
  });
}

export function useApproveOrder(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => orderService.approveOrder(id),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(id), order);
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
    },
  });
}

export function useRejectOrder(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reason?: string) => orderService.rejectOrder(id, reason),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(id), order);
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
    },
  });
}

export function useMarkSentOrder(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => orderService.markSent(id),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(id), order);
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
    },
  });
}

export function useCompleteOrder(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => orderService.markCompleted(id),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(id), order);
      queryClient.invalidateQueries({ queryKey: ORDERS_KEY });
    },
  });
}
