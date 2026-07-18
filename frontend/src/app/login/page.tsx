'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuth } from '@/providers/auth-provider';
import { Lock, Mail, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// סכימת וולידציה עם Zod
const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

function loginErrorMessage(error: unknown): string {
  const status = (error as { response?: { status?: number; data?: { message?: string } } })?.response?.status;
  const serverMessage = (error as { response?: { data?: { message?: string } } })?.response?.data?.message;

  if (status === 401) return "Invalid email or password.";
  if (status === 429) return "Too many attempts. Please wait a moment and try again.";
  if (status === 400 && serverMessage) return serverMessage; // e.g. missing/expired CSRF token
  if (status && status >= 500) return "Server error. Please try again shortly.";
  return "Could not sign in. Please check your connection and try again.";
}

export default function LoginPage() {
  const { login, isLoggingIn, loginError } = useAuth();
  
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = (data: LoginFormValues) => {
    login(data);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md space-y-8 rounded-2xl bg-white p-10 shadow-xl shadow-slate-200/50">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">SSOS</h1>
          <p className="mt-2 text-sm text-slate-500">Sign in to manage your supplier orders</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-6">
          <div className="space-y-4">
            {/* Email Field */}
            <div>
              <label className="block text-sm font-medium text-slate-700">Email Address</label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Mail size={18} />
                </div>
                <input
                  {...register('email')}
                  type="email"
                  className={cn(
                    "block w-full rounded-lg border border-slate-200 py-3 pl-10 pr-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all",
                    errors.email && "border-red-500 focus:border-red-500 focus:ring-red-100"
                  )}
                  placeholder="name@company.com"
                />
              </div>
              {errors.email && <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>}
            </div>

            {/* Password Field */}
            <div>
              <label className="block text-sm font-medium text-slate-700">Password</label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Lock size={18} />
                </div>
                <input
                  {...register('password')}
                  type="password"
                  className={cn(
                    "block w-full rounded-lg border border-slate-200 py-3 pl-10 pr-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all",
                    errors.password && "border-red-500 focus:border-red-500 focus:ring-red-100"
                  )}
                  placeholder="••••••••"
                />
              </div>
              {errors.password && <p className="mt-1 text-xs text-red-500">{errors.password.message}</p>}
            </div>
          </div>

          {/* Error Message from Server — distinguishes the actual cause instead
              of a single generic string, since a masked message here is what
              made the CSRF-token bug undiagnosable from the UI. */}
          {Boolean(loginError) && (
            <div className="rounded-lg bg-red-50 p-3 text-center text-sm font-medium text-red-600">
              {loginErrorMessage(loginError)}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoggingIn}
            className="flex w-full items-center justify-center rounded-lg bg-primary py-3 text-sm font-semibold text-white shadow-lg shadow-primary/30 transition-all hover:bg-primary/90 focus:ring-2 focus:ring-primary/20 active:scale-[0.98] disabled:opacity-70"
          >
            {isLoggingIn ? (
              <Loader2 className="animate-spin" size={20} />
            ) : (
              "Sign In"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
