import psycopg2

NEON_URL = "postgresql://neondb_owner:npg_lnig01mwDMLf@ep-mute-frog-ad3vchf3-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def add_order_days():
    conn = psycopg2.connect(NEON_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS order_days VARCHAR(100);")
    cur.close()
    conn.close()
    print("✔ עמודת 'order_days' (ימי הזמנות) נוספה בהצלחה לטבלת הספקים!")

if __name__ == "__main__":
    add_order_days()