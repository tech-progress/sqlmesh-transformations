# Upgrades and recovery

Template versions are SemVer, independent of SQLMesh/PostgreSQL/Python pins. The initial release is `1.0.0`. Never follow a mutable SQLMesh/Python image tag without a new locked and verified template release.

## Upgrade procedure

1. Disable cron and wait for all runs/operator plans to finish. Preserve the exact source commit, template version, `uv.lock`, database role configuration and stable secrets.
2. Take matched logical dumps of state and warehouse while quiescent. Store them encrypted outside both service volumes; fixtures are not representative of real sensitive data. Record a common backup boundary and test restoration before proceeding.
3. Upgrade SQLMesh/dependency lock in a disposable clone. Inspect upstream changes, state schema migrations and model/audit categorization. Run `verify.sh` and the complete workflow, including both-database restore. Do not let a new cron image implicitly be your untested state-migration experiment.
4. Perform required SQLMesh state migration explicitly as an operator using the pinned version, with scheduling still paused. Render a bounded plan against the intended databases, inspect the diff and intervals, then approve the **new** review hash. Never reuse a hash across changed targets or state.
5. Verify production views and persisted intervals, then enable hourly cron. Observe one actual exit-zero scheduled run. Keep coordinated pre-upgrade backups and source available for rollback.

## Paired restore

Use compatible PostgreSQL clients (the pinned database containers supply `pg_dump`/`psql`). The local workflow demonstrates the following with fixture data and independent replacement volumes:

```bash
docker compose exec -T state pg_dump -U sqlmesh -d sqlmesh_state --no-owner --no-privileges > state.sql
docker compose exec -T warehouse pg_dump -U sqlmesh -d warehouse --no-owner --no-privileges > warehouse.sql
# Restore into EMPTY replacement databases using matching roles and pinned SQLMesh source:
docker compose exec -T state psql -X -v ON_ERROR_STOP=1 -U sqlmesh -d sqlmesh_state < state.sql
docker compose exec -T warehouse psql -X -v ON_ERROR_STOP=1 -U sqlmesh -d warehouse < warehouse.sql
docker compose run --rm runner python scripts/assert-results.py --through 2026-10-01
docker compose run --rm runner ./start.sh --end 2026-10-01
```

The assertion dates are fixture-only. In production, validate your own row counts/checksums, production plan/snapshot identities and interval ranges. Dumps omit role ownership; provision matching roles/permissions separately. Do not restore only state or only warehouse. Never restore old state against newer warehouse physical tables without verifying their snapshot mapping.

For a PostgreSQL major upgrade, provision replacements and use a supported dump/restore or migration path; never attach old-major data files to a new-major image. SQLMesh downgrade may not understand migrated state. Roll back the image/source and **both** compatible databases together, not just the runner.
