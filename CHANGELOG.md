# Changelog

## [1.0.1] - 2026-10-02

- Include the reviewed runtime license inventory required by the minimal multi-stage image.
- Make standalone static checks reject missing runtime notice/inventory build inputs.
- Preserve the original v1.0.0 tag; it lacks the required inventory and is not a qualified deployment release.

## [1.0.0] - 2026-10-02
- Private, independent PostgreSQL state and warehouse services with durable volumes.
- SQLMesh 0.236.2 fixture models, tests, blocking audits, and hourly exiting runner.
- Content-bound, explicitly reviewed plan approval; no cron planning or automatic changes.
- Offline draft repair/audit and local incremental, replacement, failure, and restore gates.
