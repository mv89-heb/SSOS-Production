"use client";

import { useMemo, useState } from "react";
import { Check, ChevronDown, Copy, MessageCircle, Send } from "lucide-react";
import { Button } from "@/components/ui/button";

type OrderItem = { sku?: string | null; product_name: string; quantity: number; unit_price: number; total_price: number };
type ShareOrder = {
  order_number: string;
  supplier_name: string;
  currency: string;
  items: OrderItem[];
  notes?: string | null;
};

type TemplateKey = "formal" | "short" | "delivery";
const ORGANIZATION_NAME = "ישיבת אוהבי ירושלים - ראשית";

const templates: Record<TemplateKey, { label: string; build: (order: ShareOrder) => string }> = {
  formal: {
    label: "הזמנה רשמית",
    build: order => `שלום ${order.supplier_name},\n\nמטעם ${ORGANIZATION_NAME}, מצורפת הזמנת רכש ${order.order_number}.\n\nנשמח לאישור קבלת ההזמנה ולתיאום אספקה.${order.notes ? `\n\nהערות:\n${order.notes}` : ""}\n\nתודה רבה,\n${ORGANIZATION_NAME}`,
  },
  short: {
    label: "הודעה קצרה",
    build: order => `שלום, מטעם ${ORGANIZATION_NAME}: הזמנת רכש ${order.order_number} מוכנה לאישור. אשמח לאישור קבלה ותיאום אספקה.${order.notes ? `\nהערה: ${order.notes}` : ""}\nתודה.`,
  },
  delivery: {
    label: "תיאום אספקה",
    build: order => `שלום, כאן ${ORGANIZATION_NAME}, לגבי הזמנה ${order.order_number}. נשמח לתאם מועד אספקה. אנא אשרו קבלת ההזמנה וציינו מועד אספקה אפשרי.${order.notes ? `\nהערות: ${order.notes}` : ""}\nתודה.`,
  },
};

function buildDetailedMessage(order: ShareOrder) {
  const lines = order.items.map((item, index) => `${index + 1}. ${item.product_name} | כמות: ${item.quantity}`);
  return `שלום ${order.supplier_name},\n\nמטעם ${ORGANIZATION_NAME}, הזמנת רכש ${order.order_number}\n\n${lines.join("\n")}${order.notes ? `\n\nהערות:\n${order.notes}` : ""}\n\nנשמח לאישור קבלת ההזמנה ולתיאום אספקה.\n\nתודה רבה,\n${ORGANIZATION_NAME}`;
}

export function WhatsAppOrderShare({ order }: { order: ShareOrder }) {
  const [template, setTemplate] = useState<TemplateKey>("formal");
  const [copied, setCopied] = useState(false);
  const message = useMemo(() => templates[template].build(order), [template, order]);

  const openWhatsApp = (text = message) => {
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank", "noopener,noreferrer");
  };

  const copyMessage = async () => {
    await navigator.clipboard.writeText(message);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <section className="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 shadow-sm dark:border-emerald-900/60 dark:bg-emerald-950/20">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white"><MessageCircle size={18} /></span><div><h2 className="font-black text-slate-900 dark:text-white">שליחה ב־WhatsApp</h2><p className="text-xs text-slate-500 dark:text-slate-400">הודעה מטעם {ORGANIZATION_NAME}, ללא סכומי הזמנה.</p></div></div>
        </div>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(templates) as TemplateKey[]).map(key => <button key={key} type="button" onClick={() => setTemplate(key)} className={`rounded-xl px-3 py-2 text-xs font-extrabold transition ${template === key ? "bg-emerald-600 text-white" : "bg-white text-slate-600 hover:bg-emerald-100 dark:bg-slate-900 dark:text-slate-300"}`}>{templates[key].label}</button>)}
          <button type="button" onClick={() => openWhatsApp(buildDetailedMessage(order))} className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-extrabold text-white hover:bg-slate-800 dark:bg-white dark:text-slate-900"><ChevronDown size={14} className="inline rotate-[-90deg]" /> פירוט מלא</button>
        </div>
      </div>
      <textarea readOnly value={message} onChange={() => undefined} rows={7} className="mt-4 w-full resize-y rounded-xl border border-emerald-200 bg-white p-3 text-sm leading-6 text-slate-700 outline-none dark:border-emerald-900/60 dark:bg-slate-950 dark:text-slate-200" aria-label="תוכן הודעת WhatsApp" />
      <div className="mt-3 flex flex-wrap gap-2">
        <Button onClick={() => openWhatsApp()}><Send size={16} /> פתיחת WhatsApp</Button>
        <Button variant="secondary" onClick={() => void copyMessage()}>{copied ? <Check size={16} /> : <Copy size={16} />} {copied ? "הועתק" : "העתקת הודעה"}</Button>
      </div>
    </section>
  );
}
