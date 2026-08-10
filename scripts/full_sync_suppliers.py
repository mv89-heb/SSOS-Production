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

def full_sync():
    with app.app_context():
        tenant = db.session.query(Tenant).first()
        tenant_id = tenant.id if tenant else 1
        
        if not os.path.exists(EXCEL_FILE):
            print(f"❌ שגיאה: לא מצאתי את הקובץ {EXCEL_FILE}.")
            return

        df = pd.read_excel(EXCEL_FILE, sheet_name='גיליון1', header=3)
        print(f"🔄 מבצע סנכרון מלא של כל פרטי הספקים...")

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
            cust_num = str(row.get("מס' לקוח", '')).strip() if pd.notna(row.get("מס' לקוח")) else ''
            del_days = str(row.get('ימי אספקה', '')).strip() if pd.notna(row.get('ימי אספקה')) else ''
            
            phone1 = phone1 if phone1 and phone1 != 'nan' else ''
            phone2 = phone2 if phone2 and phone2 != 'nan' else ''
            mobile = mobile if mobile and mobile != 'nan' else ''
            contact = contact if contact and contact != 'nan' else ''
            cust_num = cust_num if cust_num and cust_num != 'nan' else ''
            del_days = del_days if del_days and del_days != 'nan' else ''

            # בחירת טלפון ראשי ומשני
            main_phone = mobile if mobile else (phone1 if phone1 else None)
            secondary_phone = phone2 if phone1 and phone2 else None

            supplier = db.session.query(Supplier).filter_by(name=sup_name, tenant_id=tenant_id).first()
            if supplier:
                if main_phone: supplier.phone = main_phone
                if secondary_phone: supplier.phone2 = secondary_phone
                if contact: supplier.contact_name = contact
                if cust_num: supplier.customer_number = cust_num
                if del_days: supplier.delivery_days = del_days
                updated_count += 1
            else:
                new_sup = Supplier(
                    name=sup_name,
                    tenant_id=tenant_id,
                    phone=main_phone,
                    phone2=secondary_phone,
                    contact_name=contact if contact else None,
                    customer_number=cust_num if cust_num else None,
                    delivery_days=del_days if del_days else None,
                    active=True
                )
                db.session.add(new_sup)
                added_count += 1

        db.session.commit()
        print(f"\n🎉 הסנכרון המלא הושלם בהצלחה!")
        print(f"📌 עודכנו: {updated_count} ספקים.")
        print(f"✨ נוספו: {added_count} ספקים חדשים.")

if __name__ == "__main__":
    full_sync()