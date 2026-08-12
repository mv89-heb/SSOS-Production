import Sidebar from "@/components/layout/sidebar";
import Header from "@/components/layout/header";
import CommandPalette from "@/components/layout/command-palette";
import { AutoClassifyButton } from "@/components/catalog/auto-classify-button";

export const dynamic = "force-dynamic";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div dir="rtl" className="min-h-screen min-w-0 bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -right-32 -top-40 h-96 w-96 rounded-full bg-indigo-200/20 blur-3xl dark:bg-indigo-900/10" />
        <div className="absolute -bottom-40 left-1/3 h-96 w-96 rounded-full bg-violet-200/15 blur-3xl dark:bg-violet-900/10" />
      </div>

      <Sidebar />

      <div className="min-h-screen min-w-0 md:mr-64">
        <Header />
        <main className="min-h-[calc(100vh-4rem)] min-w-0 overflow-x-hidden">
          <div className="mx-auto w-full max-w-[1440px] min-w-0 px-3 py-4 sm:px-5 sm:py-5 lg:px-7 lg:py-7">
            <AutoClassifyButton />
            {children}
          </div>
        </main>
      </div>

      <CommandPalette />
    </div>
  );
}
