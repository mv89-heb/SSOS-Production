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
 const router=useRouter();
 const {user}=useAuth();
 const canManage=permissions.canManageImports(user);
 const initial=useMemo(()=>JSON.stringify(INITIAL_ORDERS,null,2),[]);
 const [json,setJson]=useState(initial);
 const [busy,setBusy]=useState(false);
 const [preview,setPreview]=useState<any>(null);
 const [previewedJson,setPreviewedJson]=useState("");
 const [message,setMessage]=useState("");
 const [error,setError]=useState("");

 function parsedOrders(){
  const orders=JSON.parse(json);
  if(!Array.isArray(orders)||!orders.length)throw new Error("נדרשת רשימת הזמנות תקינה.");
  return orders;
 }

 async function previewOrders(){
  setBusy(true);setError("");setMessage("");setPreview(null);setPreviewedJson("");
  try{
   const orders=parsedOrders();
   const {data}=await apiClient.post("/api/historical-document-import/manual-orders/preview",{orders});
   setPreview(data);
   setPreviewedJson(json);
  }catch(e: unknown){
   const ex=e as {response?:{data?:{message?:string}};message?:string};
   setError(ex.response?.data?.message??ex.message??"בדיקת הנתונים נכשלה.");
  }finally{setBusy(false);}
 }

 function applySupplierSuggestion(orderIndex:number,supplierId:number){
  try{
   const orders=parsedOrders();
   orders[orderIndex-1].supplier_id=supplierId;
   setJson(JSON.stringify(orders,null,2));
   setPreview(null);setPreviewedJson("");setMessage("");
  }catch(e: unknown){
   setError(e instanceof Error?e.message:"לא ניתן לעדכן את שיוך הספק.");
  }
 }

 function applyProductSuggestion(orderIndex:number,lineIndex:number,productId:number){
  try{
   const orders=parsedOrders();
   orders[orderIndex-1].items[lineIndex-1].product_id=productId;
   setJson(JSON.stringify(orders,null,2));
   setPreview(null);setPreviewedJson("");setMessage("");
  }catch(e: unknown){
   setError(e instanceof Error?e.message:"לא ניתן לעדכן את שיוך המוצר.");
  }
 }

 async function importOrders(){
  setBusy(true);setError("");setMessage("");
  try{
   if(!preview||previewedJson!==json)throw new Error("יש לבצע בדיקת התאמות מחדש לפני הייבוא.");
   if(preview.summary.unmatched_suppliers>0)throw new Error("יש לשייך את כל הספקים לפני הייבוא. בחר הצעה מתאימה ובצע בדיקה מחדש.");
   const orders=parsedOrders();
   const {data}=await apiClient.post("/api/historical-document-import/manual-orders",{name:"הזמנות היסטוריות פעמית ושמאי 2026-11-18",orders});
   setMessage("נשמרו "+data.orders.length+" הזמנות היסטוריות באצווה "+data.batch.id+". לא נוצרו הזמנות פעילות ולא עודכן מלאי.");
   setPreview(null);setPreviewedJson("");
  }catch(e: unknown){
   const ex=e as {response?:{data?:{message?:string}};message?:string};
   setError(ex.response?.data?.message??ex.message??"ייבוא ההזמנות נכשל.");
  }finally{setBusy(false);}
 }

 if(!canManage)return <div className="rounded-xl border bg-white p-8 text-center text-sm text-slate-500">נדרשת הרשאת מנהל כדי לייבא היסטוריית הזמנות.</div>;
 const summary=preview?.summary;
 const canImport=!!preview&&previewedJson===json&&summary?.unmatched_suppliers===0&&!busy;

 return <main dir="rtl" className="mx-auto w-full max-w-6xl space-y-5 p-4 sm:p-6">
  <button onClick={()=>router.push("/dashboard/settings/historical-import")} className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900"><ArrowRight size={18}/> חזרה לייבוא היסטורי</button>
  <header>
   <h1 className="text-2xl font-bold text-slate-900">ייבוא היסטוריית הזמנות ידנית</h1>
   <p className="mt-1 text-sm text-slate-500">14 רשומות היסטוריות · טווח התאריכים 24.05.2026–08.11.2026 · ספקים פעמית ושמאי.</p>
  </header>
  <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
   <div className="flex gap-2"><ShieldAlert size={19} className="mt-0.5 shrink-0"/>
    <div><strong>היסטוריה בלבד — ללא שינוי במלאי, במחירים, בקבלות או בהזמנות הפעילות.</strong>
     <p className="mt-1 leading-6">יש לבדוק התאמת ספק ומוצר לפני הייבוא. התאמות אוטומטיות מתבצעות רק לפי שם מדויק; הצעות דומות דורשות בחירה מפורשת. כמויות ללא יחידה או ללא כמות נשמרות לתיעוד אך אינן משמשות לחישוב הצריכה.</p>
    </div>
   </div>
  </section>
  <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
   <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-bold">נתוני הייבוא · 14 הזמנות</h2><span className="text-xs text-slate-500">ניתן לערוך לפני הבדיקה</span></div>
   <textarea value={json} onChange={e=>{setJson(e.target.value);setPreview(null);setPreviewedJson("");setMessage("");}} spellCheck={false} className="min-h-[420px] w-full rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-6 text-slate-900 focus:border-indigo-500 focus:outline-none"/>
   <div className="flex flex-wrap gap-2">
    <button onClick={previewOrders} disabled={busy} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-bold text-indigo-800 disabled:opacity-50"><Search size={17}/>{busy?"בודק...":"בדוק התאמות לפני ייבוא"}</button>
    <button onClick={importOrders} disabled={!canImport} className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"><Upload size={17}/>{busy?"שומר...":"אשר וייבא הזמנות היסטוריות"}</button>
   </div>
   {preview&&previewedJson===json&&<p className="text-xs text-emerald-700">הבדיקה מתייחסת בדיוק לתוכן שמופיע בעורך. כל שינוי מחייב בדיקה חוזרת.</p>}
   {message&&<p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 size={17}/>{message}</p>}
   {error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
  </section>

  {preview&&<>
   <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-center gap-2"><ClipboardCheck size={19} className="text-indigo-600"/><h2 className="font-bold">תוצאות בדיקת התאמות</h2></div>
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
     {[
      ["הזמנות",summary.order_count],
      ["שורות פריטים",summary.line_count],
      ["התאמות מוצר",summary.exact_product_matches],
      ["מוצרים לא משויכים",summary.unmatched_products],
      ["ספקים לא משויכים",summary.unmatched_suppliers],
      ["כמויות חסרות",summary.missing_quantities],
      ["יחידות לא מאומתות",summary.unverified_units],
      ["קרטונים ללא גודל אריזה",summary.cartons_missing_pack_size],
     ].map(([label,value])=><div key={label} className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-xl font-extrabold tabular-nums">{Number(value).toLocaleString("he-IL")}</div></div>)}
    </div>
    {summary.unmatched_suppliers>0&&<p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">יש לשייך את כל הספקים לפני הייבוא. לחץ על הצעת ספק כדי להוסיף את מזהה הספק לנתונים, ואז הרץ בדיקה מחדש.</p>}
    {summary.unmatched_products>0&&<p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">שורות מוצר שלא ישויכו לקטלוג יישמרו כהיסטוריה, אך לא ישתתפו בתחזית הצריכה. בחר הצעות מתאימות לכל שורה שניתן לזהות.</p>}
    {summary.unverified_units>0&&<p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">יחידות לא מאומתות לא יומרו אוטומטית ליחידות מלאי. יש לציין quantity_unit רק כאשר היחידה ידועה בוודאות.</p>}
   </section>

   <section className="space-y-3">
    {preview.orders.map((order:any)=><article key={order.order_index} className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
     <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 p-3">
      <div><div className="font-bold">הזמנה {order.order_index} · {order.supplier_name}</div><div className="text-xs text-slate-500">{order.order_date}</div></div>
      <span className={order.supplier_matched?"text-xs font-bold text-emerald-700":"text-xs font-bold text-red-700"}>{order.supplier_matched?"ספק משויך":"ספק דורש שיוך"}</span>
     </header>
     {!order.supplier_matched&&order.supplier_candidates?.length>0&&<div className="border-b border-slate-100 p-3"><p className="mb-2 text-xs font-semibold text-slate-600">הצעות ספק — בחר רק אם זו אותה ישות עסקית:</p><div className="flex flex-wrap gap-2">{order.supplier_candidates.map((candidate:any)=><button key={candidate.supplier_id} onClick={()=>applySupplierSuggestion(order.order_index,candidate.supplier_id)} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs font-bold text-indigo-800 hover:bg-indigo-100">{candidate.supplier_name} · ID {candidate.supplier_id} · {Math.round(candidate.score*100)}%</button>)}</div></div>}
     <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-right text-xs">
       <thead className="bg-white text-slate-500"><tr><th className="px-3 py-2">תיאור מקור</th><th className="px-3 py-2">כמות</th><th className="px-3 py-2">יחידה</th><th className="px-3 py-2">התאמת מוצר</th></tr></thead>
       <tbody>{order.items.map((line:any)=><tr key={line.line_index} className="border-t border-slate-100">
        <td className="px-3 py-2 font-semibold">{line.description}</td>
        <td className="px-3 py-2 tabular-nums">{line.quantity??"לא צוינה"}</td>
        <td className="px-3 py-2">{line.quantity_unit==="unverified"?"לא מאומתת":line.quantity_unit==="carton"?"קרטון":line.quantity_unit==="piece"||line.quantity_unit==="unit"?"יחידה":"—"}</td>
        <td className="px-3 py-2">
         {line.product_id?<span className="font-bold text-emerald-700">{line.product_name} · ID {line.product_id} ({line.product_match})</span>:<div className="space-y-2">
          <span className="font-semibold text-amber-700">לא משויך</span>
          {line.product_candidates?.length>0&&<div className="flex flex-wrap gap-1.5">{line.product_candidates.map((candidate:any)=><button key={candidate.product_id} onClick={()=>applyProductSuggestion(order.order_index,line.line_index,candidate.product_id)} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-semibold text-slate-700 hover:border-indigo-300 hover:bg-indigo-50">{candidate.product_name} · ID {candidate.product_id} · {Math.round(candidate.score*100)}%</button>)}</div>}
         </div>}
        </td>
       </tr>)}</tbody>
      </table>
     </div>
    </article>)}
   </section>
   <p className="text-xs leading-5 text-slate-500">{preview.message} הצעות דמיון אינן התאמות אוטומטיות; רק לחיצה מפורשת תוסיף product_id או supplier_id לנתוני הייבוא.</p>
  </>}
 </main>;
}
