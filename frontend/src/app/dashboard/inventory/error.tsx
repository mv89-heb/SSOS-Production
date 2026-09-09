"use client";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div dir="rtl" className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-900 dark:border-red-900 dark:bg-red-950/20 dark:text-red-200">
      <h2 className="font-black">לא ניתן לטעון את מסך המלאי</h2>
      <p className="mt-1 text-sm">נסה לרענן. הנתונים לא שונו.</p>
      <button type="button" onClick={() => reset()} className="mt-4 rounded-xl bg-red-700 px-4 py-2 text-sm font-bold text-white">נסה שוב</button>
    </div>
  );
}
