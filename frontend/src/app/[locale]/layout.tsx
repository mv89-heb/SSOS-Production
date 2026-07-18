import type { Metadata } from "next";
import { Assistant } from "next/font/google";
import "../../globals.css"; // מיקום יחסי מעודכן
import QueryProvider from "@/providers/query-provider";
import { AuthProvider } from "@/providers/auth-provider";
import { ToastProvider } from "@/providers/toast-provider";
import { cn } from "@/lib/utils";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { NextIntlClientProvider } from "next-intl";

export const dynamic = "force-dynamic";

const assistant = Assistant({
  subsets: ["hebrew", "latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "SSOS - Smart Supplier Order System",
  description: "Enterprise Order Management Platform",
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  // ולידציה של השפה המבוקשת
  if (!routing.locales.includes(locale as any)) {
    notFound();
  }

  const messages = await getMessages();
  const dir = locale === "he" ? "rtl" : "ltr";

  return (
    <html lang={locale} dir={dir} className={assistant.variable}>
      <body className={cn("font-sans antialiased bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100")}>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <QueryProvider>
            <ToastProvider>
              <AuthProvider>{children}</AuthProvider>
            </ToastProvider>
          </QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
