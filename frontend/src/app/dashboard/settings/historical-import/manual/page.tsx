"use client";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, Loader2, ShieldAlert, Upload } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";

const INITIAL_ORDERS = [
{order_date:"2026-07-21",supplier_name:"פעמית",items:[["אובלי קלקר 9",4],["מרקיות קלקר",6],["צלחות קלקר 9",5],["כפיות",4],["כוסות קשיח",2],["מגבת נייר 165מ'",10,"קרטונים","carton"],["פח שובך",10]]},
{order_date:"2026-08-10",supplier_name:"פעמית",items:[["אובלי קלקר 9",10],["מרקיות קלקר",10],["צלחות קלקר 9",10],["צלחות קלקר 7",10],["מגבת נייר 165מ'",10,"קרטונים","carton"]]},
{order_date:"2026-08-25",supplier_name:"פעמית",items:[["כוסות פלסטיק קשיח",2],["לפטניות",1],["מרקיות פלסטיק",2],["אקונומיקה",6],["סבון כלים",12],["כפפות לטקס M",12],["כפפות לטקס L",12]]},
{order_date:"2026-08-25",supplier_name:"פעמית",order_reference:"2026-08-25-פעמית-ב",items:[["מזלג קרם",11],["מפיות",2],["ניילון נצמד",2],["רדיד אלומיניום",1],["קסרול",2],["קערות פירות",2]]},
{order_date:"2026-09-07",supplier_name:"פעמית",items:[["פח שובך 50ל'",10],["נייר ניגוב",6],["נייר טואלט צץ-רץ",5],["תבנית גסטרונום 50יח'",10],["צלחות קלקר 9",10]]},
{order_date:"2026-09-22",supplier_name:"פעמית",items:[["מגבת צץ-רץ",5],["נייר חתוך",5],["מגבת נייר",8],["טואלט פטנט",5],["כוס יהלום",5],["כוסות נייר",8]]},
{order_date:"2026-10-11",supplier_name:"פעמית",items:[["צלחת 9 קלקר",11],["כוסות נייר",4],["קערת פירות",2],["צלחת 7 פלסטיק",5]]},
{order_date:"2026-10-15",supplier_name:"פעמית",items:[["כוסות נייר",4],["צלחת 9 קלקר",5],["סכינים",5],["מרקית קלקר",8],["מגבת נייר 165מ'",10,"קרטונים","carton"]]},
{order_date:"2026-10-29",supplier_name:"פעמית",items:[["צלחת 9 קלקר",11],["תבנית גסטרונום",3],["מגבת נייר 165מ'",6,"קרטונים","carton"],["סבון ידיים ורוד",1],["נוזל לניקוי כלים",1]]},
{order_date:"2026-11-08",supplier_name:"פעמית",items:[["כוסות נייר חמה",8],["כוסות קרה",5],["צלחת קלקר 9",5],["סכינים קרם",5],["מגבת נייר 165מ'",10,"קרטונים","carton"]]},
{order_date:"2026-05-24",supplier_name:"שמאי",items:[["אובלי קלקר 9",1],["מזלג קרם",11],["כפיות תה",2],["כוס קשיח",2],["כוס פשוטה",3],["צלחת 7",2],["צלחת 9",2]]},
{order_date:"2026-10-25",supplier_name:"שמאי",items:[["שקיות אשפה 75/85 קומפקט",1],["מרקיות קלקר ארוז 1000",4],["צלחות קלקר 9 ארוז 500",5],["כוסות נייר 8B",2]]},
{order_date:"2026-10-28",supplier_name:"שמאי",items:[["שקיות אשפה קומפקט",null],["מרקיות קלקר",null],["צלחות קלקר 9",null],["כוסות קרטון 8oz",null],["שקיות אשפה 50/70",null],["כפות ומזלגות קרם",null]]},
{order_date:"2026-11-01",supplier_name:"שמאי",items:[["כפות",5],["מזלגות",5],["צלחות קלקר 9",5],["מרקיות קלקר",5],["כף הגשה",1]]}
].map(o=>({...o,items:o.items.map(([description,quantity,unit,quantity_unit])=>({description,quantity,...(unit?{unit}:{}),...(quantity_unit?{quantity_unit}:{})}))}));

export default function ManualHistoricalImportPage() {
 const router=useRouter(); const {user}=useAuth(); const canManage=permissions.canManageImports(user);
 const initial=useMemo(()=>JSON.stringify(INITIAL_ORDERS,null,2),[]);
 const [json,setJson]=useState(initial); const [busy,setBusy]=useState(false); const [message,setMessage]=useState(""); const [error,setError]=useState("");
 async function importOrders(){
  setBusy(true);setError("");setMessage("");
  try{
   const orders=JSON.parse(json);
   if(!Array.isArray(orders)||!orders.length)throw new Error("נדרשת רשימת הזמנות תקינה.");
   const {data}=await apiClient.post("/api/historical-document-import/manual-orders",{name:"הזמנות היסטוריות פעמית ושמאי 2026-11-18",orders});
   setMessage("נשמרו "+data.orders.length+" הזמנות היסטוריות באצווה "+data.batch.id+". לא נוצרו הזמנות פעילות ולא עודכן מלאי.");
  }catch(e){
   const ex=e;setError(ex.response?.data?.message??ex.message??"ייבוא ההזמנות נכשל.");
  }finally{setBusy(false);}
 }
 if(!canManage)return <div className="rounded-xl border bg-white p-8 text-center text-sm text-slate-500">נדרשת הרשאת מנהל כדי לייבא היסטוריית הזמנות.</div>;
 return <main dir="rtl" className="mx-auto w-full max-w-5xl space-y-5 p-4 sm:p-6">
  <button onClick={()=>router.push("/dashboard/settings/historical-import")} className="inline-flex items-center gap-2 text-sm text-slate-600"><ArrowRight size={18}/> חזרה לייבוא היסטורי</button>
  <header><h1 className="text-2xl font-bold text-slate-900">ייבוא היסטוריית הזמנות ידנית</h1><p className="mt-1 text-sm text-slate-500">14 הזמנות שבוצעו בפועל אצל פעמית ושמאי, כולל שמירת שורות ללא כמויות ידועות.</p></header>
  <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><div className="flex gap-2"><ShieldAlert size={19} className="mt-0.5 shrink-0"/><div><strong>היסטוריה בלבד — ללא שינוי במלאי או בהזמנות הפעילות.</strong><p className="mt-1">הספקים והמוצרים משויכים רק בהתאמה מדויקת לקטלוג. שורות ללא כמות נשמרות כחסרות. יחידות שלא צוינו מסומנות לבדיקה ואינן משמשות לחישוב צריכה עד לאימות. כמויות הקרטונים המפורשות נשמרות כקרטונים, אך המרה תחייב גודל אריזה מאומת בקטלוג.</p></div></div></section>
  <section className="space-y-3 rounded-xl border bg-white p-4 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-bold">נתוני הייבוא · 14 הזמנות</h2><span className="text-xs text-slate-500">ניתן לערוך לפני הייבוא</span></div>
   <textarea value={json} onChange={e=>setJson(e.target.value)} spellCheck={false} className="min-h-[420px] w-full rounded-lg border bg-slate-50 p-3 font-mono text-xs leading-6"/>
   <button onClick={importOrders} disabled={busy} className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{busy?<Loader2 size={17} className="animate-spin"/>:<Upload size={17}/>} {busy?"מייבא...":"אשר וייבא 14 הזמנות היסטוריות"}</button>
   {message&&<p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 size={17}/>{message}</p>}
   {error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
  </section>
 </main>;
}
