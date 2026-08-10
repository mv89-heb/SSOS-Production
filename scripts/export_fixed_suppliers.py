import pandas as pd
import os

EXCEL_FILE = "טלפונים ספקי מזון.xls"
OUTPUT_FILE = "Fixed_Suppliers_Master.xlsx"

def generate_fixed_suppliers_excel():
    print("🧹 מעבד ומנקה את נתוני הספקים והטלפונים...")
    
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ שגיאה: לא מצאתי את הקובץ {EXCEL_FILE}.")
        return

    df = pd.read_excel(EXCEL_FILE, sheet_name='גיליון1', header=3)
    
    cleaned_records = []
    
    for _, row in df.iterrows():
        sup_name = row.get('ספק')
        if pd.isna(sup_name) or str(sup_name).strip() == '' or str(sup_name).strip() == 'ספק':
            continue
            
        sup_name = str(sup_name).strip()
        phone1 = str(row.get('טלפון-1', '')).strip() if pd.notna(row.get('טלפון-1')) else ''
        phone2 = str(row.get('טלפון-2', '')).strip() if pd.notna(row.get('טלפון-2')) else ''
        mobile = str(row.get('נייד', '')).strip() if pd.notna(row.get('נייד')) else ''
        contact = str(row.get('שם איש קשר', '')).strip() if pd.notna(row.get('שם איש קשר')) else ''
        
        phone1 = phone1 if phone1 and phone1 != 'nan' else ''
        phone2 = phone2 if phone2 and phone2 != 'nan' else ''
        mobile = mobile if mobile and mobile != 'nan' else ''
        contact = contact if contact and contact != 'nan' else ''
        
        cleaned_records.append({
            'שם ספק': sup_name,
            'טלפון ראשי': phone1,
            'טלפון נוסף': phone2,
            'נייד': mobile,
            'איש קשר': contact
        })
        
    master_df = pd.DataFrame(cleaned_records)
    master_df.to_excel(OUTPUT_FILE, index=False)
    
    print(f"\n🎉 קובץ האקסל המעודכן לספקים נוצר בהצלחה!")
    print(f"📁 שם הקובץ: {OUTPUT_FILE}")
    print(f"📊 סה\"כ ספקים שנמצאו ונוקו: {len(master_df)}")

if __name__ == "__main__":
    generate_fixed_suppliers_excel()