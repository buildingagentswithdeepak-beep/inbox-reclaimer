import {spawnSync} from 'node:child_process';
import {existsSync, readFileSync, writeFileSync, readdirSync, unlinkSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {deflateSync} from 'node:zlib';
import path from 'node:path';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = path.join(root, 'out/ReportSender.mp4');
const ffmpeg = path.join(root, 'node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe');
for (const dir of ['scripts', 'public', 'out']) assert(existsSync(path.join(root, dir)));
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const originalHash = hash(readFileSync(source));
const run = (args) => {
  const result = spawnSync(ffmpeg, ['-hide_banner', '-loglevel', 'error', ...args], {maxBuffer: 128 * 1024 * 1024});
  if (result.error || result.status !== 0) throw result.error ?? new Error(result.stderr.toString());
  return result.stdout;
};
function pngBytes(pixels, width, height) {
  assert.equal(pixels.length, width * height * 3);
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
const decode = (file, time, filter) => run(['-i', file, '-ss', String(time), '-frames:v', '1', '-an', '-vf', filter,
  '-c:v', 'rawvideo', '-f', 'image2pipe', '-pix_fmt', 'rgb24', 'pipe:1']);

if (process.argv.includes('--inspect')) {
  const times = process.argv.slice(3).map(Number);
  assert(times.length && times.every((time) => Number.isFinite(time) && time >= 0));
  const width = 1240, height = 790;
  const sheet = Buffer.alloc(width * Math.ceil(times.length / 2) * (height / 2) * 3, 26);
  for (const [index, time] of times.entries()) {
    const pixels = decode(source, time, 'crop=1240:790:400:150');
    assert.equal(pixels.length, width * height * 3);
    writeFileSync(path.join(root, `out/identify-source-private-${time}.png`), pngBytes(pixels, width, height));
    for (let y = 0; y < height / 2; y++) for (let x = 0; x < width / 2; x++) {
      const src = (y * 2 * width + x * 2) * 3;
      const dest = ((Math.floor(index / 2) * height / 2 + y) * width + index % 2 * width / 2 + x) * 3;
      pixels.copy(sheet, dest, src, src + 3);
    }
  }
  writeFileSync(path.join(root, 'out/identify-source-private-contact.png'), pngBytes(sheet, width, Math.ceil(times.length / 2) * height / 2));
  console.log(`Private inspection sheet in reading order: ${times.join(', ')} seconds. Removed by successful preparation.`);
} else {
  // Reviewed browser-report crop excludes chrome, paths and the account's own row.
  const time = 3;
  const crop = {x: 48, y: 446, width: 864, height: 396};
  const width = 1200, height = 550;
  const original = decode(source, time, `crop=${crop.width}:${crop.height}:${crop.x}:${crop.y}`);
  assert.equal(original.length, crop.width * crop.height * 3);
  const pixels = Buffer.alloc(width * height * 3);
  // Preserve actual sender pixels, explicitly requested by the user.
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const sx = Math.floor(x * crop.width / width), sy = Math.floor(y * crop.height / height);
    const src = (sy * crop.width + sx) * 3;
    original.copy(pixels, (y * width + x) * 3, src, src + 3);
  }
  const output = 'public/identify-senders.png';
  const png = pngBytes(pixels, width, height);
  writeFileSync(path.join(root, output), png);
  const decoded = decode(path.join(root, output), 0, 'null');
  assert(decoded.equals(pixels), 'PNG round-trip mismatch');
  let unchangedPixels = 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const sx = Math.floor(x * crop.width / width), sy = Math.floor(y * crop.height / height);
    const src = (sy * crop.width + sx) * 3, dest = (y * width + x) * 3;
    for (let c = 0; c < 3; c++) assert.equal(decoded[dest + c], original[src + c]);
    unchangedPixels++;
  }
  writeFileSync(path.join(root, 'out/identify-source-preview.png'), png);
  const hashAfter = hash(readFileSync(source));
  assert.equal(hashAfter, originalHash, 'Original recording changed');
  const audit = {
    source: 'out/ReportSender.mp4', sourceHashBefore: originalHash, sourceHashAfter: hashAfter,
    timestampSeconds: time, seek: 'Output-side -ss 3; first decoded frame at or after requested timestamp',
    crop, senderVisibility: 'Actual senders visible at explicit user request; account details, paths and internal IDs excluded by crop',
    output, width, height, pngSha256: hash(png), scaling: '25/18 nearest neighbor',
    disclosure: 'Recorded report / held for readability', visibleRows: 4,
    highlightedSender: 'noreply@medium.com',
    outline: {x: 31, y: 323, width: 1145, height: 120},
    checks: {losslessRoundTrip: true, unchangedPixels, allPixelsMatchSource: true},
  };
  writeFileSync(path.join(root, 'out/identify-source-validation.json'), JSON.stringify(audit, null, 2) + '\n');
  // Never leave private inspection pixels among the deliverable previews.
  for (const file of readdirSync(path.join(root, 'out'))) {
    if (/^identify-source-private-(?:[\d.]+|contact)\.png$/.test(file)) unlinkSync(path.join(root, 'out', file));
  }
  console.log(`Prepared ${output}: ${width}x${height}; actual senders visible; ${unchangedPixels} source-matching pixels.`);
  console.log('Private inspection images removed. Disclosure: Recorded report / held for readability.');
}
assert.equal(hash(readFileSync(source)), originalHash, 'Original recording changed');
console.log(`Original SHA-256 unchanged: ${originalHash}`);
