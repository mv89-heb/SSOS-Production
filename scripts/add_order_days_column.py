import os

import psycopg2


def add_order_days():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS order_days VARCHAR(100);"
            )
        print("✔ עמודת 'order_days' (ימי הזמנות) נוספה בהצלחה לטבלת הספקים!")
    finally:
        conn.close()


if __name__ == "__main__":
    add_order_days()
