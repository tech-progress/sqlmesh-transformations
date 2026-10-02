import argparse
import hashlib
import json
from contextlib import closing
from pathlib import Path

from sqlmesh import Context


def review_document(context, plan):
    gateway = context.config.get_gateway()
    targets = {}
    for name, connection in (("warehouse", gateway.connection), ("state", gateway.state_connection)):
        targets[name] = {key: getattr(connection, key) for key in ("host", "port", "database", "user", "sslmode")}
    return {
        "environment": "prod",
        "previous_plan_id": plan.previous_plan_id,
        "targets": targets,
        "sql_sources": {
            str(path): path.read_text()
            for folder in ("models", "audits")
            for path in sorted(Path(folder).glob("*.sql"))
        },
        "start": str(plan.start),
        "end": str(plan.end),
        "execution_time": str(plan.execution_time),
        "snapshots": sorted(
            [{"name": snapshot.name, "identifier": snapshot.identifier, "fingerprint": snapshot.fingerprint.dict(), "version": snapshot.version,
              "category": snapshot.change_category} for snapshot in plan.snapshots.values()],
            key=lambda snapshot: snapshot["name"],
        ),
        "removed": sorted(plan.context_diff.removed_snapshots),
        "missing_intervals": sorted(
            [{"name": interval.snapshot_id.name, "identifier": interval.snapshot_id.identifier,
              "intervals": interval.intervals} for interval in plan.missing_intervals],
            key=lambda interval: interval["name"],
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Review a bounded prod plan; approval is bound to its content and database targets.")
    parser.add_argument("action", choices=("review", "apply"))
    parser.add_argument("--execution-time", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approve")
    arguments = parser.parse_args()
    if arguments.action == "apply" and not arguments.approve:
        parser.error("apply requires --approve SHA256 from a reviewed plan")
    with closing(Context(paths=".")) as context:
        plan = context.plan("prod", execution_time=arguments.execution_time, no_prompts=True, auto_apply=False)
        document = review_document(context, plan)
        digest = hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
        document["approval_sha256"] = digest
        print(json.dumps(document, indent=2, sort_keys=True))
        if arguments.output:
            arguments.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
        if arguments.action == "apply":
            if arguments.approve != digest:
                parser.error("approval does not match the current plan; review again (no plan applied)")
            context.apply(plan)


if __name__ == "__main__":
    main()
