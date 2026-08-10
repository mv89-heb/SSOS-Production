import sys
import os
import psycopg2

NEON_URL = "postgresql://neondb_owner:npg_lnig01mwDMLf@ep-mute-frog-ad3vchf3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def add_columns():
    print("🔄 מתחבר למסד הנתונים ומוסיף את העמודות החסרות לטבלת הספקים...")
    conn = psycopg2.connect(NEON_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # הוספת עמודות חדשות אם אינן קיימות
    queries = [
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS phone2 VARCHAR(50);",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS customer_number VARCHAR(100);",
        "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS delivery_days VARCHAR(100);"
    ]

    for q in queries:
        cur.execute(q)
        print(f"✔ בוצע: {q}")

    cur.close()
    conn.close()
    print("\n🎉 העמודות נוספו בהצלחה למסד הנתונים!")

if __name__ == "__main__":
    add_columns()