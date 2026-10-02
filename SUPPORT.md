# Support boundary

This is a single-node evaluation starter with a small fixture, not HA, managed ingestion, or a production-scale warehouse. A successful job proves the tested intervals only. Budget separately for three services, durable volumes and backups; no memory/CPU recommendation is cloud-validated yet.

- Uninitialized `prod`: expected failure. Arrange a private-network operator job, run tests, review a bounded plan and explicitly approve it. Never auto-apply in cron to hide initialization errors.
- Database readiness: each connection has a 10-second connect timeout and at most 12 attempts with 2-second spacing; a total invocation is finite. Confirm private DNS, port and referenced secrets. Do not open a public proxy as a workaround.
- Audit failure: job exits nonzero. Find and repair bad raw data; failed intervals remain pending. SQLMesh may have materialized data before audit failure, so never consume a newly failed physical table as approved output. Retry the interval after repair; use reviewed restatement plans for already completed history.
- Changed source: scheduled runs use persisted production snapshots until a reviewed plan promotes the change. Pause scheduling for operator plans and upgrades. Monitor job outcomes and age of the latest successful daily interval, not an HTTP healthcheck.
- Cron overlap: Railway does not start the next scheduled run while the prior run remains active. This daily fixture is small; tune workload batching before extending it. Restart is `NEVER` by contract.
- Credentials: generated passwords are independent and should remain stable across redeploys. Database-owner privileges are intentionally broad for evaluation; use narrower roles and enforce TLS according to your production security requirements.
- State/warehouse split: back up and restore **both** at a coordinated quiescent boundary. A state-only restore can claim completed intervals whose warehouse tables are absent. There is no shared filesystem or runner volume to restore.

The draft tools operate offline and do not perform cloud restoration. See `PUBLISHING.md` for pending live validation and `FINDINGS.md` for exact local evidence.
