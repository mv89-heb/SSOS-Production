import sys
import os
import re

NEON_URL = "postgresql://neondb_owner:npg_lnig01mwDMLf@ep-mute-frog-ad3vchf3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

os.environ['DATABASE_URL'] = NEON_URL
os.environ['SQLALCHEMY_DATABASE_URI'] = NEON_URL

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app 
from app.extensions import db
from app.models.supplier import Supplier
from app.models.product import Product

app = create_app()

def inspect_primary_products():
    with app.app_context():
        print("🕵️ סורק את טבלת המוצרים הראשיים...\n")
        
        suppliers = db.session.query(Supplier).all()
        fake_suppliers = [s for s in suppliers if s.name and re.match(r'^[0-9.]+$', s.name.strip())]
        
        for fs in fake_suppliers:
            # הפעם אנחנו בודקים ישירות את טבלת המוצרים (Product) 
            products = db.session.query(Product).filter_by(supplier_id=fs.id).all()
            
            if products:
                print(f"🗑️ 'ספק' מזויף: {fs.name} (מזהה: {fs.id})")
                for p in products:
                    print(f"   -> מוצר ראשי שתקוע אצלו: {p.name} (מזהה מוצר: {p.id})")
                print("")

if __name__ == "__main__":
    inspect_primary_products()