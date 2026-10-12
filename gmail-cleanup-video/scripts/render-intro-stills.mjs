import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';

const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'GmailIntroduction'});
await mkdir('out/intro-stills', {recursive: true});
for (const frame of [150, 330, 570, 810, 858, 904, 914, 940, 1040]) {
  await renderStill({serveUrl, composition, frame, output: `out/intro-stills/frame-${frame}.png`, scale: .75, inputProps: {audio: false}});
  console.log(`Rendered ${frame / 60}s`);
}
