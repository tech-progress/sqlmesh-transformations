# Deploy and Host SQLMesh transformations on Railway

Reviewed SQLMesh plans with private state and warehouse Postgres.

## About Hosting SQLMesh transformations

[SQLMesh](https://github.com/SQLMesh/sqlmesh) incrementally transforms SQL data with tested plans and blocking audits. This evaluation stack pairs an exiting hourly runner with independent private [PostgreSQL](https://www.postgresql.org/) state and warehouse services. State and warehouse each have their own durable volume. Models, tests and audits are baked into the image.

## Why Deploy SQLMesh transformations on Railway

Keep SQLMesh snapshots and intervals independent from the warehouse, replace ephemeral runners without losing progress, and review a bounded plan before promotion. Hourly jobs execute `sqlmesh run prod` and exit; they never apply model changes. No public UI or backend is exposed. Initial production initialization requires an explicit operator review and approval inside the private network.

## Common Use Cases

- Evaluate incremental SQL transformations with deterministic order/revenue fixtures.
- Practice tested backfills and deliberately blocking data-quality audits.
- Learn durable state, disposable runners and coordinated two-database recovery.

## Dependencies for SQLMesh transformations

### Deployment Dependencies

- SQLMesh 0.236.2, Python 3.12.15 and locked Python dependencies.
- Two digest-pinned PostgreSQL 16.15 services with independent secrets and volumes.
- A real configured GitHub source repository and slash-free release branch.
- Operator access for reviewed plan initialization; a separate raw-data producer for real workloads.

This is not a high-availability or production-scale warehouse. Cloud deployment, draft deployment and publication gates are still pending; there is no published template ID or deploy link.
