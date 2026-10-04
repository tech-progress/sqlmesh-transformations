import assert from 'node:assert/strict';
import test from 'node:test';
import { loadDocumentation, verifyDocumentation } from '../scripts/verify-docs.mjs';

const documentation = loadDocumentation();
const options = { checkVersion: process.env.SQLMESH_DOCS_SKIP_VERSION !== '1' };
const changedDocument = (filename, transform) => ({
  ...documentation,
  documents: { ...documentation.documents, [filename]: transform(documentation.documents[filename]) },
});
const rejectsChange = (filename, transform, message) => {
  assert.throws(() => verifyDocumentation(changedDocument(filename, transform), options), message);
};

test('public documentation preserves runtime and qualification boundaries', () => {
  verifyDocumentation(documentation, options);
});

test('version gate rejects drift and release declarations agree even during owner update', () => {
  const declaredVersion = documentation.documents['README.md'].match(/current template release is `v([\d.]+)`/)[1];
  verifyDocumentation({ ...documentation, version: declaredVersion });
  assert.throws(() => verifyDocumentation({ ...documentation, version: '0.0.0' }), /release must match VERSION/);
  assert.throws(() => verifyDocumentation(changedDocument('SUPPORT.md', text => text.replace(`v${declaredVersion}`, 'v0.0.0')), { checkVersion: false }), /declarations must agree/);
  rejectsChange('CHANGELOG.md', text => text.replace(`## [${declaredVersion}]`, '## [0.0.0]'), /release entry required/);
});

test('rejects private evidence, provisional identifiers and nondistributed links', () => {
  for (const filename of Object.keys(documentation.documents)) {
    for (const reference of ['[Internal](FINDINGS.md)', '[Review](LICENSE_REVIEW.md)', '/tmp/receipt.log', '.verification/receipt.json']) {
      rejectsChange(filename, text => `${text}\n${reference}\n`, /private evidence references/);
    }
    rejectsChange(filename, text => `${text}\nProvisional code FP8DRv.\n`, /provisional publication identifiers/);
  }
  rejectsChange('README.md', text => `${text}\n[Guide](missing-guide.md)\n`, /distributed public files/);
  rejectsChange('README.md', text => `${text}\n[Root](../README.md)\n`, /distributed public files/);
});

test('requires six marketplace headings, description and every main upstream link', () => {
  for (const heading of documentation.documents['MARKETPLACE.md'].match(/^#{1,3} .+$/gm)) {
    rejectsChange('MARKETPLACE.md', text => text.replace(heading, `${heading} extra`), /six exact marketplace headings/);
  }
  for (const origin of documentation.metadata.origins) {
    for (const filename of ['README.md', 'MARKETPLACE.md']) {
      rejectsChange(filename, text => text.replaceAll(origin.url, 'https://example.invalid/'), /main upstream URL/);
    }
  }
  rejectsChange('MARKETPLACE.md', text => text.replace(documentation.metadata.description, 'Generic hosting.'), /description must match metadata/);
});

test('rejects default drift, missing variables and bootstrap/scheduler overclaims', () => {
  for (const key of new Set(Object.values(documentation.defaults).flatMap(service => Object.keys(service)))) {
    rejectsChange('README.md', text => text.replaceAll('`' + key + '`', '`UNDOCUMENTED`'), /graph variable/);
  }
  for (const filename of ['README.md', 'PUBLISHING.md', 'SUPPORT.md', 'UPGRADE.md', 'MARKETPLACE.md']) {
    rejectsChange(filename, text => text.replaceAll('`0 * * * *`', '`* * * * *`'), /documented runtime default/);
    rejectsChange(filename, text => text.replaceAll('`NEVER`', '`ALWAYS`'), /documented runtime default/);
    rejectsChange(filename, text => text.replaceAll(/hourly scheduler firing/g, 'scheduler behavior'), /unobserved historical scheduler limit/);
    rejectsChange(filename, text => `${text}\nProd is initialized by default.\n`, /unearned runtime\/publication claim/);
  }
  assert.throws(() => verifyDocumentation({ ...documentation, startup: `${documentation.startup}\nsqlmesh plan prod --auto-apply\n` }, options), /scheduled startup must never plan\/apply/);
  assert.throws(() => verifyDocumentation({ ...documentation, volumes: { ...documentation.volumes, 'SQLMesh Warehouse': documentation.volumes['SQLMesh State'] } }, options), /independent volume keys/);
  assert.throws(() => verifyDocumentation({
    ...documentation,
    defaults: { ...documentation.defaults, 'SQLMesh Runner': { ...documentation.defaults['SQLMesh Runner'], STATE_SSLMODE: 'disable' } },
  }, options), /connection default must match documentation/);
  rejectsChange('README.md', text => text.replace('Optional defaults `prefer`', 'Optional defaults `disable`'), /connection default STATE_SSLMODE/);
  rejectsChange('README.md', text => text.replaceAll('sleep 1800', 'sleep infinity'), /bounded private maintenance/);
});

test('keeps exact-source qualification, accepted cleanup and recipe-license boundaries', () => {
  rejectsChange('PUBLISHING.md', text => text.replaceAll('queried stored graph', 'local graph'), /required gate queried stored graph/);
  rejectsChange('PUBLISHING.md', text => text.replace('zero queued work', 'some queued work'), /required gate zero queued work/);
  rejectsChange('PUBLISHING.md', text => text.replace("Standard deletion plus verified zero compute and disclosed retention satisfies the owner's cleanup policy.", 'Cleanup optional.'), /accepted cleanup policy/);
  rejectsChange('PUBLISHING.md', text => text.replace('Physical storage deletion and billing-zero proof are not publication gates under the accepted policy.', 'Physical erasure required.'), /physical-erasure\/billing boundary/);
  rejectsChange('PUBLISHING.md', text => `${text}\nWait 48 hours for physical deletion before publication.\n`, /superseded storage waiting gate/);
  rejectsChange('README.md', text => text.replace('MIT for newly authored recipe code only', 'MIT for every upstream runtime'), /recipe-only MIT license/);
  rejectsChange('README.md', text => text.replace('does not relabel combined runtime binaries or grant security clearance', 'clears the entire runtime'), /upstream\/runtime license and security boundary/);
});

test('rejects stale absolute source/cloud status and duplicated PostgreSQL patch pins', () => {
  for (const filename of Object.keys(documentation.documents)) {
    for (const claim of ['No standalone source exists.', 'Not yet cloud-verified.', 'Cloud deployment gates are still pending.', 'No draft exists.', 'This release has never been deployed.']) {
      rejectsChange(filename, text => `${text}\n${claim}\n`, /stale absolute source\/cloud claims/);
    }
    rejectsChange(filename, text => `${text}\nPostgreSQL 16.15 is the release pin.\n`, /link pin sources/);
  }
});
