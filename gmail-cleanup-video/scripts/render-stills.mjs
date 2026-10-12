import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'GmailCleanupHook'});
await mkdir('out/stills', {recursive: true});
for (const frame of [45, 110, 205, 270, 400, 540, 665, 755, 845, 945, 1040, 1079]) {
  await renderStill({serveUrl, composition, frame, output: `out/stills/frame-${String(frame).padStart(4, '0')}.png`, scale: 0.75, inputProps: {audio: false}});
  console.log(`Rendered frame ${frame} (${(frame / 60).toFixed(2)}s)`);
}
