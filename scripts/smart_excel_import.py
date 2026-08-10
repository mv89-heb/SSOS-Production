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
from app.models.product import Product
from app.models.supplier_offer import SupplierProductOffer
from app.models.tenant import Tenant

app = create_app()
FILE_PATH = "מחירים - ספקי מזון.xls"

def get_or_create_supplier(name, tenant_id):
    """ מעודכן: עכשיו מקבל tenant_id כדי שנוכל ליצור ספקים חדשים כהלכה """
    if not name or pd.isna(name): return None
    name = str(name).strip()
    sup = db.session.query(Supplier).filter_by(name=name).first()
    if not sup:
        sup = Supplier(name=name, tenant_id=tenant_id)
        db.session.add(sup)
        db.session.flush()
    return sup

def get_or_create_product(name, tenant_id, primary_supplier_id):
    if not name or pd.isna(name): return None
    name = str(name).strip()
    prod = db.session.query(Product).filter_by(name=name).first()
    if not prod:
        prod = Product(name=name, tenant_id=tenant_id, supplier_id=primary_supplier_id)
        db.session.add(prod)
        db.session.flush()
    return prod

def save_offer(product, supplier, price, tenant_id):
    try:
        price_val = float(price)
    except ValueError:
        return # מדלג אם המחיר הוא טקסט לא תקין

    offer = db.session.query(SupplierProductOffer).filter_by(product_id=product.id, supplier_id=supplier.id).first()
    if not offer:
        offer = SupplierProductOffer(
            product_id=product.id, 
            supplier_id=supplier.id, 
            price=price_val, 
            tenant_id=tenant_id
        )
        db.session.add(offer)
    else:
        offer.price = price_val

def process_standard_sheet(xls, sheet_name, supplier_name, prod_col, price_col, tenant_id):
    print(f"\n📂 מעבד לשונית סטנדרטית: '{sheet_name}'...")
    df = pd.read_excel(xls, sheet_name=sheet_name)
    supplier = get_or_create_supplier(supplier_name, tenant_id)
    
    count = 0
    for index, row in df.iterrows():
        prod_name = row.get(prod_col)
        price = row.get(price_col)
        
        if pd.isna(prod_name) or pd.isna(price):
            continue
            
        product = get_or_create_product(prod_name, tenant_id, supplier.id)
        save_offer(product, supplier, price, tenant_id)
        count += 1
        
    print(f"✅ נוספו/עודכנו {count} מוצרים לספק {supplier_name}.")

def process_pivot_sheet(xls, sheet_name, tenant_id):
    print(f"\n📂 מעבד לשונית השוואה: '{sheet_name}'...")
    df = pd.read_excel(xls, sheet_name=sheet_name)
    supplier_columns = ['פעמית.ח', 'דלאס', 'ווגשל', 'טאץ', 'ר. שמאי']
    
    count = 0
    for index, row in df.iterrows():
        prod_name = row.get('המוצר')
        if pd.isna(prod_name): continue
        
        valid_offers = []
        for sup_name in supplier_columns:
            price = row.get(sup_name)
            if not pd.isna(price) and type(price) != str:
                valid_offers.append((sup_name, price))
                
        if not valid_offers: continue
        
        first_sup = get_or_create_supplier(valid_offers[0][0], tenant_id)
        product = get_or_create_product(prod_name, tenant_id, first_sup.id)
        
        for sup_name, price in valid_offers:
            supplier = get_or_create_supplier(sup_name, tenant_id)
            save_offer(product, supplier, price, tenant_id)
            count += 1
            
    print(f"✅ נוספו/עודכנו {count} הצעות מחיר מספקים שונים.")

def process_complex_gidron(xls, tenant_id):
    print(f"\n📂 מעבד לשונית מורכבת: 'גידרון'...")
    df = pd.read_excel(xls, sheet_name='גידרון', header=None)
    
    supplier_col_map = {
        2: 'גידרון',
        4: 'עמית',
        5: 'ווגשל',
        6: 'נחמה'
    }
    
    count = 0
    for index in range(2, len(df)):
        row = df.iloc[index]
        prod_name = row[0] 
        if pd.isna(prod_name): continue
        
        valid_offers = []
        for col_idx, sup_name in supplier_col_map.items():
            price = row[col_idx]
            if not pd.isna(price) and type(price) != str:
                valid_offers.append((sup_name, price))
                
        if not valid_offers: continue
        
        first_sup = get_or_create_supplier(valid_offers[0][0], tenant_id)
        product = get_or_create_product(prod_name, tenant_id, first_sup.id)
        
        for sup_name, price in valid_offers:
            supplier = get_or_create_supplier(sup_name, tenant_id)
            save_offer(product, supplier, price, tenant_id)
            count += 1
            
    print(f"✅ נוספו/עודכנו {count} הצעות מחיר מהלשונית.")

def process_complex_mafaim(xls, tenant_id):
    print(f"\n📂 מעבד לשונית מורכבת: 'מאפיים'...")
    df = pd.read_excel(xls, sheet_name='מאפיים', header=None)
    
    supplier_col_map = {
        1: 'קליינס',
        3: 'קוליטש',
        5: 'חלת הבית',
        6: 'גידרון',
        8: "בן ג'ריס",
        10: 'נחמה'
    }
    
    count = 0
    for index in range(1, len(df)):
        row = df.iloc[index]
        prod_name = row[0]
        if pd.isna(prod_name): continue
        
        valid_offers = []
        for col_idx, sup_name in supplier_col_map.items():
            price = row[col_idx]
            if not pd.isna(price) and type(price) != str:
                valid_offers.append((sup_name, price))
                
        if not valid_offers: continue
        
        first_sup = get_or_create_supplier(valid_offers[0][0], tenant_id)
        product = get_or_create_product(prod_name, tenant_id, first_sup.id)
        
        for sup_name, price in valid_offers:
            supplier = get_or_create_supplier(sup_name, tenant_id)
            save_offer(product, supplier, price, tenant_id)
            count += 1
            
    print(f"✅ נוספו/עודכנו {count} הצעות מחיר מהלשונית.")

def run_smart_import():
    with app.app_context():
        tenant = db.session.query(Tenant).first()
        tenant_id = tenant.id if tenant else 1
        
        try:
            xls = pd.ExcelFile(FILE_PATH)
            
            if 'וגשל' in xls.sheet_names:
                process_standard_sheet(xls, 'וגשל', 'ווגשל', 'מוצר', 'מחיר לפני מע"מ', tenant_id)
            
            if 'יפאורה' in xls.sheet_names:
                process_standard_sheet(xls, 'יפאורה', 'יפאורה', 'מוצר', 'מחיר לפני מע"מ', tenant_id)
                
            if 'תנובה' in xls.sheet_names:
                process_standard_sheet(xls, 'תנובה', 'תנובה', 'תנובה', 'מכירה לישיבות', tenant_id)
                
            if 'אנגל' in xls.sheet_names:
                process_standard_sheet(xls, 'אנגל', "אנג'ל", "אנג'ל", 'המכירה לישיבות', tenant_id)
                
            if 'חד פעמי חדש' in xls.sheet_names:
                process_pivot_sheet(xls, 'חד פעמי חדש', tenant_id)
                
            if 'גידרון' in xls.sheet_names:
                process_complex_gidron(xls, tenant_id)
                
            if 'מאפיים' in xls.sheet_names:
                process_complex_mafaim(xls, tenant_id)
                
            db.session.commit()
            print("\n🎉 כל הנתונים מהאקסל יובאו וסודרו בדאטהבייס בהצלחה!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ שגיאה במהלך הייבוא: {e}")

if __name__ == "__main__":
    run_smart_import()