import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const inputProps = {audio: false};
const composition = await selectComposition({serveUrl, id: 'GmailAnalyze', inputProps});
await mkdir('out/analyze-stills', {recursive: true});
for (const frame of [90, 225, 300, 540, 600, 651, 708, 810, 899]) {
  await renderStill({serveUrl, composition, frame, output: `out/analyze-stills/frame-${frame}.png`, inputProps});
  console.log(`Rendered ${(frame / 60).toFixed(2)}s`);
}
