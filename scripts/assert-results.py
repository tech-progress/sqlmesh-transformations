import argparse
import json
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from config import connection
from sqlmesh import Context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--through", required=True)
    parser.add_argument("--interval-through")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    expected = [
        ("2026-09-29", 2, "20.00"),
        ("2026-09-30", 1, "30.00"),
        ("2026-10-01", 1, "40.00"),
    ]
    expected = [row for row in expected if row[0] <= arguments.through]
    warehouse = connection("WAREHOUSE").create_engine_adapter()
    state = connection("STATE").create_engine_adapter()
    try:
        rows = warehouse.fetchall("SELECT order_date, paid_orders, revenue FROM analytics.daily_revenue ORDER BY order_date")
        actual = [(str(date), count, str(revenue)) for date, count, revenue in rows]
        if actual != expected:
            raise AssertionError(f"Incorrect incremental revenue: {actual!r}, expected {expected!r}")
        if state.fetchone("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='raw'")[0]:
            raise AssertionError("Warehouse raw data leaked into the state database")
        if warehouse.fetchone("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='sqlmesh' AND table_name='_intervals'")[0]:
            raise AssertionError("State intervals leaked into the warehouse")
        interval_rows = state.fetchall("SELECT name, identifier, start_ts, end_ts, is_removed FROM sqlmesh._intervals ORDER BY name, identifier, start_ts, end_ts, is_removed")
        if not interval_rows:
            raise AssertionError("State database has no persisted intervals")
        with closing(Context(paths=".")) as context:
            environment = context.state_sync.get_environment("prod")
            snapshots = context.state_sync.get_snapshots(environment.snapshots)
            materialized = [snapshot for snapshot in snapshots.values() if snapshot.name.endswith('"staged_orders"') or snapshot.name.endswith('"daily_revenue"')]
            if len(materialized) != 2 or any(not snapshot.intervals for snapshot in materialized):
                raise AssertionError("Both models must have persisted intervals")
            start = int(datetime(2026, 9, 29, tzinfo=timezone.utc).timestamp() * 1000)
            end_date = date.fromisoformat(arguments.interval_through or arguments.through) + timedelta(days=1)
            end = int(datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
            if any(snapshot.intervals != [(start, end)] for snapshot in materialized):
                raise AssertionError("Persisted logical intervals differ from the expected complete date range")
            intervals = sorted(
                [{"name": snapshot.name, "identifier": snapshot.identifier, "version": snapshot.version,
                  "intervals": snapshot.intervals} for snapshot in materialized],
                key=lambda snapshot: snapshot["name"],
            )
            document = {"rows": actual, "plan_id": environment.plan_id, "intervals": intervals}
        if arguments.output:
            arguments.output.write_text(json.dumps(document, sort_keys=True, default=str) + "\n")
        print(json.dumps(document, sort_keys=True, default=str))
    finally:
        warehouse.close()
        state.close()


if __name__ == "__main__":
    main()
