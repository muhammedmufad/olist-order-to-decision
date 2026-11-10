"""Load the raw Olist CSV files into a local DuckDB warehouse."""
from pathlib import Path

import duckdb

RAW_DIR = Path("data/raw")
DB_PATH = Path("warehouse/olist.duckdb")


def table_name(csv_path: Path) -> str:
    """olist_orders_dataset.csv -> orders"""
    return csv_path.stem.replace("olist_", "").replace("_dataset", "")


def main() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    for csv_path in sorted(RAW_DIR.glob("*.csv")):
        table = table_name(csv_path)
        con.execute(f"""
            CREATE OR REPLACE TABLE raw.{table} AS
            SELECT * FROM read_csv_auto('{csv_path.as_posix()}', header = true)
        """)
        rows = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        print(f"raw.{table:<36} {rows:>10,} rows")

    con.close()


if __name__ == "__main__":
    main()