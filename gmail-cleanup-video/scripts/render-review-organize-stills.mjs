import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const inputProps = {audio: false};
const composition = await selectComposition({serveUrl, id: 'GmailReviewOrganize', inputProps});
await mkdir('out/review-organize-stills', {recursive: true});
for (const frame of [60, 360, 760, 762, 768, 780, 839, 870, 930, 1140, 1470, 1679, 1680, 1799]) {
  await renderStill({serveUrl, composition, frame, output: `out/review-organize-stills/frame-${frame}.png`, inputProps});
  console.log(`Rendered ${(frame / 60).toFixed(2)}s`);
}
