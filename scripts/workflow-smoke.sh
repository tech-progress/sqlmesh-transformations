#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${root}"
project=rt-sqlmesh-cb5c13c4
if [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=${project}")" || -n "$(docker volume ls -q --filter "label=com.docker.compose.project=${project}")" ]]; then
  echo "Refusing to overwrite existing ${project} resources; clean your own previous run first." >&2
  exit 1
fi
export STATE_PASSWORD="$(openssl rand -hex 24)" WAREHOUSE_PASSWORD="$(openssl rand -hex 24)"
compose=(docker compose -p "${project}" -f compose.yaml)
evidence="$(mktemp -d /tmp/rt-sqlmesh-cb5c13c4-evidence.XXXXXX)"
cleanup() {
  local status=0
  timeout 90 "${compose[@]}" down --volumes --remove-orphans >"${evidence}/cleanup.log" 2>&1 || status=$?
  rm -f "${evidence}/state.sql" "${evidence}/warehouse.sql"
  if (( status != 0 )); then echo "Owned-resource cleanup failed (${status}); inspect ${evidence}/cleanup.log" >&2; fi
  return "${status}"
}
trap cleanup EXIT
run() { timeout 180 "${compose[@]}" run --rm --no-deps -T runner "$@"; }
expect_failure() {
  local logfile="$1"; shift
  local status=0
  run "$@" >"${evidence}/${logfile}" 2>&1 || status=$?
  if (( status == 0 || status == 124 || status == 137 )); then
    echo "Expected explicit nonzero failure, got ${status}: ${logfile}" >&2; exit 1
  fi
  printf '%s exit=%s\n' "${logfile}" "${status}" | tee -a "${evidence}/status.txt"
}
timeout 900 "${compose[@]}" build runner >"${evidence}/build.log" 2>&1
timeout 120 "${compose[@]}" up -d --wait --wait-timeout 90 state warehouse
expect_failure uninitialized.log ./start.sh
grep -Fq 'review and explicitly approve' "${evidence}/uninitialized.log"
run python scripts/fixture.py
run sqlmesh test >"${evidence}/model-tests.log" 2>&1
run python scripts/plan.py review --execution-time 2026-09-30 --output /tmp/review.json >"${evidence}/review.log" 2>&1
approval="$(sed -n 's/.*"approval_sha256": "\([a-f0-9]*\)".*/\1/p' "${evidence}/review.log")"
[[ "${approval}" =~ ^[a-f0-9]{64}$ ]]
expect_failure missing-approval.log python scripts/plan.py apply --execution-time 2026-09-30
expect_failure wrong-approval.log python scripts/plan.py apply --execution-time 2026-09-30 --approve wrong
grep -Fq 'approval does not match' "${evidence}/wrong-approval.log"
run python scripts/plan.py apply --execution-time 2026-09-30 --approve "${approval}" >"${evidence}/apply.log" 2>&1
run python scripts/assert-results.py --through 2026-09-29 >"${evidence}/first-day.json"
run ./start.sh --end 2026-09-30 >"${evidence}/incremental.log" 2>&1
run python scripts/assert-results.py --through 2026-09-30 >"${evidence}/second-day.json"
run python scripts/fixture.py --bad-audit
expect_failure blocking-audit.log ./start.sh --end 2026-10-01
grep -Fq nonnegative_amount "${evidence}/blocking-audit.log"
run python scripts/assert-results.py --through 2026-09-30 >"${evidence}/after-audit.json"
cmp "${evidence}/second-day.json" "${evidence}/after-audit.json"
run python scripts/fixture.py --repair-audit
run ./start.sh --end 2026-10-01 >"${evidence}/third-day.log" 2>&1
run python scripts/assert-results.py --through 2026-10-01 >"${evidence}/before-replacement.json"
run ./start.sh --end 2026-10-01 >"${evidence}/replacement.log" 2>&1
run python scripts/assert-results.py --through 2026-10-01 >"${evidence}/after-replacement.json"
cmp "${evidence}/before-replacement.json" "${evidence}/after-replacement.json"
run python scripts/plan.py review --execution-time 2026-10-02 >"${evidence}/current-review.log" 2>&1
current_approval="$(sed -n 's/.*"approval_sha256": "\([a-f0-9]*\)".*/\1/p' "${evidence}/current-review.log")"
run python scripts/probe-changed-source.py --approve "${current_approval}" >"${evidence}/changed-source.log" 2>&1
grep -Fq 'approval does not match' "${evidence}/changed-source.log"
run python scripts/assert-results.py --through 2026-10-01 >"${evidence}/after-changed-source.json"
cmp "${evidence}/before-replacement.json" "${evidence}/after-changed-source.json"
timeout 90 "${compose[@]}" exec -T state pg_dump -U sqlmesh -d sqlmesh_state --no-owner --no-privileges >"${evidence}/state.sql"
timeout 90 "${compose[@]}" exec -T warehouse pg_dump -U sqlmesh -d warehouse --no-owner --no-privileges >"${evidence}/warehouse.sql"
timeout 90 "${compose[@]}" down --volumes
timeout 120 "${compose[@]}" up -d --wait --wait-timeout 90 state warehouse
timeout 90 "${compose[@]}" exec -T state psql -X -v ON_ERROR_STOP=1 -U sqlmesh -d sqlmesh_state <"${evidence}/state.sql" >"${evidence}/restore-state.log"
timeout 90 "${compose[@]}" exec -T warehouse psql -X -v ON_ERROR_STOP=1 -U sqlmesh -d warehouse <"${evidence}/warehouse.sql" >"${evidence}/restore-warehouse.log"
run python scripts/assert-results.py --through 2026-10-01 >"${evidence}/after-restore.json"
cmp "${evidence}/before-replacement.json" "${evidence}/after-restore.json"
run ./start.sh --end 2026-10-01 >"${evidence}/restored-run.log" 2>&1
run python scripts/assert-results.py --through 2026-10-01 >"${evidence}/restored-run.json"
cmp "${evidence}/after-restore.json" "${evidence}/restored-run.json"
run ./start.sh >"${evidence}/railway-default-start.log" 2>&1
run python scripts/assert-results.py --through 2026-10-01 --interval-through "$(date -u -d yesterday +%F)" >"${evidence}/railway-default-start.json"
cleanup
trap - EXIT
[[ -z "$(docker ps -aq --filter "label=com.docker.compose.project=${project}")" ]]
[[ -z "$(docker volume ls -q --filter "label=com.docker.compose.project=${project}")" ]]
printf 'PASS: models, reviewed plan, incremental results, replacement, stale approval, changed source, blocking audit, paired restore, exact Railway start command, zero containers/volumes. Evidence: %s\n' "${evidence}" | tee "${evidence}/result.txt"
