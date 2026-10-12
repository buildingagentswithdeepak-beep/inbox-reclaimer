import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const inputProps = {audio: false};
const composition = await selectComposition({serveUrl, id: 'GmailReportReveal', inputProps});
await mkdir('out/report-stills', {recursive: true});
for (const frame of [150, 330, 540, 750, 930, 1020, 1139]) {
  await renderStill({serveUrl, composition, frame, output: `out/report-stills/frame-${frame}.png`, scale: .75, inputProps});
  console.log(`Rendered ${(frame / 60).toFixed(2)}s`);
}
