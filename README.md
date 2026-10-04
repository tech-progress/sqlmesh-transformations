# SQLMesh transformations

The current template release is `v1.0.4` (see [VERSION](VERSION)). This is a single-node evaluation starter, not a highly available warehouse or unattended schema-change system. This release must be qualified independently. A source release does not prove marketplace publication; consult the maintainer's marketplace registry for publication status and any final deploy link.

Upstream products: [SQLMesh](https://github.com/SQLMesh/sqlmesh) ([documentation](https://sqlmesh.readthedocs.io/en/stable/)) and [PostgreSQL](https://www.postgresql.org/).

## What deploys

| Service | Purpose | Persistence / network |
| --- | --- | --- |
| SQLMesh Runner | Baked SQL models, unit tests, blocking audits; exits after `sqlmesh run prod` | No volume, no HTTP server, no public domain or healthcheck |
| SQLMesh State | SQLMesh snapshots, production environment and processed intervals | Independent 5000 MB `/var/lib/postgresql/data` volume; private TCP 5432 |
| SQLMesh Warehouse | Raw input, physical tables and production views | Separate 5000 MB `/var/lib/postgresql/data` volume; private TCP 5432 |

Exact runtime pins are in [Dockerfile](Dockerfile), [compose.yaml](compose.yaml), [uv.lock](uv.lock) and [.railway/railway.ts](.railway/railway.ts); Python and Railway IaC dependencies have committed locks. SQLMesh anonymous analytics are disabled. No shared service filesystem, Docker socket, external orchestrator, browser UI or public database proxy is required.

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

## Railway setup

Historical `v1.0.3` qualification confirmed source fetch, private operator tests, reviewed plan/application, incremental results, blocking audit failure/repair, runner replacement and coordinated two-database restoration. A manual exact-deployment restart executed the restored default job and left no running runner instance. Its `SUCCESS` / `buildOnly` metadata alone did not prove job completion; native job logs and instance state supplied the bounded runtime evidence. No explicit numeric exit-code field or real hourly scheduler firing was observed in that historical run. These results do not qualify a new source revision, database pin or stored template graph. See [PUBLISHING.md](PUBLISHING.md) for fresh qualification gates.

### Initial private-network operator session

An uninitialized production environment deliberately fails its cron job; initialization is never silently auto-approved. Use this explicit temporary maintenance configuration to obtain an operator process inside Railway's private network:

1. Wait for both private databases to be healthy. Explicitly select the intended project, environment and runner service. Pause scheduling by clearing the runner's cron schedule and temporarily set its Start Command to `sleep 1800` in Railway's service settings. Keep restart `NEVER`, no public domain/proxy and the same exact source commit. Deploy that maintenance configuration and inspect the actual deployment manifest and current instance; mutable service settings alone do not establish what a redeploy used. It expires after 30 minutes; do not leave it as the production start command.
2. Use `railway ssh --service "SQLMesh Runner" -- python scripts/fixture.py` **only for synthetic evaluation data**. Real installations provide their own `raw.orders` data. Run `railway ssh --service "SQLMesh Runner" -- sqlmesh test`, then `railway ssh --service "SQLMesh Runner" -- python scripts/plan.py review --execution-time 2026-09-30`. Inspect the complete readable SQL, database targets, categories and bounded intervals. Dates shown here are fixture dates, not an instruction to backfill real data to that date.
3. Only after operator review, run `railway ssh --service "SQLMesh Runner" -- python scripts/plan.py apply --execution-time 2026-09-30 --approve REVIEWED_SHA256`. The command recomputes the plan against those targets and rejects stale or missing approval. Pause other operators and scheduling during review/apply.
4. Stop the maintenance deployment. Restore Start Command `./start.sh`, cron `0 * * * *`, restart `NEVER` and no healthcheck/public networking; deploy the same intended source. Read back the actual deployment manifest. Observe a real hourly scheduler firing, native completed-job outcome and persisted intervals; a manual restart is a separate check. A cron runner normally has no continuously running instance between completed jobs; the databases remain running. Build-only `SUCCESS` and database readiness do not establish SQL job success.

SSH uses your own registered Railway key and the explicitly selected project/environment. Do not use local `railway run` as proof that private hostnames are reachable from your workstation, borrow another user's key or expose either database publicly to simplify initialization.

The public standalone source is [tech-progress/sqlmesh-transformations](https://github.com/tech-progress/sqlmesh-transformations), with real `main` and slash-free `release-v1` compatibility channel, root `/`. Select the immutable tag corresponding to [VERSION](VERSION) only after the release owner creates and verifies it; do not infer source promotion from these docs. Historical immutable `v1.0.3` is commit `24b86e70ea8b747a7a999c83b595eb07dbd80604`. Historical tags are not moved; `v1.0.0` lacks the required inventory and `v1.0.2` has a documentation-version mismatch, so neither is a qualified deployment release. Fork maintainers must set `TEMPLATE_SOURCE_REPO` to their own actual accessible repository and authorize Railway's GitHub App; public visibility alone is not proof of source authorization. `TEMPLATE_SOURCE_BRANCH` defaults to slash-free `release-v1`; `TEMPLATE_SOURCE_ROOT` defaults to `/`. Monorepo maintainers may explicitly select `/sqlmesh-transformations`. Build watch patterns follow the selected root. Independent native secret expressions generate distinct database passwords; never use deterministic SDK `randomString` for published credentials.

```bash
bun install --frozen-lockfile
TEMPLATE_SOURCE_REPO=tech-progress/sqlmesh-transformations \
TEMPLATE_SOURCE_BRANCH=release-v1 \
TEMPLATE_SOURCE_ROOT=/ \
bun scripts/evaluate-iac.ts
```

`evaluate-iac.ts` evaluates the pinned SDK locally, retaining its resource nodes and exposing mount edges from `volumeAttachments`; it never calls the Railway API. This is an offline contract representation, not proof of a cloud plan/import. Railway SDK 3.12.0's legacy `railway-iac-ts` executable is a compatibility error stub; native cloud IaC execution requires Railway CLI 5.42.1 or newer and an authorized, explicitly scoped operation.

All three services are private; do not generate domains or database TCP proxies. Databases start independently and the runner has bounded readiness retries. A freshly provisioned cron runner deliberately fails until an operator initializes `prod` through an explicit reviewed plan. The maintenance session above is bounded operator access to the **same image/source** inside the project private network, not a continuously running runner. Load the fixture only if desired, run tests, review and approve a bounded initial plan, then restore hourly cron. Validate the operator route for the current release in the disposable gate described in [PUBLISHING.md](PUBLISHING.md).

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
node scripts/verify-docs.mjs
node --test tests/docs.test.mjs
./scripts/verify.sh
./scripts/workflow-smoke.sh
```

The workflow builds the exact image, starts both databases with bounded waits, tests models, rejects missing/stale approval, applies an explicitly approved **test fixture** plan, checks daily results, deliberately fails/repairs a blocking audit, replaces containers, refuses changed-source approval, proves cron does not promote changed models, destroys/recreates both databases, restores both logical dumps, reruns production, compares logical persisted intervals, and tests the exact no-argument Railway startup command. It cleans its own containers/volumes and refuses a preexisting `rt-sqlmesh-cb5c13c4` project rather than deleting someone else's resources. Operator fixture automation is not the deployment startup path.

Draft restoration/audit scripts perform offline JSON transformation only, with no token lookup or remote calls. `verify.sh` tests a deliberately contaminated draft; it does not certify live Railway deployment/publication. See [SUPPORT.md](SUPPORT.md) for limits and [UPGRADE.md](UPGRADE.md) for coordinated backup/restore. [LICENSE](LICENSE) grants MIT for newly authored recipe code only. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [runtime-license-inventory.json](runtime-license-inventory.json) retain upstream obligations; source-only licensing does not relabel combined runtime binaries or grant security clearance. Public source and a stored draft do not establish reusable marketplace publication.
