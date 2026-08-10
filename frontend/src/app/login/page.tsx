'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import Link from 'next/link';
import { useAuth } from '@/providers/auth-provider';
import { Lock, Mail, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// סכימת וולידציה עם Zod
const loginSchema = z.object({
  email: z.string().email('כתובת אימייל לא תקינה'),
  password: z.string().min(8, 'הסיסמה חייבת להכיל לפחות 8 תווים'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

function loginErrorMessage(error: unknown): string {
  const response = (error as { response?: { status?: number; data?: { message?: string } } })?.response;
  const status = response?.status;
  const serverMessage = response?.data?.message;

  if (status === 401) return "אימייל או סיסמה שגויים.";
  if (status === 429) return "יותר מדי ניסיונות. נסה שוב בעוד רגע.";
  if (status && status >= 500) return "שגיאת שרת. נסה שוב בעוד מספר רגעים.";
  if (!response) return "לא ניתן היה להגיע לשרת. בדוק את החיבור לאינטרנט, או שהאתר מוגדר כראוי.";
  if (serverMessage) return serverMessage; // e.g. missing/expired CSRF token
  return "ההתחברות נכשלה. בדוק את החיבור ונסה שוב.";
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
          <p className="mt-2 text-sm text-slate-500">התחבר כדי לנהל את הזמנות הספקים שלך</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-6">
          <div className="space-y-4">
            {/* Email Field */}
            <div>
              <label className="block text-sm font-medium text-slate-700">כתובת אימייל</label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                  <Mail size={18} />
                </div>
                <input
                  {...register('email')}
                  type="email"
                  className={cn(
                    "block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all",
                    errors.email && "border-red-500 focus:border-red-500 focus:ring-red-100"
                  )}
                  placeholder="name@company.com"
                />
              </div>
              {errors.email && <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>}
            </div>

            {/* Password Field */}
            <div>
              <label className="block text-sm font-medium text-slate-700">סיסמה</label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                  <Lock size={18} />
                </div>
                <input
                  {...register('password')}
                  type="password"
                  className={cn(
                    "block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all",
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
              "התחברות"
            )}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500">
          אין לך חשבון?{' '}
          <Link href="/register" className="font-medium text-primary hover:underline">
            צור חשבון
          </Link>
        </p>
      </div>
    </div>
  );
}
