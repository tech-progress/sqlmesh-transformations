#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${root}"
required_files=(
  .dockerignore .env.example .gitignore .railway/railway.ts Dockerfile compose.yaml
  config.py pyproject.toml uv.lock package.json bun.lock VERSION CHANGELOG.md
  THIRD_PARTY_NOTICES.md runtime-license-inventory.json
  README.md MARKETPLACE.md SUPPORT.md UPGRADE.md LICENSE
  marketplace-metadata.json template-defaults.json template-descriptions.json
  template-networking.json template-volumes.json external_models.yaml start.sh
  models/staged_orders.sql models/daily_revenue.sql audits/quality.sql
  tests/test_orders.yaml tests/test_template_contract.py
  scripts/verify.sh scripts/workflow-smoke.sh scripts/smoke.sh scripts/plan.py
  scripts/check-ready.py scripts/assert-results.py scripts/fixture.py scripts/probe-changed-source.py
  scripts/evaluate-iac.ts scripts/template-contract.py scripts/restore-template-draft.sh scripts/audit-template.sh
  scripts/verify-docs.mjs tests/docs.test.mjs
)
for file in "${required_files[@]}"; do test -f "${file}" || { echo "Missing ${file}" >&2; exit 1; }; done
version="$(<VERSION)"
[[ "${version}" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]
grep -Eq "^## \[${version//./\\.}\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" CHANGELOG.md
grep -Fq "current template release is \`v${version}\`" README.md
for heading in '# Deploy and Host' '## About Hosting' '## Why Deploy' '## Common Use Cases' '## Dependencies for' '### Deployment Dependencies'; do grep -Fq "${heading}" MARKETPLACE.md; done
for file in *.json; do jq empty "${file}"; done
jq -e '.directory=="sqlmesh-transformations" and .name=="SQLMesh transformations" and .category=="Analytics" and (.description|length)>=45 and (.description|length)<=75 and (.icon|contains("/web/client/public/favicons/favicon.svg")) and (has("id")|not) and (has("code")|not) and (has("distributionRepo")|not)' marketplace-metadata.json >/dev/null
while IFS= read -r origin; do grep -Fq "${origin}" README.md; grep -Fq "${origin}" MARKETPLACE.md; done < <(jq -r '.origins[].url' marketplace-metadata.json)
jq -e --slurpfile descriptions template-descriptions.json 'to_entries|all(. as $service|(.value|keys|sort)==($descriptions[0][$service.key]|keys|sort))' template-defaults.json >/dev/null
for script in start.sh scripts/*.sh; do bash -n "${script}"; test -x "${script}"; done
python3 -m py_compile config.py scripts/*.py tests/test_template_contract.py
uv lock --check --offline
export STATE_PASSWORD=structure-validation-only WAREHOUSE_PASSWORD=structure-validation-only
compose_json="$(docker compose -p rt-sqlmesh-cb5c13c4 config --format json)"
jq -e '.services|all(.ports==null) and (.runner.volumes==null) and (.runner.restart=="no")' <<<"${compose_json}" >/dev/null
graph="$(mktemp /tmp/sqlmesh-offline-graph.XXXXXX.json)"
alternate="$(mktemp /tmp/sqlmesh-offline-alternate.XXXXXX.json)"
trap 'rm -f "${graph}" "${alternate}"' EXIT
TEMPLATE_SOURCE_REPO=fixture-owner/fixture-source TEMPLATE_SOURCE_BRANCH=release-v1 TEMPLATE_SOURCE_ROOT=sqlmesh-transformations bun scripts/evaluate-iac.ts >"${graph}"
TEMPLATE_SOURCE_REPO=fixture-owner/alternate-source TEMPLATE_SOURCE_BRANCH=release-v2 TEMPLATE_SOURCE_ROOT=/ bun scripts/evaluate-iac.ts >"${alternate}"
jq -e '.graph.resources[]|select(.name=="SQLMesh Runner")|.source.repo=="fixture-owner/alternate-source" and .source.branch=="release-v2" and .source.rootDirectory=="/" and .build.watchPatterns==["/**"]' "${alternate}" >/dev/null
SQLMESH_TEST_GRAPH="${graph}" python3 -m unittest discover -s tests -p test_template_contract.py -v
node scripts/verify-docs.mjs
node --test tests/*.test.mjs
grep -Fq 'exec sqlmesh run prod "$@"' start.sh
if grep -Eq 'auto.apply|sqlmesh plan|scripts/plan.py' start.sh; then echo 'Cron may not plan/apply' >&2; exit 1; fi
grep -Fq 'name = "sqlmesh"' uv.lock
grep -Fq 'version = "0.236.2"' uv.lock
if find . -path './node_modules' -prune -o -path './.venv' -prune -o -path './.local' -prune -o -type f \( -name .env -o -name '*.local' \) -print | grep -q .; then echo 'Local secret file found' >&2; exit 1; fi
echo 'PASS: scoped structure, pins, locks, metadata, private compose, configurable offline IaC, distinct mount edges, contaminated draft repair/audit.'
