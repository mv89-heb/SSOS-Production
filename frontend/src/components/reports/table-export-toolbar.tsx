"use client";

import { useMemo, useState } from "react";
import { Download, FileSpreadsheet, FileText } from "lucide-react";

function cleanCell(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

function xmlEscape(value: string) {
  // SpreadsheetML is XML 1.0: strip forbidden control characters before escaping.
  return value
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\uFFFE\uFFFF]/g, "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
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
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function safeFilename(value: string) {
  return value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-").replace(/\s+/g, "-").slice(0, 90) || "report";
}

function worksheetName(value: string, index: number) {
  const cleaned = value.replace(/[\[\]:*?\/\\]/g, " ").trim().slice(0, 31);
  return cleaned || `Sheet${index + 1}`;
}

function createExcelXml(title: string, tables: HTMLTableElement[]) {
  const usedNames = new Set<string>();
  const worksheets = tables.map((table, index) => {
    const heading = table.closest("section")?.querySelector("h2, h3")?.textContent?.trim()
      || table.getAttribute("aria-label")
      || `טבלה ${index + 1}`;
    const rows = tableRows(table);
    const rowXml = rows.map((row, rowIndex) => {
      const cells = row.map((value) =>
        `<Cell${rowIndex === 0 ? ' ss:StyleID="Header"' : ""}><Data ss:Type="String">${xmlEscape(value)}</Data></Cell>`
      ).join("");
      return `<Row>${cells}</Row>`;
    }).join("");
    return `<Worksheet ss:Name="${xmlEscape(worksheetName(heading, index, usedNames))}"><Table>${rowXml}</Table></Worksheet>`;
  }).join("");
  return `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet" xmlns:html="http://www.w3.org/TR/REC-html40">
  <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office"><Title>${xmlEscape(title)}</Title></DocumentProperties>
  <Styles><Style ss:ID="Header"><Font ss:Bold="1"/><Interior ss:Color="#DDE6F7" ss:Pattern="Solid"/></Style></Styles>
  ${worksheets}
</Workbook>`;
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
    const xml = createExcelXml(pageTitle, tables);
    downloadFile("\uFEFF" + xml, `${safeFilename(pageTitle)}.xls`, "application/vnd.ms-excel;charset=utf-8");
    setMessage(`יוצאו ${tables.length} גיליונות Excel לפי הטבלאות המוצגות והסינון הפעיל.`);
  }

  function exportPdf() {
    const tables = visibleTables();
    setMessage(tables.length
      ? "נפתח חלון ההדפסה. בחר/י ״שמירה כ-PDF״ כדי לשמור את הדוח עם הסינון הנוכחי."
      : "לא נמצאו טבלאות; ניתן לשמור את הדוח הגלוי כ-PDF דרך חלון ההדפסה.");
    window.print();
  }

  return (
    <section aria-label="ייצוא דוחות" className="mb-4 flex flex-col gap-3 rounded-2xl border border-indigo-100 bg-white p-3 shadow-sm dark:border-indigo-950 dark:bg-slate-900 sm:flex-row sm:items-center sm:justify-between print:hidden">
      <div className="min-w-0">
        <div className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-100">
          <Download size={17} className="text-indigo-600" /> ייצוא דוחות מהמסך
        </div>
        <p className="mt-1 text-xs text-slate-500">הייצוא מתייחס לטבלאות שמוצגות כעת ולסינון הפעיל. כל טבלה מיוצאת לגיליון נפרד.</p>
        {message && <p role="status" className="mt-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">{message}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={exportExcel} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white hover:bg-emerald-700">
          <FileSpreadsheet size={16} /> Excel (.xls)
        </button>
        <button type="button" onClick={exportPdf} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
          <FileText size={16} /> PDF / הדפסה
        </button>
      </div>
    </section>
  );
}
