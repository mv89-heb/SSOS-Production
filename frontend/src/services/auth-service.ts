import { apiClient } from './api-client';
import { AuthResponse, User, Tenant } from '@/types';

export const authService = {
  /**
   * התחברות למערכת - ה-Cookie נשמר אוטומטית בדפדפן
   */
  login: async (credentials: Record<string, string>): Promise<AuthResponse> => {
    const { data } = await apiClient.post<AuthResponse>('/api/auth/login', credentials);
    return data;
  },

  /**
   * התנתקות - מוחק את ה-Session ב-Backend
   */
  logout: async (): Promise<{ success: boolean }> => {
    const { data } = await apiClient.post('/api/auth/logout');
    return data;
  },

  /**
   * שליפת נתוני המשתמש והטננט הנוכחי לפי ה-Session הקיים
   */
  getMe: async (): Promise<{ user: User; tenant: Tenant | null }> => {
    const { data } = await apiClient.get<{ success: boolean; user: User; tenant: Tenant | null }>('/api/auth/me');
    return { user: data.user, tenant: data.tenant };
  }
};
