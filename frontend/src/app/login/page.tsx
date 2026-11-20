'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import Link from 'next/link';
import { useAuth } from '@/providers/auth-provider';
import { Lock, Mail, Loader2, ShieldCheck, Sparkles, Boxes, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import SsosLogo from '@/components/brand/ssos-logo';

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
  if (serverMessage) return serverMessage;
  return "ההתחברות נכשלה. בדוק את החיבור ונסה שוב.";
}

export default function LoginPage() {
  const { login, isLoggingIn, loginError } = useAuth();
  const { register, handleSubmit, formState: { errors } } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });
  const onSubmit = (data: LoginFormValues) => login(data);

  return (
    <main dir="rtl" className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#071b2c] px-4 py-8 text-slate-900">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -right-40 -top-48 h-[34rem] w-[34rem] rounded-full bg-teal-500/15 blur-[100px] ssos-glow" />
        <div className="absolute -bottom-56 -left-32 h-[38rem] w-[38rem] rounded-full bg-blue-500/15 blur-[110px]" />
        <div className="absolute inset-0 opacity-[0.08]" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,.16) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.16) 1px, transparent 1px)', backgroundSize: '48px 48px' }} />
        <div className="absolute left-[18%] top-[16%] h-64 w-64 rounded-full border border-teal-200/10 ssos-orbit" />
        <div className="absolute left-[calc(18%+7.5rem)] top-[calc(16%+7.5rem)] h-4 w-4 rounded-full bg-teal-300/60 shadow-[0_0_32px_8px_rgba(94,234,212,.25)]" />
      </div>

      <div className="relative z-10 mx-auto grid w-full max-w-6xl items-center gap-8 lg:grid-cols-[1.05fr_.95fr] lg:gap-16">
        <section className="hidden text-white lg:block">
          <div className="ssos-mark-arrive"><SsosLogo size="lg" light /></div>
          <div className="ssos-rise mt-10 max-w-xl">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-teal-200/20 bg-teal-200/10 px-4 py-2 text-xs font-bold text-teal-100"><Sparkles size={14} /> סביבת עבודה חכמה לניהול רכש</p>
            <h1 className="text-4xl font-black leading-[1.2] tracking-tight xl:text-5xl">כל שרשרת הרכש.<br /><span className="text-teal-300">בשליטה אחת.</span></h1>
            <p className="mt-5 max-w-lg text-base leading-8 text-slate-300">ניהול הזמנות, ספקים, מלאי ומסמכים — בחוויית עבודה אחת מדויקת, שקופה ונוחה.</p>
          </div>
          <div className="ssos-rise mt-10 grid max-w-xl grid-cols-3 gap-3">
            {[{ icon: Boxes, title: 'רכש ומלאי' }, { icon: TrendingUp, title: 'תובנות ונתונים' }, { icon: ShieldCheck, title: 'בקרה ואמינות' }].map(({ icon: Icon, title }) => <div key={title} className="rounded-2xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur-sm"><Icon className="mb-3 h-5 w-5 text-teal-300" /><p className="text-xs font-bold text-slate-200">{title}</p></div>)}
          </div>
          <p className="mt-12 text-xs font-medium tracking-wide text-slate-500">SMART SUPPLIER ORDER SYSTEM <span className="mx-2 text-teal-500">•</span> SSOS</p>
        </section>

        <section className="ssos-rise w-full rounded-[2rem] border border-white/60 bg-white p-6 shadow-[0_32px_100px_rgba(0,0,0,.35)] sm:p-10">
          <div className="mb-8 flex flex-col items-center text-center lg:items-start lg:text-right">
            <div className="mb-5 lg:hidden"><SsosLogo size="lg" /></div>
            <div className="mb-3 hidden lg:block"><span className="rounded-full bg-teal-50 px-3 py-1.5 text-xs font-extrabold text-teal-800">כניסה מאובטחת</span></div>
            <h2 className="text-2xl font-black tracking-tight text-[#10263d] sm:text-3xl">ברוכים השבים</h2>
            <p className="mt-2 text-sm text-slate-500">התחברו כדי להמשיך לנהל את פעילות הרכש</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div>
              <label className="mb-2 block text-sm font-bold text-slate-700">כתובת אימייל</label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4 text-slate-400"><Mail size={18} /></span>
                <input {...register('email')} type="email" autoComplete="username" className={cn("block w-full rounded-xl border border-slate-200 bg-slate-50 py-3.5 pl-4 pr-11 text-slate-900 placeholder:text-slate-400 transition focus:border-teal-600 focus:bg-white focus:outline-none focus:ring-4 focus:ring-teal-600/10", errors.email && "border-red-500 focus:border-red-500 focus:ring-red-100")} placeholder="name@company.com" />
              </div>
              {errors.email && <p className="mt-1.5 text-xs font-semibold text-red-600">{errors.email.message}</p>}
            </div>
            <div>
              <label className="mb-2 block text-sm font-bold text-slate-700">סיסמה</label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-4 text-slate-400"><Lock size={18} /></span>
                <input {...register('password')} type="password" autoComplete="current-password" className={cn("block w-full rounded-xl border border-slate-200 bg-slate-50 py-3.5 pl-4 pr-11 text-slate-900 placeholder:text-slate-400 transition focus:border-teal-600 focus:bg-white focus:outline-none focus:ring-4 focus:ring-teal-600/10", errors.password && "border-red-500 focus:border-red-500 focus:ring-red-100")} placeholder="••••••••" />
              </div>
              {errors.password && <p className="mt-1.5 text-xs font-semibold text-red-600">{errors.password.message}</p>}
            </div>
            {Boolean(loginError) && <div role="alert" className="rounded-xl border border-red-100 bg-red-50 p-3 text-center text-sm font-semibold text-red-700">{loginErrorMessage(loginError)}</div>}
            <button type="submit" disabled={isLoggingIn} className="group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-l from-[#126f78] to-[#168b89] py-3.5 text-sm font-extrabold text-white shadow-lg shadow-teal-900/20 transition duration-200 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-teal-900/25 focus:outline-none focus:ring-4 focus:ring-teal-600/20 active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-70">
              {isLoggingIn ? <><Loader2 className="h-5 w-5 animate-spin" /> מתחבר...</> : <>כניסה למערכת <span className="transition-transform group-hover:-translate-x-1">←</span></>}
            </button>
          </form>
          <div className="mt-7 flex items-center justify-between border-t border-slate-100 pt-5 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5"><ShieldCheck size={14} className="text-teal-700" /> חיבור מאובטח</span>
            <Link href="/register" className="font-bold text-teal-800 transition hover:text-teal-600 hover:underline">יצירת חשבון</Link>
          </div>
        </section>
      </div>
      <div className="absolute bottom-4 left-0 right-0 z-10 text-center text-[10px] font-medium tracking-wider text-slate-500">SSOS · SMART SUPPLIER ORDER SYSTEM</div>
    </main>
  );
}
