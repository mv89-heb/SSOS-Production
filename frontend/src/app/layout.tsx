import type { Metadata } from "next";
import "./globals.css";
import QueryProvider from "@/providers/query-provider";
import { AuthProvider } from "@/providers/auth-provider";
import { ToastProvider } from "@/providers/toast-provider";
import ReminderPushRegistration from "@/components/reminder-push-registration";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const assistant = { variable: "" };

export const metadata: Metadata = {
  title: "SSOS - מערכת ניהול הזמנות ספקים",
  description: "פלטפורמת ניהול הזמנות רכש",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl" className={assistant.variable}>
      <body className={cn("font-sans antialiased bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100")}>
        <QueryProvider>
          <ToastProvider>
            <AuthProvider>
              {children}
              <ReminderPushRegistration />
            </AuthProvider>
          </ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
