'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import Link from 'next/link';
import { useAuth } from '@/providers/auth-provider';
import { RegisterPayload } from '@/types';
import { Lock, Mail, Loader2, User as UserIcon, Building2, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

const registerSchema = z
  .object({
    mode: z.enum(['new', 'join']),
    full_name: z.string().trim().min(2, 'שם מלא הוא שדה חובה'),
    email: z.string().email('כתובת אימייל לא תקינה'),
    password: z
      .string()
      .min(8, 'הסיסמה חייבת להכיל לפחות 8 תווים')
      .refine((v) => /[A-Za-z]/.test(v), 'הסיסמה חייבת לכלול אות')
      .refine((v) => /\d/.test(v), 'הסיסמה חייבת לכלול ספרה'),
    confirm_password: z.string(),
    tenant_name: z.string().trim().optional(),
    tenant_slug: z.string().trim().optional(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'הסיסמאות אינן תואמות',
    path: ['confirm_password'],
  })
  .refine((data) => data.mode !== 'new' || !!data.tenant_name, {
    message: 'שם החברה הוא שדה חובה',
    path: ['tenant_name'],
  })
  .refine((data) => data.mode !== 'join' || !!data.tenant_slug, {
    message: 'קוד החברה הוא שדה חובה',
    path: ['tenant_slug'],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

function registerErrorMessage(error: unknown): string {
  const err = error as { response?: { status?: number; data?: { error?: string; message?: string } }; message?: string };
  const response = err?.response;
  const status = response?.status;
  const code = response?.data?.error;
  const serverMessage = response?.data?.message;

  if (code === 'email_already_registered') return 'כתובת האימייל הזו כבר רשומה במערכת.';
  if (code === 'tenant_already_exists') return 'חברה בשם הזה כבר קיימת.';
  if (code === 'tenant_not_found') return 'לא נמצאה חברה עם הקוד הזה — בדוק אותו ונסה שוב.';
  if (code === 'weak_password') return serverMessage || 'הסיסמה חייבת להכיל לפחות 8 תווים, אות וספרה.';
  if (code === 'invalid_email') return 'אנא הזן כתובת אימייל תקינה.';
  if (code === 'full_name_required') return 'שם מלא הוא שדה חובה.';
  if (status === 429) return 'יותר מדי ניסיונות. נסה שוב בעוד רגע.';
  if (status && status >= 500) return 'שגיאת שרת. נסה שוב בעוד מספר רגעים.';
  // No HTTP response at all usually means the request never reached the
  // backend — a network error or a CORS rejection (misconfigured
  // NEXT_PUBLIC_API_URL / CORS_ORIGINS), not a data problem.
  if (!response) return 'לא ניתן היה להגיע לשרת. בדוק את החיבור לאינטרנט, או שהאתר מוגדר כראוי.';
  // Any other 4xx (e.g. an expired/missing CSRF token) — show the
  // backend's own message instead of hiding it behind a generic string.
  if (serverMessage) return serverMessage;
  return 'יצירת החשבון נכשלה. בדוק את הפרטים ונסה שוב.';
}

export default function RegisterPage() {
  const { register: doRegister, isRegistering, registerError } = useAuth();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { mode: 'new' },
  });

  const mode = watch('mode');

  const onSubmit = (data: RegisterFormValues) => {
    const payload: RegisterPayload =
      data.mode === 'new'
        ? { email: data.email, password: data.password, full_name: data.full_name, tenant_name: data.tenant_name! }
        : { email: data.email, password: data.password, full_name: data.full_name, tenant_slug: data.tenant_slug! };
    doRegister(payload);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md space-y-8 rounded-2xl bg-white p-10 shadow-xl shadow-slate-200/50">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">SSOS</h1>
          <p className="mt-2 text-sm text-slate-500">צור חשבון חדש</p>
        </div>

        {/* Mode toggle */}
        <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
          <button
            type="button"
            onClick={() => setValue('mode', 'new')}
            className={cn(
              'flex items-center justify-center gap-2 rounded-md py-2 text-sm font-medium transition-all',
              mode === 'new' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            )}
          >
            <Building2 size={16} />
            חברה חדשה
          </button>
          <button
            type="button"
            onClick={() => setValue('mode', 'join')}
            className={cn(
              'flex items-center justify-center gap-2 rounded-md py-2 text-sm font-medium transition-all',
              mode === 'join' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            )}
          >
            <Users size={16} />
            הצטרפות לחברה
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-4">
            {/* Full name */}
            <div>
              <label className="block text-sm font-medium text-slate-700">שם מלא</label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                  <UserIcon size={18} />
                </div>
                <input
                  {...register('full_name')}
                  type="text"
                  className={cn(
                    'block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all',
                    errors.full_name && 'border-red-500 focus:border-red-500 focus:ring-red-100'
                  )}
                  placeholder="ישראל ישראלי"
                />
              </div>
              {errors.full_name && <p className="mt-1 text-xs text-red-500">{errors.full_name.message}</p>}
            </div>

            {/* Email */}
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
                    'block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all',
                    errors.email && 'border-red-500 focus:border-red-500 focus:ring-red-100'
                  )}
                  placeholder="name@company.com"
                />
              </div>
              {errors.email && <p className="mt-1 text-xs text-red-500">{errors.email.message}</p>}
            </div>

            {/* Company name / slug — depends on mode */}
            {mode === 'new' ? (
              <div>
                <label className="block text-sm font-medium text-slate-700">שם החברה</label>
                <div className="relative mt-1">
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                    <Building2 size={18} />
                  </div>
                  <input
                    {...register('tenant_name')}
                    type="text"
                    className={cn(
                      'block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all',
                      errors.tenant_name && 'border-red-500 focus:border-red-500 focus:ring-red-100'
                    )}
                    placeholder='שם החברה שלך בע"מ'
                  />
                </div>
                {errors.tenant_name && <p className="mt-1 text-xs text-red-500">{errors.tenant_name.message}</p>}
                <p className="mt-1 text-xs text-slate-400">תהיה מנהל המערכת של החברה החדשה הזו.</p>
              </div>
            ) : (
              <div>
                <label className="block text-sm font-medium text-slate-700">קוד חברה</label>
                <div className="relative mt-1">
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                    <Users size={18} />
                  </div>
                  <input
                    {...register('tenant_slug')}
                    type="text"
                    className={cn(
                      'block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all',
                      errors.tenant_slug && 'border-red-500 focus:border-red-500 focus:ring-red-100'
                    )}
                    placeholder="acme-co"
                  />
                </div>
                {errors.tenant_slug && <p className="mt-1 text-xs text-red-500">{errors.tenant_slug.message}</p>}
                <p className="mt-1 text-xs text-slate-400">בקש את קוד החברה ממנהל המערכת שלך.</p>
              </div>
            )}

            {/* Password */}
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
                    'block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all',
                    errors.password && 'border-red-500 focus:border-red-500 focus:ring-red-100'
                  )}
                  placeholder="••••••••"
                />
              </div>
              {errors.password && <p className="mt-1 text-xs text-red-500">{errors.password.message}</p>}
            </div>

            {/* Confirm password */}
            <div>
              <label className="block text-sm font-medium text-slate-700">אימות סיסמה</label>
              <div className="relative mt-1">
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                  <Lock size={18} />
                </div>
                <input
                  {...register('confirm_password')}
                  type="password"
                  className={cn(
                    'block w-full rounded-lg border border-slate-200 py-3 pr-10 pl-3 text-slate-900 placeholder-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/20 sm:text-sm transition-all',
                    errors.confirm_password && 'border-red-500 focus:border-red-500 focus:ring-red-100'
                  )}
                  placeholder="••••••••"
                />
              </div>
              {errors.confirm_password && <p className="mt-1 text-xs text-red-500">{errors.confirm_password.message}</p>}
            </div>
          </div>

          {Boolean(registerError) && (
            <div className="rounded-lg bg-red-50 p-3 text-center text-sm font-medium text-red-600">
              {registerErrorMessage(registerError)}
            </div>
          )}

          <button
            type="submit"
            disabled={isRegistering}
            className="flex w-full items-center justify-center rounded-lg bg-primary py-3 text-sm font-semibold text-white shadow-lg shadow-primary/30 transition-all hover:bg-primary/90 focus:ring-2 focus:ring-primary/20 active:scale-[0.98] disabled:opacity-70"
          >
            {isRegistering ? <Loader2 className="animate-spin" size={20} /> : 'יצירת חשבון'}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500">
          כבר יש לך חשבון?{' '}
          <Link href="/login" className="font-medium text-primary hover:underline">
            התחבר
          </Link>
        </p>
      </div>
    </div>
  );
}
