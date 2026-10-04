# Deploy and Host SQLMesh transformations on Railway

Reviewed SQLMesh plans with private state and warehouse Postgres.

Template release **v1.0.4**; see [VERSION](VERSION). This release must be qualified independently. A source release does not prove marketplace publication; the maintainer's marketplace registry records final status and deploy links.

## About Hosting SQLMesh transformations

[SQLMesh](https://github.com/SQLMesh/sqlmesh) incrementally transforms SQL data with tested plans and blocking audits. This evaluation stack deploys three private services: an exiting hourly runner and independent [PostgreSQL](https://www.postgresql.org/) state and warehouse databases. Each database has its own 5000 MB durable volume. Models, tests and audits are baked into the image.

## Why Deploy SQLMesh transformations on Railway

Keep SQLMesh snapshots and intervals independent from the warehouse, replace ephemeral runners without losing progress, and review a bounded plan before promotion. Cron `0 * * * *` (UTC) uses Start Command `./start.sh` and restart `NEVER`; jobs execute `sqlmesh run prod` and exit, never applying model changes. There is no continuously running runner, HTTP healthcheck, public UI or database proxy. The fresh default intentionally refuses uninitialized `prod` until an explicit reviewed plan is applied inside the private network. [README.md](README.md) documents bounded maintenance access and restoration of the exact cron settings. Build-only `SUCCESS` and database readiness are not completed native SQL jobs.

## Common Use Cases

- Evaluate incremental SQL transformations with deterministic order/revenue fixtures.
- Practice tested backfills and deliberately blocking data-quality audits.
- Learn durable state, disposable runners and coordinated two-database recovery.

## Dependencies for SQLMesh transformations

### Deployment Dependencies

- Locked SQLMesh/Python dependencies and runtime pins in [Dockerfile](Dockerfile) and [uv.lock](uv.lock).
- Two digest-pinned PostgreSQL services with independent secrets and volumes; [compose.yaml](compose.yaml) and [.railway/railway.ts](.railway/railway.ts) define the exact images.
- Public standalone `tech-progress/sqlmesh-transformations`, `main` / `release-v1`, root `/`; verify the release's immutable tag and source authorization.
- Operator access for reviewed plan initialization; a separate raw-data producer for real workloads.

This is not a high-availability or production-scale warehouse. Historical `v1.0.3` private operator/application, blocking audit, replacement and paired restore passed. Its default job was manually restarted; historical hourly scheduler firing was not observed. Every release requires current native job and scheduler evidence under [PUBLISHING.md](PUBLISHING.md). The MIT recipe license covers newly authored source only; upstream/runtime duties and notices remain separate. Standard deletion plus verified zero compute and disclosed retention is the cleanup boundary, without physical-erasure or billing-zero claims.
