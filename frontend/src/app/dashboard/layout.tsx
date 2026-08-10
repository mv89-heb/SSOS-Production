import Sidebar from "@/components/layout/sidebar";
import Header from "@/components/layout/header";
import CommandPalette from "@/components/layout/command-palette";

// מניעת שמירה סטטית של אזור הניהול
export const dynamic = "force-dynamic";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6">
          <div className="mx-auto max-w-7xl">
            {children}
          </div>
        </main>
      </div>
      <CommandPalette />
    </div>
  );
}
