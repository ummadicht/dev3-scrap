"""
Interactive PostgreSQL Database Viewer (Scraper & PriceIQ Schemas)
==================================================================
Runs queries over the secure SSH tunnel and prints formatted tables.
Usage:
  python inspect_db.py
  python inspect_db.py --table price_iq.pricing_records
  python inspect_db.py --table price_iq.rate_card_matrix
  python inspect_db.py --query "SELECT * FROM price_iq.pricing_records LIMIT 5;"
"""

import argparse
import sys
import db

def inspect(table_name: str = "price_iq.pricing_records", query: str = None, limit: int = 10):
    db_mgr = db.DatabaseManager()
    with db_mgr.get_connection() as conn:
        with conn.cursor() as cur:
            if query:
                sql = query
            else:
                sql = f"SELECT * FROM {table_name} LIMIT {limit};"
            
            print(f"\n[Executing Query]: {sql}\n")
            cur.execute(sql)
            if cur.description is None:
                conn.commit()
                print("Query executed successfully. (Rows affected: " + str(cur.rowcount) + ")")
                return
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            if not rows:
                print("No records found.")
                return

            # Print formatted table
            col_widths = [max(len(col), max(len(str(r[i] or '')) for r in rows)) for i, col in enumerate(columns)]
            # Cap width for long text
            col_widths = [min(w, 35) for w in col_widths]

            header = " | ".join(f"{col:<{col_widths[i]}}" for i, col in enumerate(columns))
            sep = "-+-".join("-" * col_widths[i] for i in range(len(columns)))
            print(header)
            print(sep)

            for r in rows:
                line = " | ".join(f"{str(r[i] or ''):<{col_widths[i]}}"[:col_widths[i]] for i in range(len(columns)))
                print(line)

            print(f"\n(Total {len(rows)} rows displayed)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect PostgreSQL tables")
    parser.add_argument("--table", type=str, default="price_iq.pricing_records", help="Schema-qualified table name")
    parser.add_argument("--query", type=str, default=None, help="Custom SQL query")
    parser.add_argument("--limit", type=int, default=10, help="Number of rows to display")
    args = parser.parse_args()

    inspect(table_name=args.table, query=args.query, limit=args.limit)

