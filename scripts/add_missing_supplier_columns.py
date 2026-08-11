import os

import psycopg2


def add_columns():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            queries = [
                "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS phone2 VARCHAR(50);",
                "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS customer_number VARCHAR(100);",
                "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS delivery_days VARCHAR(100);",
            ]
            for query in queries:
                cur.execute(query)
                print(f"✔ בוצע: {query}")
    finally:
        conn.close()


if __name__ == "__main__":
    add_columns()
