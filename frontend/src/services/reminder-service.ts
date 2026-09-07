import { apiClient } from "./api-client";
import { Order } from "@/types";

export interface OrderReminder {
  order: Order;
  next_reminder_at: string | null;
}

export interface ReminderConfiguration {
  has_supplier_rules: boolean;
  supplier_name: string;
}

export const reminderService = {
  getOpen: async (): Promise<OrderReminder[]> => {
    const { data } = await apiClient.get<{ success: boolean; reminders: OrderReminder[] }>("/api/order-reminders");
    return data.reminders;
  },

  getConfiguration: async (orderId: number): Promise<ReminderConfiguration> => {
    const { data } = await apiClient.get<{ success: boolean } & ReminderConfiguration>(`/api/order-reminders/orders/${orderId}/configuration`);
    return { has_supplier_rules: data.has_supplier_rules, supplier_name: data.supplier_name };
  },

  activate: async (orderId: number): Promise<Order> => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/order-reminders/orders/${orderId}/activate`);
    return data.order;
  },

  createManual: async (orderId: number, reminderAt: string, note: string): Promise<Order> => {
    const { data } = await apiClient.post<{ success: boolean; order: Order }>(`/api/order-reminders/orders/${orderId}/manual`, {
      reminder_at: reminderAt,
      note,
    });
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
