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

import type { User, Tenant } from "@/types";

interface AuthMeResponse {
  user: User;
  tenant?: Tenant | null;
}

interface AuthContextType {
  user: User | null;
  tenant: Tenant | null;

  isLoading: boolean;
  isLoggingIn: boolean;
  loginError: string | null;
  isAuthenticated: boolean;

  login: (credentials: {
    email: string;
    password: string;
  }) => Promise<void>;

  logout: () => Promise<void>;

  checkAuthStatus: () => Promise<void>;
}


const AuthContext = createContext<AuthContextType | undefined>(
  undefined
);


export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {

  const [user, setUser] = useState<User | null>(null);

  const [tenant, setTenant] =
    useState<Tenant | null>(null);


  const [isLoading, setIsLoading] =
    useState(true);


  const [isLoggingIn, setIsLoggingIn] =
    useState(false);


  const [loginError, setLoginError] =
    useState<string | null>(null);


  const [isAuthenticated, setIsAuthenticated] =
    useState(false);


  const router = useRouter();
  const pathname = usePathname();



  /**
   * בדיקת Session מול Flask-Login
   *
   * Browser שולח HttpOnly Cookie אוטומטית
   */
  const checkAuthStatus = async () => {

    try {

      const response =
        await apiClient.get<AuthMeResponse>(
          "/auth/me"
        );


      if (response.data?.user) {

        setUser(response.data.user);

        setTenant(
          response.data.tenant ?? null
        );

        setIsAuthenticated(true);

      } else {

        setUser(null);
        setTenant(null);
        setIsAuthenticated(false);

      }


    } catch {

      setUser(null);
      setTenant(null);
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
   * הגנת נתיבים
   */
  useEffect(() => {

    if (isLoading) {
      return;
    }


    const isLoginPage =
      pathname.includes("/login");


    const isProtected =
      pathname.includes("/dashboard");


    if (
      isProtected &&
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
   *
   * Flask יוצר Session Cookie
   */
  const login = async (
    credentials: {
      email: string;
      password: string;
    }
  ) => {


    setIsLoggingIn(true);

    setLoginError(null);



    try {


      await apiClient.post(
        "/auth/login",
        credentials
      );


      await checkAuthStatus();



    } catch (error: any) {


      setUser(null);
      setTenant(null);

      setIsAuthenticated(false);


      const message =
        error?.friendlyMessage ||
        "שגיאה בהתחברות";


      setLoginError(message);


      throw error;



    } finally {


      setIsLoggingIn(false);


    }

  };




  /**
   * Logout
   */
  const logout = async () => {


    try {


      await apiClient.post(
        "/auth/logout"
      );


    } catch (error) {


      console.error(
        "Logout failed",
        error
      );


    } finally {


      setUser(null);

      setTenant(null);

      setIsAuthenticated(false);

      setLoginError(null);


      router.push("/login");


    }

  };



  return (

    <AuthContext.Provider
      value={{
        user,
        tenant,

        isLoading,
        isLoggingIn,
        loginError,

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
