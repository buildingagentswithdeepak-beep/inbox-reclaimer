import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repository = path.resolve(project, '..');
const manifestPath = path.join(project, 'src/data/continuation-code.json');
const logoSource = 'C:/RockDeveloper/BuildingAgentsLogo.png';
const logoFile = 'public/building-agents-logo.png';
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const args = process.argv.slice(2);
assert(args.length === 0 || (args.length === 1 && args[0] === '--verify'), 'Usage: node scripts/prepare-continuation-source.mjs [--verify]');
const verify = args[0] === '--verify';

// Every tuple denotes one contiguous source range, never concatenated fragments.
const selections = [
  ['cli', 'cli.py', 'analyze', 276, 277, [[276, 276]]],
  ['read-workflow', 'workflow.py', 'run_read_workflow', 23, 29, [[23, 27]]],
  ['scan', 'sync.py', 'SyncService.limited_scan', 127, 133, [[129, 133]]],
  ['aggregation', 'analytics.py', 'build_report', 159, 165, [[159, 160], [163, 165]]],
  ['render', 'render.py', 'render_html', 174, 177, [[174, 175]]],
  ['selection', 'sender/selection.py', 'select_sender', 23, 26, [[25, 26]]],
  ['decision', 'sender/commands.py', '_perform', 61, 68, [[61, 62], [67, 68]]],
  ['writer', 'sender/commands.py', '_perform', 69, 77, [[69, 69], [75, 77]]],
  ['pause', 'sender/workflow.py', 'run_sender_workflow.await_approval', 90, 94, [[92, 94]]],
  ['checks', 'sender/executor.py', 'SenderExecutor._safe_read', 101, 106, [[103, 105]]],
  ['intent', 'sender/executor.py', 'SenderExecutor._effect', 125, 129, [[127, 129]]],
  ['effect', 'sender/executor.py', 'SenderExecutor._effect', 135, 140, [[137, 140]]],
  ['journal-intent', 'sender/journal.py', 'SenderJournal.begin', 846, 852, [[848, 852]]],
  ['outcome', 'sender/journal.py', 'SenderJournal.finish', 898, 902, [[900, 901]]],
  ['transport', 'sender/gmail.py', 'GoogleSenderWriter.trash_ids', 234, 239, [[238, 238]]],
];

const groups = [
  {id: 'read-entry', startSecond: 0, endSecond: 6, cards: [
    {startSecond: 0, endSecond: 6, excerptIds: ['cli', 'read-workflow'], layout: 'paired'},
  ]},
  {id: 'fetch-analyze-present', startSecond: 6, endSecond: 16, cards: [
    {startSecond: 6, endSecond: 9, excerptIds: ['scan'], layout: 'single'},
    {startSecond: 9, endSecond: 12, excerptIds: ['aggregation'], layout: 'single'},
    {startSecond: 12, endSecond: 16, excerptIds: ['render'], layout: 'single'},
  ]},
  {id: 'select-approve', startSecond: 16, endSecond: 26, cards: [
    {startSecond: 16, endSecond: 19, excerptIds: ['selection'], layout: 'single'},
    {startSecond: 19, endSecond: 22, excerptIds: ['decision'], layout: 'single'},
    {startSecond: 22, endSecond: 26, excerptIds: ['writer'], layout: 'single'},
  ]},
  {id: 'pause-check-dispatch', startSecond: 26, endSecond: 32, cards: [
    {startSecond: 26, endSecond: 29, excerptIds: ['pause', 'checks'], layout: 'paired'},
    {startSecond: 29, endSecond: 32, excerptIds: ['intent', 'effect'], layout: 'paired'},
  ]},
  {id: 'journal-provider', startSecond: 32, endSecond: 39, cards: [
    {startSecond: 32, endSecond: 36, excerptIds: ['journal-intent', 'outcome'], layout: 'paired'},
    {startSecond: 36, endSecond: 39, excerptIds: ['transport'], layout: 'single'},
  ]},
];

const sources = new Map();
const excerpts = selections.map(([id, name, symbol, startLine, endLine, highlights]) => {
  const file = `src/inbox_reclaimer/${name}`;
  if (!sources.has(file)) {
    const bytes = readFileSync(path.join(repository, file));
    const text = bytes.toString('utf8');
    assert(Buffer.from(text, 'utf8').equals(bytes), `Source must round-trip UTF-8: ${file}`);
    // Retain original terminators, including CRLF, and the final unterminated line.
    const lines = text.match(/[^\r\n]*(?:\r\n|\n|\r|$)/g).filter((line) => line !== '');
    sources.set(file, {bytes, lines, sourceSha256: sha256(bytes)});
  }
  const source = sources.get(file);
  assert(startLine >= 1 && endLine >= startLine && endLine <= source.lines.length, `Invalid range: ${id}`);
  const selected = source.lines.slice(startLine - 1, endLine);
  const code = selected.join('');
  const highlightRanges = highlights.map(([first, last]) => {
    assert(first >= startLine && last <= endLine && first <= last, `Invalid highlight: ${id}`);
    return {startLine: first, endLine: last};
  });
  return {
    id, file, symbol, language: 'python', startLine, endLine, code,
    sourceSha256: source.sourceSha256,
    excerptSha256: sha256(Buffer.from(code, 'utf8')),
    highlightRanges,
    lineCount: selected.length,
    maxLineChars: Math.max(...selected.map((line) => [...line.replace(/(?:\r\n|\n|\r)$/, '')].length)),
  };
});

const ids = excerpts.map(({id}) => id);
assert.equal(new Set(ids).size, ids.length, 'Duplicate excerpt IDs');
let cursor = 0;
const scheduled = [];
for (const group of groups) {
  assert.equal(group.startSecond, cursor, 'Groups must be contiguous');
  for (const card of group.cards) {
    assert.equal(card.startSecond, cursor, 'Cards must be contiguous');
    assert(card.endSecond > cursor && card.endSecond <= group.endSecond, 'Invalid card duration');
    assert.equal(card.excerptIds.length, card.layout === 'paired' ? 2 : 1);
    scheduled.push(...card.excerptIds);
    cursor = card.endSecond;
  }
  assert.equal(cursor, group.endSecond);
}
assert.equal(cursor, 39);
assert.deepEqual([...scheduled].sort(), [...ids].sort(), 'Each excerpt must be scheduled exactly once');

const logoBytes = readFileSync(logoSource);
assert(logoBytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), 'Source logo must be PNG');
const manifest = {
  schemaVersion: 1,
  sourceRoot: '..',
  lineCoordinates: '1-based inclusive source lines; highlightRanges use the same coordinates',
  codeEncoding: 'UTF-8, original indentation and line terminators, no inserted ellipses',
  timeline: {unit: 'seconds', interval: 'start-inclusive, end-exclusive', duration: 39, groups},
  sources: [...sources].map(([file, source]) => ({file, sourceSha256: source.sourceSha256, byteLength: source.bytes.length})),
  excerpts,
  logo: {sourceFile: logoSource, file: logoFile, sourceSha256: sha256(logoBytes), sha256: sha256(logoBytes), byteLength: logoBytes.length},
};

// Existing manifests are pins, not a cache silently refreshed after source changes.
if (verify || existsSync(manifestPath)) {
  const pinned = JSON.parse(readFileSync(manifestPath, 'utf8'));
  for (const source of manifest.sources) {
    const old = pinned.sources.find(({file}) => file === source.file);
    assert.equal(old?.sourceSha256, source.sourceSha256, `Pinned whole-file hash changed: ${source.file}`);
  }
  assert.deepEqual(pinned, manifest, 'Manifest differs from current source, logo, or extraction specification; review before repinning');
}

function checkInputsUnchanged() {
  for (const [file, source] of sources) {
    assert(readFileSync(path.join(repository, file)).equals(source.bytes), `Source changed during preparation: ${file}`);
  }
  assert(readFileSync(logoSource).equals(logoBytes), 'Source logo changed during preparation');
}

checkInputsUnchanged();
if (!verify) {
  assert(statSync(path.join(project, 'src')).isDirectory());
  assert(statSync(path.join(project, 'public')).isDirectory());
  mkdirSync(path.dirname(manifestPath), {recursive: true});
  copyFileSync(logoSource, path.join(project, logoFile));
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', 'utf8');
}
assert(readFileSync(path.join(project, logoFile)).equals(logoBytes), 'Public logo is not a byte-exact source copy');
assert.deepEqual(JSON.parse(readFileSync(manifestPath, 'utf8')), manifest);
checkInputsUnchanged();
console.log(`${verify ? 'Verified' : 'Generated'} ${excerpts.length} verbatim excerpts, ${sources.size} pinned source files, 39-second schedule, and byte-identical logo.`);
console.table(excerpts.map(({id, file, startLine, endLine, lineCount, maxLineChars}) => ({id, file, startLine, endLine, lineCount, maxLineChars})));
console.log(`Logo SHA-256: ${manifest.logo.sha256}`);
console.log(`Longest source line: ${Math.max(...excerpts.map(({maxLineChars}) => maxLineChars))} characters including indentation.`);
