"""Print sample rows from every raw table, then trace one order across the tables."""
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "warehouse" / "olist.duckdb"
TABLES = [
    "orders", "order_items", "customers", "order_payments", "order_reviews",
    "products", "sellers", "geolocation", "product_category_name_translation",
]

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)

con = duckdb.connect(str(DB_PATH), read_only=True)

# Part 1: two sample rows per table, shown sideways (one line per column)
for table in TABLES:
    df = con.execute(f"select * from raw.{table} limit 2").df()
    print(f"\n===== raw.{table} ({len(df.columns)} columns) =====")
    print(df.T)

# Part 2: follow one order that has exactly 2 items through every table
order_id = con.execute("""
    select order_id from raw.order_items
    group by order_id
    having count(*) = 2
    limit 1
""").fetchone()[0]

print(f"\n\n########## Tracing order {order_id} ##########")
for table in ["orders", "order_items", "order_payments", "order_reviews"]:
    print(f"\n--- {table} ---")
    print(con.execute(f"select * from raw.{table} where order_id = ?", [order_id]).df().T)

customer_id = con.execute(
    "select customer_id from raw.orders where order_id = ?", [order_id]
).fetchone()[0]
print("\n--- customers ---")
print(con.execute("select * from raw.customers where customer_id = ?", [customer_id]).df().T)

# Part 3: why geolocation needs cleaning: many rows for one zip prefix
print("\n\n########## One zip prefix in raw.geolocation ##########")
print(con.execute("""
    select geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city
    from raw.geolocation
    where geolocation_zip_code_prefix = (select geolocation_zip_code_prefix from raw.geolocation limit 1)
    limit 8
""").df())

con.close()