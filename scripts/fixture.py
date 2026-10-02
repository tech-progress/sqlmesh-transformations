import argparse

from config import connection


def main():
    parser = argparse.ArgumentParser(description="Explicit evaluation fixture loader, never invoked by cron.")
    parser.add_argument("--bad-audit", action="store_true")
    parser.add_argument("--repair-audit", action="store_true")
    arguments = parser.parse_args()
    adapter = connection("WAREHOUSE").create_engine_adapter()
    try:
        adapter.execute("CREATE SCHEMA IF NOT EXISTS raw")
        adapter.execute("CREATE TABLE IF NOT EXISTS raw.orders (order_id INT PRIMARY KEY, ordered_at TIMESTAMP NOT NULL, amount DECIMAL(12,2) NOT NULL, status TEXT NOT NULL)")
        adapter.execute("""INSERT INTO raw.orders VALUES
            (1, '2026-09-29 09:00', 12.50, 'PAID'),
            (2, '2026-09-29 10:00', 7.50, 'paid'),
            (3, '2026-09-29 11:00', 99.00, 'cancelled'),
            (4, '2026-09-30 12:00', 30.00, 'paid'),
            (5, '2026-10-01 12:00', 40.00, 'paid')
            ON CONFLICT (order_id) DO UPDATE SET amount=EXCLUDED.amount, status=EXCLUDED.status""")
        if arguments.bad_audit:
            adapter.execute("INSERT INTO raw.orders VALUES (6, '2026-10-01 12:00', -1.00, 'paid') ON CONFLICT (order_id) DO UPDATE SET amount=-1.00")
        if arguments.repair_audit:
            adapter.execute("DELETE FROM raw.orders WHERE order_id=6")
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
