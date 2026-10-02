import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve", required=True)
    arguments = parser.parse_args()
    model = Path("models/daily_revenue.sql")
    original = model.read_text()
    try:
        model.write_text(original.replace("status = 'paid'", "status = 'paid' AND order_date >= CAST('2026-09-29' AS DATE)"))
        command = ["python", "scripts/plan.py", "apply", "--execution-time", "2026-10-02", "--approve", arguments.approve]
        rejected = subprocess.run(command, check=False)
        if rejected.returncode == 0:
            raise AssertionError("A stale approval applied changed source")
        subprocess.run(["./start.sh", "--end", "2026-10-01"], check=True)
    finally:
        model.write_text(original)


if __name__ == "__main__":
    main()
