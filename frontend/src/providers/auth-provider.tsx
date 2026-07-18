"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";

import {
  useRouter,
  usePathname,
} from "next/navigation";

import apiClient from "@/services/api-client";

import type { User } from "@/types";

interface AuthMeResponse {
  user: User;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  login: (
    credentials: {
      email: string;
      password: string;
    }
  ) => Promise<void>;

  logout: () => Promise<void>;

  checkAuthStatus: () => Promise<void>;
}


const AuthContext =
  createContext<AuthContextType | undefined>(
    undefined
  );


export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {

  const [user, setUser] =
    useState<User | null>(null);

  const [isLoading, setIsLoading] =
    useState(true);

  const [isAuthenticated, setIsAuthenticated] =
    useState(false);


  const router = useRouter();
  const pathname = usePathname();



  /**
   * בדיקת Session מול Flask-Login
   */
  const checkAuthStatus =
    async () => {

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


      } catch {

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
   * הגנת Routes
   */
  useEffect(() => {

    if (isLoading) {
      return;
    }


    const isProtectedRoute =
      pathname.includes("/dashboard");


    const isLoginRoute =
      pathname.includes("/login");



    if (
      isProtectedRoute &&
      !isAuthenticated
    ) {

      router.push("/login");

    }


    if (
      isLoginRoute &&
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
