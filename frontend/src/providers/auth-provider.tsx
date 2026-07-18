"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";

import { useRouter, usePathname } from "next/navigation";
import apiClient from "@/services/api-client";

// להתאים את הנתיב לפי ה-Type הקיים אצלך בפרויקט
import { User } from "@/types/user";


interface AuthMeResponse {
  user: User;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  login: (credentials: {
    email: string;
    password: string;
  }) => Promise<void>;

  logout: () => Promise<void>;

  checkAuthStatus: () => Promise<void>;
}


const AuthContext = createContext<AuthContextType | undefined>(undefined);


export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null);

  const [isLoading, setIsLoading] = useState(true);

  const [isAuthenticated, setIsAuthenticated] =
    useState(false);


  const router = useRouter();
  const pathname = usePathname();


  /**
   * בדיקת Session מול Flask-Login
   *
   * אין Token
   * אין localStorage
   *
   * הדפדפן שולח HttpOnly Cookie אוטומטית
   */
  const checkAuthStatus = async () => {
    try {
      const response =
        await apiClient.get<AuthMeResponse>(
          "/auth/me"
        );


      if (response.data?.user) {
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


  /**
   * טעינה ראשונית
   */
  useEffect(() => {
    checkAuthStatus();
  }, []);



  /**
   * ניהול Redirect
   */
  useEffect(() => {

    if (isLoading) {
      return;
    }


    const isLoginPage =
      pathname.includes("/login");


    const isProtectedPage =
      pathname.includes("/dashboard");


    if (
      isProtectedPage &&
      !isAuthenticated
    ) {
      router.push("/login");
    }


    if (
      isLoginPage &&
      isAuthenticated
    ) {
      router.push("/dashboard");
    }


  }, [
    pathname,
    isAuthenticated,
    isLoading,
    router,
  ]);



  /**
   * Login
   */
  const login = async (
    credentials: {
      email: string;
      password: string;
    }
  ) => {

    setIsLoading(true);


    try {

      await apiClient.post(
        "/auth/login",
        credentials
      );


      await checkAuthStatus();


    } catch (error) {

      setUser(null);
      setIsAuthenticated(false);
      setIsLoading(false);

      throw error;
    }
  };



  /**
   * Logout
   */
  const logout = async () => {

    setIsLoading(true);


    try {

      await apiClient.post(
        "/auth/logout"
      );


    } catch (error) {

      console.error(
        "Logout failed:",
        error
      );


    } finally {

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

  const context =
    useContext(AuthContext);


  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider"
    );
  }


  return context;
}
