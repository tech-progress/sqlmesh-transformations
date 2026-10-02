# SQLMesh transformations

The current template release is `v1.0.0`. This is an **unpublished evaluation starter**, not a highly available warehouse or unattended schema-change system.

Upstream products: [SQLMesh](https://github.com/SQLMesh/sqlmesh) ([documentation](https://sqlmesh.readthedocs.io/en/stable/)) and [PostgreSQL](https://www.postgresql.org/).

## What deploys

| Service | Purpose | Persistence / network |
| --- | --- | --- |
| SQLMesh Runner | Baked SQL models, unit tests, blocking audits; exits after `sqlmesh run prod` | No volume, no HTTP server, no public domain or healthcheck |
| SQLMesh State | SQLMesh snapshots, production environment and processed intervals | Independent 5 GB `/var/lib/postgresql/data` volume; private TCP 5432 |
| SQLMesh Warehouse | Raw input, physical tables and production views | Separate 5 GB `/var/lib/postgresql/data` volume; private TCP 5432 |

SQLMesh is pinned to `0.236.2`, Python to `3.12.15`, uv to `0.12.22`, and PostgreSQL to a digest resolving to `16.15`. Python dependencies and Railway IaC dependencies have committed locks. SQLMesh anonymous analytics are disabled. No shared service filesystem, Docker socket, external orchestrator, browser UI or public database proxy is required.

The Railway cron schedule is **`0 * * * *` (UTC)** with restart policy **`NEVER`**. Each invocation checks the private databases with a bounded wait, refuses uninitialized `prod`, and replaces itself with `sqlmesh run prod`. Models run daily: hourly scheduling checks for eligible daily intervals rather than repeatedly rebuilding completed days. Failures remain nonzero; no crash-loop restart masks an audit failure.

## Models and fixture

`raw.orders` is an external input contract. The explicit fixture loader creates five orders spanning September 29–October 1, 2026; it is never called by the scheduled runner. `analytics.staged_orders` normalizes status and processes only the requested date window. `analytics.daily_revenue` counts paid orders and excludes cancelled orders. Expected outputs are `(2026-09-29, 2, 20.00)`, `(2026-09-30, 1, 30.00)`, `(2026-10-01, 1, 40.00)`.

Three SQLMesh unit tests cover windowing, normalization, cancellation, aggregation and an empty paid set. Built-in not-null / uniqueness audits and custom nonnegative amount / revenue audits block invalid materializations. The fixed model start date is for this fixture; change it and review a new plan for real source history. There is no ingestion service: supply your own raw data independently.

## Local use

Install Docker Compose, uv, Bun, Python 3 and `jq`. No host database ports are published. Create local-only secrets in your terminal (do not commit them):

```bash
export STATE_PASSWORD="$(openssl rand -hex 24)"
export WAREHOUSE_PASSWORD="$(openssl rand -hex 24)"
docker compose build runner
docker compose up -d --wait --wait-timeout 90 state warehouse
docker compose run --rm runner python scripts/fixture.py
docker compose run --rm runner sqlmesh test
```

### Review, then explicitly approve

Scheduled runs **never plan or apply**. The initial plan and every subsequent model change require an operator, including changes to audits. Review the SQL source, target databases, categories and bounded missing intervals before approving; `sqlmesh diff prod` can display the local/state differences separately. The following clock and range are deterministic fixture values, not a recommended production backfill:

```bash
docker compose run --rm runner python scripts/plan.py review \
  --execution-time 2026-09-30
# Read the JSON review's SQL source, categories, intervals and targets before copying approval_sha256.
docker compose run --rm runner python scripts/plan.py apply \
  --execution-time 2026-09-30 --approve REVIEWED_SHA256
docker compose run --rm runner ./start.sh \
  --end 2026-09-30
docker compose run --rm runner python scripts/assert-results.py --through 2026-09-30
```

SQLMesh 0.236.2 does not permit start/end overrides on normal production plans without restatements. The baked model start and explicit execution time determine eligible intervals; inspect the exact range in the review document. The fixture execution time `2026-09-30` makes only September 29 eligible. Use the real execution time and an appropriate model start for actual workloads. Planning can initialize SQLMesh state metadata, but never applies model changes during review.

Approval is a content hash, **not authentication**: operator access to the database remains powerful. The JSON review includes readable SQL model/audit source, snapshot fingerprints/categories, target host/database/user/TLS settings, range, previous production plan and pending intervals. Application recomputes the plan and refuses a missing or stale approval. SQLMesh `context.apply` additionally checks environment consistency. Pause scheduling and serialize operator changes to avoid review/apply races. Do not put approval hashes or planning commands into cron defaults. `sqlmesh plan prod` is also available for interactive expert use, but never set `--auto-apply` on scheduled jobs.

Use separate `docker compose run --rm runner ./start.sh` containers for normal jobs. Replacing a runner does not replace state or warehouse volumes. SQLMesh runs persisted production snapshots, not unapproved local changes. Stop the schedule before changing data contracts; do not confuse successful old-snapshot runs with promotion of new source.

Cleanup affects only this template's explicit local project:

```bash
docker compose -p rt-sqlmesh-cb5c13c4 down --volumes
```

This deletes both local databases. Do not use it on data you need to preserve.

## Railway setup (not yet cloud-verified)

The standalone source is `tech-progress/sqlmesh-transformations`, with real `release-v1` compatibility channel and immutable `v1.0.0` tag, root `/`. Fork maintainers must set `TEMPLATE_SOURCE_REPO` to their own actual accessible repository and authorize Railway's GitHub App; public visibility alone is not proof of source authorization. `TEMPLATE_SOURCE_BRANCH` defaults to slash-free `release-v1`; `TEMPLATE_SOURCE_ROOT` defaults to `/`. Monorepo maintainers may explicitly select `/sqlmesh-transformations`. Build watch patterns follow the selected root. Independent native secret expressions generate distinct database passwords; never use deterministic SDK `randomString` for published credentials.

```bash
bun install --frozen-lockfile
TEMPLATE_SOURCE_REPO=tech-progress/sqlmesh-transformations \
TEMPLATE_SOURCE_BRANCH=release-v1 \
TEMPLATE_SOURCE_ROOT=/ \
bun scripts/evaluate-iac.ts
```

`evaluate-iac.ts` evaluates the pinned SDK locally, retaining its resource nodes and exposing mount edges from `volumeAttachments`; it never calls the Railway API. This is an offline contract representation, not proof of a cloud plan/import. Railway SDK 3.12.0's legacy `railway-iac-ts` executable is a compatibility error stub; actual native cloud IaC execution requires Railway CLI 5.42.1 or newer and separate authorization.

The three services are private; do not generate domains or database TCP proxies. Databases start independently and the runner has bounded readiness retries. A freshly provisioned cron runner deliberately fails until an operator initializes `prod`. Arrange a one-off operator execution of the **same image/source** inside the Railway project private network with the runner credentials, load the fixture only if desired, run tests, review and approve a bounded initial plan, then enable hourly cron. An exiting cron service is not an always-running SSH target: this template does not invent a tested Railway one-off CLI command. Validate your current operator execution method in the disposable draft gate described in `PUBLISHING.md`.

### Required variables

All production values come from `template-defaults.json`; human descriptions are in `template-descriptions.json`. Local examples are in `.env.example`.

| Variables | Required / default |
| --- | --- |
| `STATE_HOST`, `STATE_DATABASE`, `STATE_USER`, `STATE_PASSWORD` | Required. Private State service DNS and cross-service database/user/secret references |
| `WAREHOUSE_HOST`, `WAREHOUSE_DATABASE`, `WAREHOUSE_USER`, `WAREHOUSE_PASSWORD` | Required. Independent Warehouse references; never reuse the State database |
| `STATE_PORT`, `WAREHOUSE_PORT` | Optional configuration defaults `5432`; recipe explicitly sets both |
| `STATE_SSLMODE`, `WAREHOUSE_SSLMODE` | Optional defaults `prefer`; use `require` for a TLS-enabled external backend |
| `PYTHONPATH` | Recipe/image sets `/app`; local Python scripts need project root, for example `.` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Each database requires its own values; recipe uses `sqlmesh_state` / `warehouse`, user `sqlmesh`, independent generated 32-character passwords |
| `PGDATA` | Both database services: `/var/lib/postgresql/data/pgdata` inside their independent volumes |
| `TEMPLATE_SOURCE_REPO`, `TEMPLATE_SOURCE_BRANCH`, `TEMPLATE_SOURCE_ROOT` | IaC authoring only; not application secrets or deployed runner variables |

No `PORT`, public URL, approval variable or auto-apply variable is required. Private networking plus `sslmode=prefer` is not end-to-end encrypted PostgreSQL: use a verified TLS deployment if policy requires encryption.

## Verification and operations

```bash
bun install --frozen-lockfile
./scripts/verify.sh
./scripts/workflow-smoke.sh
```

The workflow builds the exact image, starts both databases with bounded waits, tests models, rejects missing/stale approval, applies an explicitly approved **test fixture** plan, checks daily results, deliberately fails/repairs a blocking audit, replaces containers, refuses changed-source approval, proves cron does not promote changed models, destroys/recreates both databases, restores both logical dumps, reruns production, compares logical persisted intervals, and tests the exact no-argument Railway startup command. It cleans its own containers/volumes and refuses a preexisting `rt-sqlmesh-cb5c13c4` project rather than deleting someone else's resources. Operator fixture automation is not the deployment startup path.

Draft restoration/audit is offline JSON transformation only, with no token lookup or remote calls. `verify.sh` tests a deliberately contaminated draft; it does not certify live Railway deployment/publication. See `SUPPORT.md` for limits and `UPGRADE.md` for coordinated backup/restore. `THIRD_PARTY_NOTICES.md` and `runtime-license-inventory.json` describe the exact source-build artifact and retained upstream obligations. Public source is not a reusable Railway template until independently qualified and published.
