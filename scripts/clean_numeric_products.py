import sys
import os
import re

NEON_URL = "postgresql://neondb_owner:npg_lnig01mwDMLf@ep-mute-frog-ad3vchf3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
os.environ['DATABASE_URL'] = NEON_URL
os.environ['SQLALCHEMY_DATABASE_URI'] = NEON_URL

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app 
from app.extensions import db
from app.models.product import Product
from app.models.supplier_offer import SupplierProductOffer

app = create_app()

def clean_numeric_products():
    with app.app_context():
        print("🕵️ סורק מוצרים ששמם הוא מספר בלבד...")
        products = db.session.query(Product).all()
        numeric_products = [p for p in products if p.name and re.match(r'^[0-9.]+$', p.name.strip())]
        
        print(f"נמצאו {len(numeric_products)} מוצרים מזויפים ששמם הוא מספר.")
        
        try:
            for p in numeric_products:
                print(f"   -> מוחק מוצר מזויף: {p.name} (מזהה: {p.id})")
                # מחיקת הצעות מחיר מקושרות למניעת שגיאות מפתח זר
                db.session.query(SupplierProductOffer).filter_by(product_id=p.id).delete()
                # מחיקת המוצר עצמו
                db.session.delete(p)
                
            db.session.commit()
            print("\n🎉 כל המוצרים המספריים המזויפים נמחקו בהצלחה!")
            print("✨ הקטלוג שלך כעת נקי לחלוטין ומכיל אך ורק מוצרים אמיתיים ותקינים.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ שגיאה בניקוי: {e}")

if __name__ == "__main__":
    clean_numeric_products()