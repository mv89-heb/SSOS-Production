import sys
import os
import pandas as pd

NEON_URL = "postgresql://neondb_owner:npg_lnig01mwDMLf@ep-mute-frog-ad3vchf3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
os.environ['DATABASE_URL'] = NEON_URL
os.environ['SQLALCHEMY_DATABASE_URI'] = NEON_URL

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app 
from app.extensions import db
from app.models.supplier import Supplier
from app.models.tenant import Tenant

app = create_app()
EXCEL_FILE = "טלפונים ספקי מזון.xls"

def smart_update_suppliers():
    with app.app_context():
        tenant = db.session.query(Tenant).first()
        tenant_id = tenant.id if tenant else 1
        
        if not os.path.exists(EXCEL_FILE):
            print(f"❌ שגיאה: לא מצאתי את הקובץ {EXCEL_FILE}.")
            return

        df = pd.read_excel(EXCEL_FILE, sheet_name='גיליון1', header=3)
        print(f"🔄 ממפה ומעדכן ספקים מקובץ הטלפונים...")

        updated_count = 0
        added_count = 0

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

            # בחירת מספר הטלפון המרכזי (מעדיפים נייד או טלפון 1)
            phones = [p for p in [mobile, phone1, phone2] if p and p != 'nan']
            main_phone = phones[0] if phones else None

            # חיפוש הספק לפי השם במסד הנתונים
            supplier = db.session.query(Supplier).filter_by(name=sup_name, tenant_id=tenant_id).first()
            if supplier:
                if main_phone:
                    supplier.phone = main_phone
                if contact:
                    supplier.contact_name = contact
                updated_count += 1
                print(f"  ✔ עודכן ספק: {sup_name} | טלפון: {main_phone} | איש קשר: {contact}")
            else:
                # הוספת ספק חדש אם הוא לא היה קיים קודם
                new_sup = Supplier(
                    name=sup_name,
                    tenant_id=tenant_id,
                    phone=main_phone,
                    contact_name=contact if contact else None,
                    active=True
                )
                db.session.add(new_sup)
                added_count += 1
                print(f"  ✨ נוסף ספק חדש: {sup_name} | טלפון: {main_phone} | איש קשר: {contact}")

        db.session.commit()
        print(f"\n🎉 הסתיים בהצלחה!")
        print(f"📌 עודכנו: {updated_count} ספקים.")
        print(f"✨ נוספו: {added_count} ספקים חדשים.")

if __name__ == "__main__":
    smart_update_suppliers()