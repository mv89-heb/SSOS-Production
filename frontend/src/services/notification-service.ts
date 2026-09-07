import { apiClient } from "./api-client";

export interface NotificationItem {
  id: number;
  tenant_id: number;
  user_id: number;
  title: string;
  message: string | null;
  status: "unread" | "read" | "archived";
  created_at: string;
  read_at: string | null;
}

export const notificationService = {
  get: async (unreadOnly = false): Promise<NotificationItem[]> => {
    const { data } = await apiClient.get<{ success: boolean; notifications: NotificationItem[] }>(
      `/api/notifications${unreadOnly ? "?unread_only=true" : ""}`,
    );
    return data.notifications;
  },
  markRead: async (notificationId: number): Promise<NotificationItem> => {
    const { data } = await apiClient.post<{ success: boolean; notification: NotificationItem }>(
      `/api/notifications/${notificationId}/read`,
    );
    return data.notification;
  },
};
