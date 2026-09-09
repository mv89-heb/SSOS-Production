export default function Loading() {
  return (
    <div dir="rtl" className="space-y-5" aria-busy="true" aria-label="טוען מסך מלאי">
      <div className="h-40 animate-pulse rounded-3xl bg-slate-200 dark:bg-slate-800" />
      <div className="h-64 animate-pulse rounded-3xl bg-slate-200 dark:bg-slate-800" />
      <div className="h-80 animate-pulse rounded-3xl bg-slate-200 dark:bg-slate-800" />
    </div>
  );
}
