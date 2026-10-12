import {spawnSync} from 'node:child_process';
import {writeFileSync, existsSync, readFileSync, readdirSync, unlinkSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {deflateSync} from 'node:zlib';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const ffmpeg = path.join(root, 'node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe');
const source = path.join(root, 'out/Review.mp4');
for (const dir of ['scripts', 'public', 'out']) assert(existsSync(path.join(root, dir)));
const run = (args, input) => {
  const result = spawnSync(ffmpeg, ['-hide_banner', '-loglevel', 'error', ...args], {
    input, maxBuffer: 1024 * 1024 * 1024,
  });
  if (result.error || result.status !== 0) throw result.error ?? new Error(result.stderr.toString());
  return result.stdout;
};

// Dependency-free PNG writer for encoder input and audit images.
function pngBytes(pixels, width, height) {
  const chunk = (name, data) => {
    const body = Buffer.concat([Buffer.from(name), data]);
    let crc = 0xffffffff;
    for (const byte of body) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
    const header = Buffer.alloc(4), footer = Buffer.alloc(4);
    header.writeUInt32BE(data.length); footer.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
    return Buffer.concat([header, body, footer]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 2;
  const scanlines = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y++) pixels.copy(scanlines, y * (width * 3 + 1) + 1, y * width * 3, (y + 1) * width * 3);
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', header), chunk('IDAT', deflateSync(scanlines)), chunk('IEND', Buffer.alloc(0))]);
}
const png = (file, pixels, width, height) => writeFileSync(file, pngBytes(pixels, width, height));
const width = 1240, sourceHeight = 790, frameBytes = width * sourceHeight * 3;
const decode = (file, start, frames, crop = 'crop=1240:790:400:150') => run([
  '-i', file, '-ss', String(start), '-frames:v', String(frames), '-an', '-vf', crop,
  '-c:v', 'rawvideo', '-f', 'image2pipe', '-pix_fmt', 'rgb24', 'pipe:1',
]);
const rowCrop = (pixels, y, height) => Buffer.from(pixels.subarray(y * width * 3, (y + height) * width * 3));
const blit = (target, pixels, y) => pixels.copy(target, y * width * 3);
const encode = (name, frames, height) => {
  const file = path.join(root, name);
  run(['-y', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'png', '-i', 'pipe:0',
    '-an', '-map_metadata', '-1', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', file],
  Buffer.concat(frames.map((pixels) => pngBytes(pixels, width, height))));
  return file;
};

if (process.argv.includes('--inspect')) {
  const times = process.argv.slice(3).map(Number);
  for (const time of times) {
    const pixels = run(['-i', source, '-ss', String(time), '-frames:v', '1', '-vf', 'crop=1240:790:400:150', '-c:v', 'rawvideo', '-f', 'image2pipe', '-pix_fmt', 'rgb24', 'pipe:1']);
    png(path.join(root, `out/analyze-source-inspect-${String(time).padStart(2, '0')}.png`), pixels, 1240, 790);
  }
  console.log(`Source inspection frames: ${times.join(', ')} seconds; crop x400 y150 w1240 h790.`);
} else {
  const sourceHash = createHash('sha256').update(readFileSync(source)).digest('hex');
  const earlyReference = decode(source, 4, 1);
  const lateReference = decode(source, 13, 1);
  // Test the actual command glyphs on EVERY frame, not a guessed scroll time.
  const commandDifference = (pixels, offset, reference, referenceOffset) => {
    let total = 0;
    for (let y = 38; y < 130; y++) {
      for (let x = 70; x < 470; x++) {
        const a = ((offset + y) * width + x) * 3;
        const b = ((referenceOffset + y) * width + x) * 3;
        for (let c = 0; c < 3; c++) total += Math.abs(pixels[a + c] - reference[b + c]);
      }
    }
    return total / (92 * 400 * 3);
  };
  const clips = [
    {name: 'command', start: 4, frames: 120, height: 132, sceneStart: 0},
    {name: 'progress', start: 8.5, frames: 180, height: 420, sceneStart: 4},
    {name: 'categories', start: 19, frames: 150, height: 420, sceneStart: 10},
  ];
  const assembly = [], audit = [];
  for (const clip of clips) {
    const decoded = decode(source, clip.start, clip.frames);
    assert.equal(decoded.length, clip.frames * frameBytes, `${clip.name}: unexpected source frame count`);
    const frames = [], states = [];
    for (let i = 0; i < clip.frames; i++) {
      const pixels = decoded.subarray(i * frameBytes, (i + 1) * frameBytes);
      const early = commandDifference(pixels, 494, earlyReference, 494);
      const late = commandDifference(pixels, 0, lateReference, 0);
      assert(Math.min(early, late) < 3, `${clip.name} frame ${i}: unknown command/scroll state; refusing export`);
      const pinned = late < early;
      if (clip.name === 'command') assert(!pinned);
      if (clip.name === 'categories') assert(pinned);
      const command = rowCrop(pixels, pinned ? 0 : 494, 132);
      // Remove bottom-edge fragments of the preceding terminal line.
      command.fill(26, 0, width * 3 * 3);
      // Only the prompt prefix is replaced; all command characters remain source pixels.
      for (let y = 0; y < 36; y++) command.fill(26, y * width * 3, (y * width + 524) * 3);
      const output = Buffer.alloc(width * 420 * 3, 26);
      if (clip.name === 'progress') {
        // Source y836..936 before the recorded jump; y318..678 after it.
        blit(output, rowCrop(pixels, pinned ? 168 : 686, pinned ? 360 : 100), 0);
      } else if (clip.name === 'categories') {
        // y390..730 excludes earlier sender rows AND subsequent shell prompts.
        blit(output, rowCrop(pixels, 240, 340), 0);
      }
      frames.push(clip.name === 'command' ? command : output);
      const combined = Buffer.alloc(width * 570 * 3, 26);
      blit(combined, command, 0); blit(combined, output, 150);
      assembly.push(combined);
      states.push({frame: i, sourceFrame: Math.round(clip.start * 30) + i, pinned, commandError: Math.min(early, late)});
    }
    const file = encode(`public/analyze-${clip.name}.mp4`, frames, clip.height);
    // Decode the deliverable again, including its last frame, to verify count and size.
    const check = decode(file, 0, clip.frames + 1, 'null');
    assert.equal(check.length, clip.frames * width * clip.height * 3);
    const hashes = new Set(frames.map((frame) => createHash('sha256').update(frame).digest('hex')));
    audit.push({...clip, file: `public/analyze-${clip.name}.mp4`, uniqueSourceCrops: hashes.size, states});
    for (const index of [...new Set([0, 15, 30, 60, 90, 119, clip.frames - 1].filter((n) => n < clip.frames))]) {
      png(path.join(root, `out/analyze-source-${clip.name}-${String(index).padStart(3, '0')}.png`),
        check.subarray(index * width * clip.height * 3, (index + 1) * width * clip.height * 3), width, clip.height);
    }
    console.log(`${clip.name}: ${clip.frames / 30}s, ${width}x${clip.height}, ${hashes.size} distinct decoded source crops`);
  }
  const combinedFile = encode('public/analyze-15s.mp4', assembly, 570);
  writeFileSync(path.join(root, 'out/analyze-source-15s-preview.mp4'), readFileSync(path.join(root, 'public/analyze-15s.mp4')));
  // Each audit sheet covers ten consecutive frames at half size, in reading order.
  for (let first = 0; first < assembly.length; first += 10) {
    const count = Math.min(10, assembly.length - first);
    const decoded = decode(combinedFile, first / 30, count, 'null');
    assert.equal(decoded.length, count * width * 570 * 3, `Composite frame ${first}: unexpected decoded size`);
    const sheet = Buffer.alloc(1240 * 1425 * 3, 26);
    for (let n = 0; n < 10 && first + n < assembly.length; n++) {
      const pixels = decoded.subarray(n * width * 570 * 3, (n + 1) * width * 570 * 3);
      for (let y = 0; y < 285; y++) for (let x = 0; x < 620; x++) {
        const src = (y * 2 * width + x * 2) * 3;
        const dest = ((Math.floor(n / 2) * 285 + y) * 1240 + (n % 2) * 620 + x) * 3;
        pixels.copy(sheet, dest, src, src + 3);
      }
    }
    png(path.join(root, `out/analyze-source-audit-${String(first).padStart(3, '0')}.png`), sheet, 1240, 1425);
  }
  assert.equal(decode(combinedFile, 15, 1, 'null').length, 0, 'Composite exceeds 450 frames');
  assert.equal(createHash('sha256').update(readFileSync(source)).digest('hex'), sourceHash, 'Original source changed');
  writeFileSync(path.join(root, 'out/analyze-source-validation.json'), JSON.stringify({sourceHash, fps: 30,
    composite: {file: 'public/analyze-15s.mp4', width, height: 570, frames: assembly.length, duration: 15, auditSource: 'decoded deliverable'},
    clips: audit}, null, 2));
  // Inspection files contain private source pixels; never leave them with export previews.
  for (const file of readdirSync(path.join(root, 'out'))) {
    if (/^analyze-source-inspect-[\d.]+\.png$/.test(file)) unlinkSync(path.join(root, 'out', file));
  }
  console.log('Prepared 450 normal-speed frames; source hash unchanged; private inspection frames removed.');
}
