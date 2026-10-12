"use client";

import { useMemo, useState } from "react";
import { Download, FileSpreadsheet, FileText } from "lucide-react";

function cleanCell(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

function csvEscape(value: string) {
  // Keep real negative numbers numeric in Excel, while guarding text cells
  // that could be interpreted as spreadsheet formulas.
  const isNumeric = value.trim() !== "" && Number.isFinite(Number(value));
  const safe = !isNumeric && /^[=+@\-\t\r]/.test(value) ? "'" + value : value;
  return '"' + safe.replace(/"/g, '""') + '"';
}

function visibleTables(): HTMLTableElement[] {
  return Array.from(document.querySelectorAll<HTMLTableElement>("main table")).filter((table) => {
    const rect = table.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && getComputedStyle(table).visibility !== "hidden";
  });
}

function tableRows(table: HTMLTableElement) {
  return Array.from(table.rows).filter((row) => {
    const rect = row.getBoundingClientRect();
    return rect.height > 0 && getComputedStyle(row).display !== "none";
  }).map((row) => Array.from(row.cells).map((cell) => cleanCell(cell.innerText || cell.textContent || "")));
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function safeFilename(value: string) {
  return value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-").replace(/\s+/g, "-").slice(0, 90) || "report";
}

export default function TableExportToolbar() {
  const [message, setMessage] = useState("");
  const pageTitle = useMemo(() => {
    if (typeof document === "undefined") return "דוח";
    return document.querySelector("main h1")?.textContent?.trim() || document.title || "דוח";
  }, []);

  function exportExcel() {
    const tables = visibleTables();
    if (!tables.length) {
      setMessage("במסך הזה לא נמצאו טבלאות לייצוא.");
      return;
    }
    const sections: string[] = [];
    tables.forEach((table, index) => {
      const heading = table.closest("section")?.querySelector("h2, h3")?.textContent?.trim()
        || table.getAttribute("aria-label")
        || `טבלה ${index + 1}`;
      sections.push(csvEscape(heading));
      tableRows(table).forEach((row) => sections.push(row.map(csvEscape).join(",")));
      sections.push("");
    });
    downloadFile("\uFEFF" + sections.join("\r\n"), `${safeFilename(pageTitle)}.csv`, "text/csv;charset=utf-8");
    setMessage(`יוצאו ${tables.length} טבלאות לפי התוצאות שמוצגות כעת, כולל הסינון הפעיל.`);
  }

  function exportPdf() {
    const tables = visibleTables();
    setMessage(tables.length
      ? "בחלון ההדפסה בחר/י ״שמירה כ-PDF״. התצוגה והסינון הנוכחיים נשמרים."
      : "לא נמצאו טבלאות; ניתן לשמור את הדוח הגלוי כ-PDF דרך חלון ההדפסה.");
    window.print();
  }

  return (
    <section aria-label="ייצוא דוחות" className="mb-4 flex flex-col gap-3 rounded-2xl border border-indigo-100 bg-white p-3 shadow-sm dark:border-indigo-950 dark:bg-slate-900 sm:flex-row sm:items-center sm:justify-between print:hidden">
      <div className="min-w-0">
        <div className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-100">
          <Download size={17} className="text-indigo-600" /> ייצוא דוחות מהמסך
        </div>
        <p className="mt-1 text-xs text-slate-500">הייצוא מתייחס לטבלאות שמוצגות כעת ולסינון הפעיל. אפשר לייצא את כולן יחד.</p>
        {message && <p role="status" className="mt-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">{message}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={exportExcel} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-700">
          <FileSpreadsheet size={16} /> Excel (CSV)
        </button>
        <button type="button" onClick={exportPdf} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
          <FileText size={16} /> PDF / הדפסה
        </button>
      </div>
    </section>
  );
}
