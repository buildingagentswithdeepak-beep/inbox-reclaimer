import {bundle} from '@remotion/bundler';
import {renderStill, renderMedia, getCompositions} from '@remotion/renderer';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import path from 'node:path';

const scenes = {
  judgment: ['GmailCleanupJudgmentExamples', 30, [1, 10, 15, 20, 29.9]],
  comparison: ['GmailCleanupBeforeAfter', 17, [0, 4, 8, 13, 16.9]],
  architecture: ['GmailCleanupArchitecture', 28, [5, 12, 15, 21, 25, 27.9]],
  code: ['GmailCleanupCodeTour', 44, [1, 4, 8, 12, 15, 18, 22, 25, 27, 29, 31, 33, 36, 38, 42]],
  endcard: ['GmailCleanupEndCard', 5, [.5, 2, 4.9]],
};
const [action = 'validate', selected] = process.argv.slice(2);
if (!['stills', 'render', 'validate'].includes(action) || (selected && !scenes[selected])) throw new Error('Use continuation.mjs stills|render|validate [judgment|comparison|architecture|code|endcard]');
await mkdir('out/continuation', {recursive: true});
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const bin = path.resolve('node_modules/@remotion/compositor-win32-x64-msvc');
function run(tool, args, binary = false) {
  const p = spawnSync(path.join(bin, `${tool}.exe`), args, {encoding: binary ? undefined : 'utf8', maxBuffer: 128 * 1024 * 1024});
  if (p.status !== 0) throw new Error(p.stderr?.toString());
  return p.stdout;
}
const compositions = await getCompositions(serveUrl);
const reports = [];
const audioFiles = {endcard: 'public/audio/endcard-short-mix.wav'};
for (const [name, [id, seconds, times]] of Object.entries(scenes).filter(([name]) => !selected || name === selected)) {
  const composition = compositions.find(c => c.id === id);
  if (!composition || composition.width !== 1920 || composition.height !== 1080 || composition.fps !== 60 || composition.durationInFrames !== seconds * 60) throw new Error(`${id}: registration mismatch`);
  if (action === 'stills') {
    for (const t of times) {
      const frame = Math.round(t * 60);
      await renderStill({serveUrl, composition, frame, inputProps: {audio: false}, output: `out/continuation/${name}-${frame}.png`});
    }
  }
  if (action === 'render') {
    const raw = `out/continuation/${name}-render.mp4`;
    const output = `out/gmail-cleanup-${name}-${seconds}s-1080p.mp4`;
    await renderMedia({serveUrl, composition, inputProps: {audio: false}, codec: 'h264', crf: 16, pixelFormat: 'yuv420p', concurrency: 4, outputLocation: raw});
    run('ffmpeg', ['-y', '-v', 'error', '-i', raw, '-i', audioFiles[name] ?? `public/audio/continuation-${name}-mix.wav`, '-t', String(seconds), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', output]);
    const metadata = JSON.parse(run('ffprobe', ['-v', 'error', '-show_entries', 'format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels', '-of', 'json', output]));
    const video = metadata.streams.find(s => s.codec_type === 'video');
    const audio = metadata.streams.find(s => s.codec_type === 'audio');
    if (+metadata.format.duration !== seconds || +video.nb_frames !== seconds * 60 || video.width !== 1920 || video.height !== 1080 || video.r_frame_rate !== '60/1' || audio.channels !== 2 || +audio.sample_rate !== 48000) throw new Error(`${id}: invalid delivery`);
    const wav = run('ffmpeg', ['-v', 'error', '-i', output, '-vn', '-t', String(seconds), '-f', 'wav', '-acodec', 'pcm_s16le', 'pipe:1'], true);
    let offset = 12;
    while (wav.toString('ascii', offset, offset + 4) !== 'data') {
      const size = wav.readUInt32LE(offset + 4);
      offset += 8 + size + (size % 2);
      if (offset + 8 > wav.length) throw new Error(`${id}: no decoded WAV data`);
    }
    const pcm = wav.subarray(offset + 8);
    let peak = 0, sum = 0;
    for (let i = 0; i < pcm.length; i += 2) {const v = pcm.readInt16LE(i) / 32768; peak = Math.max(peak, Math.abs(v)); sum += v * v;}
    if (peak >= 1) throw new Error(`${id}: clipped audio`);
    const report = {id, output, ...metadata, audio: {samplePeakDbfs: 20 * Math.log10(peak), rmsDbfs: 10 * Math.log10(sum / (pcm.length / 2)), clipped: false, note: 'Decoded sample measurements, not LUFS or true peak.'}};
    await writeFile(`out/continuation/${name}-verification.json`, JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  }
  reports.push({id, seconds, frames: composition.durationInFrames, width: composition.width, height: composition.height, fps: composition.fps});
}
if (action === 'validate') {
  for (const [name] of Object.entries(scenes)) await readFile(audioFiles[name] ?? `public/audio/continuation-${name}-mix.wav`);
  await readFile('public/building-agents-logo.png');
  await writeFile('out/continuation/registration-validation.json', JSON.stringify(reports, null, 2));
}
console.log(JSON.stringify(reports, null, 2));
