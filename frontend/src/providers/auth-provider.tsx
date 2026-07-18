"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import apiClient from "@/services/api-client";

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: any) => Promise<void>;
  logout: () => Promise<void>;
  checkAuthStatus: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  
  const router = useRouter();
  const pathname = usePathname();

  // משיכת נתוני המשתמש המחובר מתוך עוגיית ה-Session
  const checkAuthStatus = async () => {
    try {
      const response = await apiClient.get("/auth/me");
      if (response.data && response.data.user) {
        setUser(response.data.user);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (error) {
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  // ריצה ראשונית בעת עליית האפליקציה
  useEffect(() => {
    checkAuthStatus();
  }, []);

  // הגנת נתיבים מבוקרת (Client-side Route Protection) המונעת לולאות הפניה
  useEffect(() => {
    if (!isLoading) {
      const isProtectedRoute = pathname.includes("/dashboard");
      const isLoginRoute = pathname.includes("/login");

      if (isProtectedRoute && !isAuthenticated) {
        router.push("/login");
      } else if (isLoginRoute && isAuthenticated) {
        router.push("/dashboard");
      }
    }
  }, [pathname, isAuthenticated, isLoading, router]);

  // זרם התחברות (Login)
  const login = async (credentials: any) => {
    setIsLoading(true);
    try {
      // 1. השרת מקבל את הפרטים ובמידה והם תקינים, מייצר ומחזיר עוגיית סשן HttpOnly
      await apiClient.post("/auth/login", credentials);
      
      // 2. קריאה מיידית לעדכון ה-State של המשתמש בעקבות ההתחברות
      await checkAuthStatus();
    } catch (error) {
      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);
      throw error;
    }
  };

  // זרם התנתקות (Logout)
  const logout = async () => {
    setIsLoading(true);
    try {
      // השרת מבצע ניקוי של הסשן ומורה לדפדפן למחוק את העוגייה
      await apiClient.post("/auth/logout");
    } catch (error) {
      console.error("Logout request failed:", error);
    } finally {
      // ניקוי המצב בצד הלקוח ומעבר לעמוד ההתחברות
      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);
      router.push("/login");
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated,
        login,
        logout,
        checkAuthStatus,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
