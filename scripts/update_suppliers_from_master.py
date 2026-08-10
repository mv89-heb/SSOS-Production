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
MASTER_FILE = "Fixed_Suppliers_Master.xlsx"

def update_suppliers_database():
    with app.app_context():
        tenant = db.session.query(Tenant).first()
        tenant_id = tenant.id if tenant else 1
        
        if not os.path.exists(MASTER_FILE):
            print(f"❌ שגיאה: לא מצאתי את הקובץ {MASTER_FILE}. הפעל קודם את סקריפט הייצוא.")
            return

        df = pd.read_excel(MASTER_FILE)
        print(f"🔄 מעדכן פרטי קשר מתוך קובץ ה-Master עבור {len(df)} ספקים...")

        updated_count = 0
        added_count = 0

        for _, row in df.iterrows():
            sup_name = str(row.get('שם ספק', '')).strip()
            if not sup_name or sup_name == 'nan':
                continue

            phone1 = str(row.get('טלפון ראשי', '')).strip()
            phone2 = str(row.get('טלפון נוסף', '')).strip()
            mobile = str(row.get('נייד', '')).strip()
            contact = str(row.get('איש קשר', '')).strip()

            # איסוף טלפון זמין ופעיל
            phones = [p for p in [phone1, mobile, phone2] if p and p != 'nan']
            main_phone = phones[0] if phones else None

            # בדיקה האם הספק קיים כבר במסד הנתונים
            supplier = db.session.query(Supplier).filter_by(name=sup_name, tenant_id=tenant_id).first()
            
            if supplier:
                if main_phone:
                    supplier.phone = main_phone
                if contact and contact != 'nan':
                    supplier.contact_name = contact
                updated_count += 1
            else:
                # הוספת ספק חדש במידה ואינו קיים
                new_sup = Supplier(
                    name=sup_name,
                    tenant_id=tenant_id,
                    phone=main_phone,
                    contact_name=contact if contact and contact != 'nan' else None,
                    active=True
                )
                db.session.add(new_sup)
                added_count += 1

        db.session.commit()
        print(f"\n🎉 עדכון מסד הנתונים הסתיים בהצלחה מלאה!")
        print(f"📌 עודכנו פרטי קשר ל-{updated_count} ספקים קיימים.")
        print(f"✨ נוספו {added_count} ספקים חדשים מתוך קובץ ה-Master.")

if __name__ == "__main__":
    update_suppliers_database()