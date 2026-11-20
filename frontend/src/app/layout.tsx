import type { Metadata } from "next";
import "./globals.css";
import QueryProvider from "@/providers/query-provider";
import { AuthProvider } from "@/providers/auth-provider";
import { ToastProvider } from "@/providers/toast-provider";
import ReminderPushRegistration from "@/components/reminder-push-registration";
import { cn } from "@/lib/utils";
import { ThemeProvider } from "@/providers/theme-provider";

export const dynamic = "force-dynamic";

const assistant = { variable: "" };

export const metadata: Metadata = {
  title: "SSOS - מערכת ניהול הזמנות ספקים",
  description: "SSOS — סביבת עבודה חכמה לניהול רכש, ספקים, מלאי ומסמכים.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl" className={assistant.variable} suppressHydrationWarning>
      <body className={cn("font-sans antialiased bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100")}>
        <ThemeProvider>
          <QueryProvider>
            <ToastProvider>
              <AuthProvider>
                {children}
                <ReminderPushRegistration />
              </AuthProvider>
            </ToastProvider>
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
