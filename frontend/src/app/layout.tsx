import type { Metadata } from "next";
import { Assistant } from "next/font/google";
import "./globals.css";
import QueryProvider from "@/providers/query-provider";
import { AuthProvider } from "@/providers/auth-provider";
import { ToastProvider } from "@/providers/toast-provider";
import { cn } from "@/lib/utils";
import { cookies } from "next/headers";
import { NextIntlClientProvider } from "next-intl";

// הגדרה קריטית המונעת מ-Next.js להציג דפים סטטיים ישנים ומכריחה טעינה דינמית על בסיס העוגיות של המשתמש
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

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const locale = cookieStore.get("NEXT_LOCALE")?.value || "he";
  const dir = locale === "he" ? "rtl" : "ltr";

  let messages;
  try {
    messages = (await import(`../messages/${locale}.json`)).default;
  } catch (e) {
    messages = (await import(`../messages/he.json`)).default;
  }

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
