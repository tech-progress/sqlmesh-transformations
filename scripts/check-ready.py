import sys
import time

from config import connection


def main():
    for prefix in ("STATE", "WAREHOUSE"):
        for attempt in range(12):
            adapter = connection(prefix).create_engine_adapter()
            try:
                adapter.fetchone("SELECT 1")
                break
            except Exception:
                if attempt == 11:
                    sys.exit(f"{prefix} database unavailable after bounded readiness wait")
                time.sleep(2)
            finally:
                adapter.close()
    state = connection("STATE").create_engine_adapter()
    try:
        initialized = state.fetchone("SELECT to_regclass('sqlmesh._environments')")[0]
        if not initialized or not state.fetchone("SELECT COUNT(*) FROM sqlmesh._environments WHERE name='prod'")[0]:
            sys.exit("prod is not initialized: review and explicitly approve the initial plan first")
    finally:
        state.close()


if __name__ == "__main__":
    main()
