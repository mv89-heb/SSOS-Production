import Sidebar from "@/components/layout/sidebar";
import Header from "@/components/layout/header";
import CommandPalette from "@/components/layout/command-palette";

// אזור הניהול תלוי בנתוני משתמש/שרת ולכן אינו נשמר כ-Static HTML.
export const dynamic = "force-dynamic";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div dir="rtl" className="relative flex min-h-screen flex-row overflow-hidden bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -right-32 -top-40 h-96 w-96 rounded-full bg-indigo-200/20 blur-3xl dark:bg-indigo-900/10" />
        <div className="absolute -bottom-40 left-1/3 h-96 w-96 rounded-full bg-violet-200/15 blur-3xl dark:bg-violet-900/10" />
      </div>

      {/* RTL layout: the primary navigation is intentionally on the right. */}
      <Sidebar />

      <div className="relative flex min-w-0 flex-1 flex-col">
        <Header />

        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1440px] px-3 py-4 sm:px-5 sm:py-5 lg:px-7 lg:py-7">
            {children}
          </div>
        </main>
      </div>

      <CommandPalette />
    </div>
  );
}
