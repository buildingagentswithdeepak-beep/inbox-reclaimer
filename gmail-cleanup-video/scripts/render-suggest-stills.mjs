import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const inputProps = {audio: false};
const composition = await selectComposition({serveUrl, id: 'GmailSuggest', inputProps});
await mkdir('out/suggest-stills', {recursive: true});
for (const frame of [60, 138, 210, 270, 360, 479]) {
  await renderStill({serveUrl, composition, frame, output: `out/suggest-stills/frame-${frame}.png`, inputProps});
  console.log(`Rendered ${(frame / 60).toFixed(2)}s`);
}
