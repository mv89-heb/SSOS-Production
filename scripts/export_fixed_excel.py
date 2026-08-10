import pandas as pd
import os

FILE_PATH = "מחירים - ספקי מזון.xls"
OUTPUT_PATH = "Fixed_Prices_Master.xlsx"

def generate_fixed_excel():
    print("🧹 מתחיל בעיבוד וניקוי הנתונים מכל הלשוניות...")
    xls = pd.ExcelFile(FILE_PATH)
    
    master_records = []

    # 1. וגשל
    if 'וגשל' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='וגשל')
        for _, row in df.iterrows():
            prod = row.get('מוצר')
            price = row.get('מחיר לפני מע"מ')
            if pd.notna(prod) and pd.notna(price):
                master_records.append({'מוצר': str(prod).strip(), 'יחידה': row.get('יחידה'), 'ספק': 'ווגשל', 'מחיר': price})

    # 2. יפאורה
    if 'יפאורה' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='יפאורה')
        for _, row in df.iterrows():
            prod = row.get('מוצר')
            price = row.get('מחיר לפני מע"מ')
            if pd.notna(prod) and pd.notna(price):
                master_records.append({'מוצר': str(prod).strip(), 'יחידה': row.get('יחידה'), 'ספק': 'יפאורה', 'מחיר': price})

    # 3. תנובה
    if 'תנובה' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='תנובה', header=None)
        for idx in range(1, len(df)):
            row = df.iloc[idx]
            prod = row[0]
            price = row[1]
            if pd.notna(prod) and pd.notna(price):
                master_records.append({'מוצר': str(prod).strip(), 'יחידה': 'יחידה', 'ספק': 'תנובה', 'מחיר': price})

    # 4. אנגל
    if 'אנגל' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='אנגל', header=None)
        for idx in range(0, len(df)):
            row = df.iloc[idx]
            prod = row[0]
            price = row[1]
            if pd.notna(prod) and pd.notna(price):
                master_records.append({'מוצר': str(prod).strip(), 'יחידה': 'יחידה', 'ספק': "אנג'ל", 'מחיר': price})

    # 5. הודיה פלסט
    if 'הודיה פלסט' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='הודיה פלסט', header=None)
        for idx in range(2, len(df)):
            row = df.iloc[idx]
            prod = row[0]
            price = row[2]
            if pd.notna(prod) and pd.notna(price):
                master_records.append({'מוצר': str(prod).strip(), 'יחידה': row.get(1), 'ספק': 'הודיה פלסט', 'מחיר': price})

    # 6. חד פעמי חדש
    if 'חד פעמי חדש' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='חד פעמי חדש')
        sup_cols = ['פעמית.ח', 'דלאס', 'ווגשל', 'טאץ', 'ר. שמאי']
        for _, row in df.iterrows():
            prod = row.get('המוצר')
            if pd.isna(prod): continue
            for s_name in sup_cols:
                val = row.get(s_name)
                if pd.notna(val) and not isinstance(val, str):
                    master_records.append({'מוצר': str(prod).strip(), 'יחידה': row.get('כמות'), 'ספק': s_name, 'מחיר': val})

    # 7. גידרון
    if 'גידרון' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='גידרון', header=None)
        sup_map = {2: 'גידרון', 4: 'עמית', 5: 'ווגשל', 6: 'נחמה'}
        for idx in range(2, len(df)):
            row = df.iloc[idx]
            prod = row[0]
            if pd.isna(prod): continue
            for col_idx, s_name in sup_map.items():
                val = row[col_idx]
                if pd.notna(val) and not isinstance(val, str):
                    master_records.append({'מוצר': str(prod).strip(), 'יחידה': row[1], 'ספק': s_name, 'מחיר': val})

    # 8. מאפיים
    if 'מאפיים' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='מאפיים', header=None)
        sup_map = {1: 'קליינס', 3: 'קוליטש', 5: 'חלת הבית', 6: 'גידרון', 8: "בן ג'ריס", 10: 'נחמה'}
        for idx in range(1, len(df)):
            row = df.iloc[idx]
            prod = row[0]
            if pd.isna(prod): continue
            for col_idx, s_name in sup_map.items():
                val = row[col_idx]
                if pd.notna(val) and not isinstance(val, str):
                    master_records.append({'מוצר': str(prod).strip(), 'יחידה': 'יחידה', 'ספק': s_name, 'מחיר': val})

    # יצירת קובץ אקסל חדש
    master_df = pd.DataFrame(master_records)
    # סינון שמות שהם מספרים בטעות
    master_df = master_df[~master_df['מוצר'].astype(str).str.match(r'^[0-9.]+$')]
    
    master_df.to_excel(OUTPUT_PATH, index=False)
    print(f"\n🎉 קובץ האקסל המתוקן נוצר בהצלחה!")
    print(f"📁 שם הקובץ: {OUTPUT_PATH}")
    print(f"📊 סה'כ שורות נתונים תקינות בקובץ: {len(master_df)}")

if __name__ == "__main__":
    generate_fixed_excel()