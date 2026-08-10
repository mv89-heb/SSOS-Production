import sys
import os
import pandas as pd
import re

NEON_URL = "postgresql://neondb_owner:npg_lnig01mwDMLf@ep-mute-frog-ad3vchf3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
os.environ['DATABASE_URL'] = NEON_URL
os.environ['SQLALCHEMY_DATABASE_URI'] = NEON_URL

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app 
from app.extensions import db
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.supplier_offer import SupplierProductOffer
from app.models.tenant import Tenant

app = create_app()
MASTER_FILE = "Fixed_Prices_Master.xlsx"

def get_or_create_supplier(name, tenant_id, cache):
    if not name or pd.isna(name): return None
    name = str(name).strip()
    if name in cache:
        return cache[name]
    
    sup = db.session.query(Supplier).filter_by(name=name, tenant_id=tenant_id).first()
    if not sup:
        sup = Supplier(name=name, tenant_id=tenant_id)
        db.session.add(sup)
        db.session.flush()
    cache[name] = sup
    return sup

def get_or_create_product(name, tenant_id, primary_supplier_id, cache):
    if not name or pd.isna(name): return None
    name = str(name).strip()
    if re.match(r'^[0-9.]+$', name) or name.lower() == 'מוצר':
        return None
    if name in cache:
        return cache[name]
        
    prod = db.session.query(Product).filter_by(name=name, tenant_id=tenant_id).first()
    if not prod:
        prod = Product(name=name, tenant_id=tenant_id, supplier_id=primary_supplier_id)
        db.session.add(prod)
        db.session.flush()
    cache[name] = prod
    return prod

def update_database():
    with app.app_context():
        tenant = db.session.query(Tenant).first()
        tenant_id = tenant.id if tenant else 1
        
        if not os.path.exists(MASTER_FILE):
            print(f"❌ שגיאה: לא מצאתי את הקובץ {MASTER_FILE}. ודא שהוא קיים בתיקייה.")
            return

        print("🧹 מאפס את נתוני הצעות המחיר והמוצרים הקודמים...")
        db.session.query(SupplierProductOffer).delete()
        db.session.query(Product).delete()
        db.session.commit()

        df = pd.read_excel(MASTER_FILE)
        print(f"התחלתי בטעינת {len(df)} שורות מתוך קובץ ה-Master לתוך ה-DB...")

        supplier_cache = {}
        product_cache = {}
        processed_pairs = set()

        imported_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            prod_name = row.get('מוצר')
            sup_name = row.get('ספק')
            price = row.get('מחיר')
            unit = row.get('יחידה')

            if pd.isna(prod_name) or pd.isna(sup_name) or pd.isna(price):
                skipped_count += 1
                continue

            # המרת מחיר ובדיקה שהוא אכן מספר תקין לחלוטין
            try:
                price_val = float(price)
            except (ValueError, TypeError):
                skipped_count += 1
                continue

            supplier = get_or_create_supplier(sup_name, tenant_id, supplier_cache)
            if not supplier:
                skipped_count += 1
                continue

            product = get_or_create_product(prod_name, tenant_id, supplier.id, product_cache)
            if not product:
                skipped_count += 1
                continue

            pair_key = (product.id, supplier.id)
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            if pd.notna(unit) and not product.unit:
                product.unit = str(unit).strip()

            offer = SupplierProductOffer(
                product_id=product.id,
                supplier_id=supplier.id,
                price=price_val,
                tenant_id=tenant_id
            )
            db.session.add(offer)
            imported_count += 1

        db.session.commit()
        print(f"\n🎉 העדכון הושלם בהצלחה מלאה!")
        print(f"📦 הוכנסו למסד הנתונים {imported_count} הצעות מחיר מדויקות ותקינות.")
        if skipped_count > 0:
            print(f"ℹ️ (הושמטו {skipped_count} שורות ריקות או כותרות פנימיות שלא היו אמורות להיכנס).")

if __name__ == "__main__":
    update_database()