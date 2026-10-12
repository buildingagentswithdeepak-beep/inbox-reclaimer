import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const inputProps = {audio: false};
const composition = await selectComposition({serveUrl, id: 'GmailTechnicalStack', inputProps});
await mkdir('out/stack-stills', {recursive: true});
for (const frame of [60, 210, 300, 390, 480, 555, 599]) {
  await renderStill({serveUrl, composition, frame, output: `out/stack-stills/frame-${frame}.png`, scale: .75, inputProps});
  console.log(`Rendered ${(frame / 60).toFixed(2)}s`);
}
