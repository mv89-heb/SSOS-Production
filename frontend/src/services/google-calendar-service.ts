import { apiClient } from "./api-client";

export interface GoogleCalendarConnection {
  id: number;
  google_email: string | null;
  calendar_id: string;
  calendar_name: string | null;
  connected: boolean;
}

export interface GoogleCalendarStatus {
  configured: boolean;
  connection: GoogleCalendarConnection | null;
  calendars: Array<{ id: string; name: string }>;
}

export const googleCalendarService = {
  status: async (): Promise<GoogleCalendarStatus> => {
    const { data } = await apiClient.get<{ success: boolean } & GoogleCalendarStatus>("/api/integrations/google-calendar/status");
    return data;
  },
  connectUrl: () => `${apiClient.defaults.baseURL}/api/integrations/google-calendar/connect`,
  disconnect: async () => {
    await apiClient.post("/api/integrations/google-calendar/disconnect");
  },
  selectCalendar: async (calendar_id: string) => {
    const { data } = await apiClient.post<{ success: boolean; connection: GoogleCalendarConnection }>("/api/integrations/google-calendar/calendar", { calendar_id });
    return data.connection;
  },
};
