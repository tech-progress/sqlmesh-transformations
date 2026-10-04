import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = new URL('../', import.meta.url);
const read = filename => readFileSync(new URL(filename, root), 'utf8');
const releaseDocuments = ['README.md', 'PUBLISHING.md', 'SUPPORT.md', 'UPGRADE.md', 'MARKETPLACE.md'];
const publicDocuments = [...releaseDocuments, 'CHANGELOG.md'];
const publicLinkTargets = new Set([
  ...publicDocuments, 'VERSION', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
  'runtime-license-inventory.json', 'Dockerfile', 'compose.yaml', 'uv.lock', '.railway/railway.ts',
]);

export function loadDocumentation() {
  return {
    version: read('VERSION').trim(),
    metadata: JSON.parse(read('marketplace-metadata.json')),
    defaults: JSON.parse(read('template-defaults.json')),
    volumes: JSON.parse(read('template-volumes.json')),
    networking: JSON.parse(read('template-networking.json')),
    railwaySource: read('.railway/railway.ts'),
    startup: read('start.sh'),
    documents: Object.fromEntries(publicDocuments.map(filename => [filename, read(filename)])),
  };
}

export function verifyDocumentation({ version, metadata, defaults, volumes, networking, railwaySource, startup, documents }, { checkVersion = true } = {}) {
  assert.match(version, /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/, 'VERSION: SemVer required');
  const declaredVersions = releaseDocuments.map(filename => {
    const text = documents[filename];
    const declaration = filename === 'README.md'
      ? /The current template release is `v([\d.]+)`/g
      : /Template release \*\*v([\d.]+)\*\*/g;
    const releases = [...text.matchAll(declaration)];
    assert.equal(releases.length, 1, `${filename}: one release declaration required`);
    if (checkVersion) assert.equal(releases[0][1], version, `${filename}: release must match VERSION`);
    assert.ok(text.includes('This release must be qualified independently.'), `${filename}: independent qualification required`);
    assert.ok(text.includes('A source release does not prove marketplace publication'), `${filename}: source/publication distinction required`);
    assert.ok(text.includes('[VERSION](VERSION)'), `${filename}: authoritative VERSION link required`);
    assert.match(text, /historical[\s\S]*v1\.0\.3/i, `${filename}: historical evidence must be identified`);
    assert.match(text, /(?:hourly scheduler firing[^.\n]*not observed|[Nn]o[^.\n]*hourly scheduler firing[^.\n]*observed|no observed hourly scheduler firing)/, `${filename}: unobserved historical scheduler limit required`);
    return releases[0][1];
  });
  assert.equal(new Set(declaredVersions).size, 1, 'release documents: declarations must agree');
  const changelogVersion = checkVersion ? version : declaredVersions[0];
  assert.match(documents['CHANGELOG.md'], new RegExp(`^## \\[${changelogVersion.replaceAll('.', '\\.')}\\] - \\d{4}-\\d{2}-\\d{2}$`, 'm'), 'CHANGELOG.md: release entry required');

  const readme = documents['README.md'];
  for (const filename of ['README.md', 'PUBLISHING.md', 'UPGRADE.md', 'MARKETPLACE.md']) {
    for (const coordinate of ['tech-progress/sqlmesh-transformations', '`main`', '`release-v1`', 'root `/`']) {
      assert.ok(documents[filename].includes(coordinate), `${filename}: standalone source coordinates required`);
    }
  }
  for (const key of new Set(Object.values(defaults).flatMap(service => Object.keys(service)))) {
    assert.ok(readme.includes('`' + key + '`'), `README.md: graph variable ${key} required`);
  }
  assert.deepEqual(Object.keys(defaults).sort(), ['SQLMesh Runner', 'SQLMesh State', 'SQLMesh Warehouse'], 'three-service defaults required');
  for (const [keys, expected] of [
    [['STATE_PORT', 'WAREHOUSE_PORT'], '5432'],
    [['STATE_SSLMODE', 'WAREHOUSE_SSLMODE'], 'prefer'],
    [['PYTHONPATH'], '/app'],
  ]) {
    const row = readme.split('\n').find(line => line.startsWith('| `' + keys[0] + '`'));
    assert.ok(row?.includes('`' + expected + '`'), `README.md: connection default ${keys.join('/')} required`);
    for (const key of keys) assert.equal(defaults['SQLMesh Runner'][key], expected, `${key}: connection default must match documentation`);
  }
  assert.ok(Object.values(networking).every(service => service.public === false), 'private networking contract required');
  assert.deepEqual(Object.keys(networking).sort(), Object.keys(defaults).sort(), 'all three services must be private');
  assert.deepEqual(Object.keys(volumes).sort(), ['SQLMesh State', 'SQLMesh Warehouse'], 'two database volumes required');
  assert.equal(new Set(Object.values(volumes).map(volume => volume.key)).size, 2, 'independent volume keys required');
  assert.ok(Object.values(volumes).every(volume => volume.sizeMB === 5000 && volume.mountPath === '/var/lib/postgresql/data'), 'independent 5000 MB volume contract required');
  assert.match(railwaySource, /start: "\.\/start\.sh"/, 'Railway default startup must match docs');
  assert.match(railwaySource, /cronSchedule: "0 \* \* \* \*", restartPolicyType: "NEVER"/, 'hourly/NEVER source contract must match docs');
  assert.match(startup, /exec sqlmesh run prod "\$@"/, 'native production startup required');
  assert.doesNotMatch(startup, /auto.apply|sqlmesh plan|scripts\/plan\.py/, 'scheduled startup must never plan/apply');

  for (const filename of releaseDocuments) {
    const text = documents[filename];
    for (const literal of ['5000 MB', '`0 * * * *`', '`NEVER`', '`./start.sh`']) {
      assert.ok(text.includes(literal), `${filename}: documented runtime default ${literal} required`);
    }
    assert.match(text, /(?:refus\w*[^.\n]*(?:uninitialized|no-prod)|(?:uninitialized|no-prod)[^.\n]*refus\w*)/i, `${filename}: expected fresh-default refusal required`);
    assert.match(text, /explicit[\s\S]*review[\s\S]*plan/i, `${filename}: explicit reviewed bootstrap required`);
    assert.match(text, /no continuously running (?:runner|instance)|not a continuously running runner/i, `${filename}: exiting runner boundary required`);
    assert.match(text, /build-only|buildOnly/i, `${filename}: build-only outcome distinction required`);
    assert.match(text, /readiness/i, `${filename}: readiness is not job success required`);
  }
  for (const filename of ['README.md', 'PUBLISHING.md']) {
    assert.match(documents[filename], /three (?:private )?services|three services are private/i, `${filename}: three private services required`);
    assert.match(documents[filename], /two independent (?:5000 MB database )?volumes|independent 5000 MB/i, `${filename}: independent database storage required`);
  }
  assert.ok(readme.includes('sleep 1800') && documents['UPGRADE.md'].includes('sleep 1800'), 'bounded private maintenance required');
  assert.match(readme, /Stop the maintenance deployment[\s\S]*Restore Start Command/, 'maintenance settings must be restored');
  assert.match(readme, /MIT for newly authored recipe code only/, 'recipe-only MIT license distinction required');
  assert.match(readme, /does not relabel combined runtime binaries or grant security clearance/, 'upstream/runtime license and security boundary required');

  for (const filename of ['README.md', 'MARKETPLACE.md']) {
    for (const origin of metadata.origins) assert.ok(documents[filename].includes(origin.url), `${filename}: main upstream URL required`);
  }
  assert.ok(metadata.description.length >= 45 && metadata.description.length <= 75, 'marketplace description must be 45–75 characters');
  assert.ok(documents['MARKETPLACE.md'].includes(metadata.description), 'marketplace description must match metadata');
  assert.deepEqual(documents['MARKETPLACE.md'].match(/^#{1,3} .+$/gm), [
    `# Deploy and Host ${metadata.name} on Railway`,
    `## About Hosting ${metadata.name}`,
    `## Why Deploy ${metadata.name} on Railway`,
    '## Common Use Cases',
    `## Dependencies for ${metadata.name}`,
    '### Deployment Dependencies',
  ], 'six exact marketplace headings required');
  assert.ok(!Object.hasOwn(metadata, 'id') && !Object.hasOwn(metadata, 'code'), 'publication identifiers belong in registry only');

  const publishing = documents['PUBLISHING.md'];
  for (const phrase of ['queried stored graph', 'templateDeployV2', 'existing UNPUBLISHED draft', 'zero running/transitional instances', 'zero queued work']) {
    assert.ok(publishing.includes(phrase), `PUBLISHING.md: required gate ${phrase}`);
  }
  for (const command of ['node scripts/verify-docs.mjs', 'node --test tests/docs.test.mjs', 'scripts/sync-template-marketplace.sh sqlmesh-transformations', 'scripts/audit-template-marketplace.sh']) {
    assert.ok(publishing.includes(command), `PUBLISHING.md: verification command ${command} required`);
  }
  assert.ok(publishing.includes("Standard deletion plus verified zero compute and disclosed retention satisfies the owner's cleanup policy."), 'accepted cleanup policy required');
  assert.ok(publishing.includes('Physical storage deletion and billing-zero proof are not publication gates under the accepted policy.'), 'physical-erasure/billing boundary required');

  for (const [filename, text] of Object.entries(documents)) {
    assert.doesNotMatch(text, /FINDINGS\.md|LICENSE_REVIEW\.md|\/tmp\/|\.verification\b|worker\d/i, `${filename}: private evidence references must not be distributed`);
    assert.doesNotMatch(text, /af87989d-c625-4fdc-b519-88d72f4129fa|FP8DRv/, `${filename}: provisional publication identifiers must not be distributed`);
    assert.doesNotMatch(text, /\b(?:no (?:public |standalone )?source (?:exists|has been)|not yet cloud-verified|cloud deployment[^.\n]*still pending|no draft exists|(?:has|have) (?:never|not yet) been deployed)\b/i, `${filename}: stale absolute source/cloud claims`);
    assert.doesNotMatch(text, /(?:wait (?:at least )?48 hours|keep .*unpublished).*?(?:before publication|until .*delet|while .*storage)/i, `${filename}: superseded storage waiting gate`);
    assert.doesNotMatch(text, /PostgreSQL (?:to a digest resolving to )?`?\d+\.\d+/, `${filename}: link pin sources instead of duplicating PostgreSQL patch versions`);
    assert.doesNotMatch(text, /prod is initialized by default|cron (?:automatically|silently) approves|this release is (?:fully qualified|published|security cleared)/i, `${filename}: unearned runtime/publication claim`);
    for (const link of text.matchAll(/\]\(([^)]+)\)/g)) {
      const target = link[1].split('#')[0];
      if (!target || /^[a-z][a-z\d+.-]*:/i.test(target)) continue;
      assert.ok(publicLinkTargets.has(target), `${filename}: link must target distributed public files`);
      assert.ok(existsSync(new URL(target, root)), `${filename}: missing public link target`);
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const checkVersion = !process.argv.includes('--skip-version');
  verifyDocumentation(loadDocumentation(), { checkVersion });
  console.log(`PASS: documentation, private defaults, marketplace headings, links and qualification boundaries${checkVersion ? ', including VERSION agreement' : '; VERSION agreement deferred for release-owner update'}. Static checks only.`);
}
