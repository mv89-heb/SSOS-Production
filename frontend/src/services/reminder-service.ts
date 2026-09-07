import { apiClient } from "./api-client";
import { Order } from "@/types";

export interface OrderReminder {
  order: Order;
  next_reminder_at: string | null;
}

export const reminderService = {
  getOpen: async (): Promise<OrderReminder[]> => {
    const { data } = await apiClient.get<{ success: boolean; reminders: OrderReminder[] }>("/api/order-reminders");
    return data.reminders;
  },

  activate: async (orderId: number): Promise<Order> => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/order-reminders/orders/${orderId}/activate`);
    return data.order;
  },

  complete: async (orderId: number): Promise<Order> => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/order-reminders/orders/${orderId}/complete`);
    return data.order;
  },

  snooze: async (orderId: number, minutes: number): Promise<Order> => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/order-reminders/orders/${orderId}/snooze`, { minutes });
    return data.order;
  },
};
