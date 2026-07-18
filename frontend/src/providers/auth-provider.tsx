"use client";

import { createContext, useContext, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, usePathname } from "next/navigation";
import { authService } from "@/services/auth-service";
import { resetCsrfToken } from "@/services/api-client";
import { User, Tenant } from "@/types";

interface AuthContextValue {
  user: User | null;
  tenant: Tenant | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: { email: string; password: string }) => void;
  isLoggingIn: boolean;
  loginError: unknown;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Dashboard routes require a session; the login page must not redirect.
const PUBLIC_PATHS = ["/login"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();

  const {
    data,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["auth-user"],
    queryFn: authService.getMe,
    retry: false,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  useEffect(() => {
    if (!isLoading && isError && !PUBLIC_PATHS.includes(pathname)) {
      router.push("/login");
    }
  }, [isError, isLoading, pathname, router]);

  const loginMutation = useMutation({
    mutationFn: authService.login,
    onSuccess: (data) => {
      if (data.success) {
        // The login response only contains `user`, not `tenant` — invalidate
        // so the next render fetches the full /me payload instead of caching
        // a partial one.
        queryClient.invalidateQueries({ queryKey: ["auth-user"] });
        router.push("/dashboard");
      }
    },
  });

  const logout = async () => {
    await authService.logout();
    resetCsrfToken();
    queryClient.setQueryData(["auth-user"], null);
    queryClient.clear();
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user: data?.user ?? null,
        tenant: data?.tenant ?? null,
        isLoading,
        isAuthenticated: !!data?.user && !isError,
        login: loginMutation.mutate,
        isLoggingIn: loginMutation.isPending,
        loginError: loginMutation.error,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
