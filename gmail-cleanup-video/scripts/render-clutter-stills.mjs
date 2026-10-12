import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir, readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const inputProps = {audio: false};
const composition = await selectComposition({serveUrl, id: 'GmailClutterAccumulation', inputProps});
await mkdir('out/clutter-stills', {recursive: true});
for (const frame of [90, 270, 540, 810, 1050, 1200, 1260, 1439]) {
  await renderStill({serveUrl, composition, frame, output: `out/clutter-stills/frame-${frame}.png`, scale: .75, inputProps});
  console.log(`Rendered ${(frame / 60).toFixed(2)}s`);
}
assert.deepEqual(await readFile('out/clutter-stills/frame-1260.png'), await readFile('out/clutter-stills/frame-1439.png'), 'Final hold must be visually identical');
console.log('PASS: identical rendered picture at 21.00 and 23.98 seconds.');
