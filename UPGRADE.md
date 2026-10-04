# Upgrades and recovery

Template release **v1.0.4**; [VERSION](VERSION) is authoritative. This release must be qualified independently. A source release does not prove marketplace publication. Template versions are SemVer, independent of SQLMesh/PostgreSQL/Python pins. Exact runtime pins live in [Dockerfile](Dockerfile), [compose.yaml](compose.yaml), [uv.lock](uv.lock) and [.railway/railway.ts](.railway/railway.ts). Never follow a mutable runtime image tag without a new locked and verified template release.

The public standalone source is `tech-progress/sqlmesh-transformations`, `main` / `release-v1`, root `/`; verify the intended immutable tag and exact commit before upgrading. Historical tags remain unchanged. The initial `v1.0.0` lacks required runtime inventory and `v1.0.2` has a documentation-version mismatch; neither is a qualified rollback target. Historical `v1.0.3` private operator/audit/replacement and paired restore passed, with manual default-job evidence but no observed hourly scheduler firing. Requalify every new source or pin independently under [PUBLISHING.md](PUBLISHING.md).

## Upgrade procedure

1. Disable cron and wait for all runs/operator plans to finish. Preserve the exact source commit, template version, `uv.lock`, database role configuration and stable secrets. All three services must remain private; state and warehouse retain independent 5000 MB volumes.
2. Take matched logical dumps of state and warehouse while quiescent. Store them encrypted outside both service volumes; fixtures are not representative of real sensitive data. Record a common backup boundary and test restoration before proceeding.
3. Upgrade SQLMesh/dependency lock in a disposable clone. Inspect upstream changes, state schema migrations and model/audit categorization. Run `verify.sh` and the complete workflow, including both-database restore. Do not let a new cron image implicitly be your untested state-migration experiment.
4. Use the explicit bounded `sleep 1800` private maintenance session from [README.md](README.md) on the intended exact source when operator access is required. Inspect the actual deployment manifest/current instance before SSH. Perform required SQLMesh state migration explicitly using the pinned version, with scheduling still paused. Render a bounded plan against the intended databases, inspect readable SQL, targets, diff and intervals, then approve the **new** review hash. Never reuse a hash across changed targets or state. A fresh default's initial no-prod refusal is expected until this bootstrap; cron must never silently plan or approve it.
5. Stop maintenance and restore Start Command `./start.sh`, cron `0 * * * *`, restart `NEVER` and no runner healthcheck/public networking; read back the actual deployed settings. Verify production views and persisted intervals, then observe one actual hourly scheduler firing and successful native job completion. Build-only `SUCCESS` and database readiness are insufficient; a manual restart is separate evidence. No continuously running runner is expected between jobs. Keep coordinated pre-upgrade backups and source available for rollback.

## Paired restore

Use compatible PostgreSQL clients (the pinned database containers supply `pg_dump`/`psql`). Pause scheduling and all operator/data writes at a common quiescent boundary. The local workflow demonstrates the following with fixture data and independent replacement volumes; historical private Railway paired restore also passed, without proving this new release:

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

Clean up disposable upgrade/restore resources with standard deletion, verified zero active deployments/instances/queued work and disclosed retention. Keep required backups under your own retention policy. No physical-erasure, retention-completion or billing-zero claim follows from deletion.
