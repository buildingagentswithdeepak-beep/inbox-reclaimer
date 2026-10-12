import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {deflateSync} from 'node:zlib';
import {openBrowser} from '@remotion/renderer';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = path.join(root, 'out/SelectedEMailPlan.mp4');
const report = process.env.SUGGEST_REPORT_PATH ?? 'C:\\Users\\v-deegarg\\AppData\\Local\\hermes\\profiles\\coder\\inbox_reclaimer\\reports\\demo-suggest-20261008-213941.html';
const tools = path.join(root, 'node_modules/@remotion/compositor-win32-x64-msvc');
const planId = 'c147c7a16a1b407b8bb1b9db1e4d487b';
const sender = 'noreply@medium.com';
for (const dir of ['scripts', 'public', 'out']) assert(existsSync(path.join(root, dir)));
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex');
const sourceHash = hash(readFileSync(source));
const reportBytes = readFileSync(report);
const reportHash = hash(reportBytes);
assert(reportBytes.toString().includes(`Plan: ${planId}<br>`), 'Report plan differs from reviewed recording');
assert(reportBytes.toString().includes(`Exact sender: ${sender} `), 'Unexpected report sender');

function run(tool, args, input) {
  const result = spawnSync(path.join(tools, `${tool}.exe`), args, {input, maxBuffer: 128 * 1024 * 1024});
  if (result.error || result.status !== 0) throw result.error ?? new Error(result.stderr.toString());
  return result.stdout;
}
const metadata = JSON.parse(run('ffprobe', ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height', '-of', 'json', source]));
const video = metadata.streams.find((stream) => stream.codec_type === 'video');
assert.equal(video.width, 1920);
assert.equal(video.height, 1080);
assert(Math.abs(Number(metadata.format.duration) - 44.164) < 0.01);

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
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', deflateSync(scanlines)), chunk('IEND', Buffer.alloc(0))]);
}
const decode = (input, time = 0) => run('ffmpeg', ['-hide_banner', '-loglevel', 'error', ...(Buffer.isBuffer(input) ? ['-f', 'image2pipe', '-c:v', 'png'] : []), '-i', Buffer.isBuffer(input) ? 'pipe:0' : input,
  '-ss', String(time), '-frames:v', '1', '-an', '-c:v', 'rawvideo', '-f', 'image2pipe', '-pix_fmt', 'rgb24', 'pipe:1'], Buffer.isBuffer(input) ? input : undefined);

const assets = [];
function save(name, pixels, width, height, provenance) {
  const png = pngBytes(pixels, width, height);
  assert(decode(png).equals(pixels), `${name}: PNG round-trip mismatch`);
  writeFileSync(path.join(root, `public/suggest-${name}.png`), png);
  // A 1300x500 contain preview checks readability without altering the deliverable.
  const preview = Buffer.alloc(1300 * 500 * 3, name === 'report' ? 243 : 26);
  const scale = Math.min(1300 / width, 500 / height);
  const w = Math.floor(width * scale), h = Math.floor(height * scale);
  const left = Math.floor((1300 - w) / 2), top = Math.floor((500 - h) / 2);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const src = (Math.floor(y / scale) * width + Math.floor(x / scale)) * 3;
    pixels.copy(preview, ((top + y) * 1300 + left + x) * 3, src, src + 3);
  }
  writeFileSync(path.join(root, `out/suggest-source-${name}-preview.png`), pngBytes(preview, 1300, 500));
  assets.push({file: `public/suggest-${name}.png`, width, height, sha256: hash(png), ...provenance, losslessRoundTrip: true});
}

for (const item of [
  {name: 'command', time: 2, crop: {x: 400, y: 574, width: 1250, height: 154}, mask: {x: 0, y: 0, width: 520, height: 28}},
  {name: 'plan', time: 29, crop: {x: 405, y: 320, width: 650, height: 282}, mask: null},
]) {
  const original = decode(source, item.time);
  assert.equal(original.length, 1920 * 1080 * 3);
  const {x, y, width, height} = item.crop;
  const pixels = Buffer.alloc(width * height * 3);
  for (let row = 0; row < height; row++) original.copy(pixels, row * width * 3, ((y + row) * 1920 + x) * 3, ((y + row) * 1920 + x + width) * 3);
  let matched = 0, masked = 0;
  for (let row = 0; row < height; row++) for (let col = 0; col < width; col++) {
    const dest = (row * width + col) * 3;
    const src = ((y + row) * 1920 + x + col) * 3;
    if (item.mask && col < item.mask.width && row < item.mask.height) {
      pixels.fill(26, dest, dest + 3);
      masked++;
    } else {
      assert(pixels.subarray(dest, dest + 3).equals(original.subarray(src, src + 3)));
      matched++;
    }
  }
  save(item.name, pixels, width, height, {source: 'out/SelectedEMailPlan.mp4', timestampSeconds: item.time, crop: item.crop,
    opaqueMask: item.mask, unchangedSourcePixels: matched, maskedPixels: masked, disclosure: 'Recorded terminal / held for readability'});
}

const browserExecutable = path.join(root, 'node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
assert(existsSync(browserExecutable), 'Install the project Remotion browser before preparing assets');
const browser = await openBrowser('chrome', {browserExecutable, logLevel: 'error'});
try {
  const page = await browser.newPage({context: null, logLevel: 'error', indent: false, pageIndex: 0, onBrowserLog: null, onLog: () => {}});
  await page.setViewport({width: 1300, height: 1000, deviceScaleFactor: 1});
  const client = page._client();
  await client.send('Network.enable');
  await client.send('Network.setBlockedURLs', {urls: ['http://*', 'https://*']});
  await page.goto({url: pathToFileURL(report).href, timeout: 30000});
  await page.evaluate(async () => { await document.fonts.ready; });
  const dom = await page.evaluate(() => {
    const rect = (r) => ({x: r.x, y: r.y, width: r.width, height: r.height});
    const header = document.querySelector('header p');
    const text = header.firstChild;
    const accountStart = text.textContent.indexOf(' · Account:');
    if (accountStart < 0) throw new Error('Expected account field not found');
    const accountRange = document.createRange();
    accountRange.setStart(text, accountStart); accountRange.setEnd(text, text.length);
    const senderRange = document.createRange();
    senderRange.setStart(text, 0); senderRange.setEnd(text, accountStart);
    const panel = document.querySelector('main .panel');
    const paragraphs = [...panel.querySelectorAll('p')];
    const plan = paragraphs.find((p) => p.textContent.startsWith('Plan: '));
    const planRange = document.createRange(); planRange.selectNode(plan.firstChild);
    const digestRange = document.createRange(); digestRange.selectNode(plan.lastChild);
    return {title: document.querySelector('h1').textContent, sender: text.textContent.slice(0, accountStart),
      badge: document.querySelector('.header-meta').textContent, counts: paragraphs[0].textContent,
      plan: plan.firstChild.textContent, accountRects: [...accountRange.getClientRects()].map(rect),
      senderRect: rect(senderRange.getBoundingClientRect()), planRect: rect(planRange.getBoundingClientRect()),
      digestRect: rect(digestRange.getBoundingClientRect()), tableRect: rect(document.querySelectorAll('main .panel')[1].getBoundingClientRect()),
      stylesheetApplied: getComputedStyle(document.querySelector('h1')).fontSize === '44px'};
  });
  assert.equal(dom.sender, `Exact sender: ${sender}`);
  assert.equal(dom.plan, `Plan: ${planId}`);
  assert.equal(dom.badge, 'No approval · No mail changed');
  assert(dom.counts.startsWith('20 eligible messages from 20 inspected candidates; candidate cap 20.'));
  assert(dom.stylesheetApplied, 'Report CSP stylesheet did not render');
  const width = 1300, height = Math.ceil(dom.planRect.y + dom.planRect.height + 2);
  assert(height <= 500, 'Summary does not fit product area');
  assert(height <= dom.digestRect.y, 'Digest would enter screenshot');
  assert(height < dom.tableRect.y, 'Message table would enter screenshot');
  // Keep the original DOM intact. Capture only the summary; redact account pixels in memory.
  const screenshot = await client.send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false,
    clip: {x: 0, y: 0, width, height, scale: 1}});
  const original = decode(Buffer.from(screenshot.value.data, 'base64'));
  assert.equal(original.length, width * height * 3);
  const pixels = Buffer.from(original);
  const masks = dom.accountRects.map((r) => ({x: Math.floor(r.x), y: Math.floor(r.y) - 2,
    width: Math.ceil(r.x + r.width) - Math.floor(r.x) + 2, height: Math.ceil(r.height) + 4}));
  assert(masks.every((m) => m.x >= Math.floor(dom.senderRect.x + dom.senderRect.width)), 'Mask overlaps sender');
  let masked = 0;
  for (const m of masks) for (let y = m.y; y < m.y + m.height; y++) for (let x = m.x; x < m.x + m.width; x++) {
    assert(x >= 0 && y >= 0 && x < width && y < height);
    pixels.fill(18, (y * width + x) * 3, (y * width + x) * 3 + 3);
    masked++;
  }
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const maskedPixel = masks.some((m) => x >= m.x && x < m.x + m.width && y >= m.y && y < m.y + m.height);
    const i = (y * width + x) * 3;
    if (maskedPixel) assert(pixels.subarray(i, i + 3).every((v) => v === 18));
    else assert(pixels.subarray(i, i + 3).equals(original.subarray(i, i + 3)));
  }
  save('report', pixels, width, height, {source: path.basename(report), sourceSha256: reportHash,
    method: 'Original file URL, Remotion bundled Chromium, CDP Page.captureScreenshot; no DOM/data/style modifications; network URLs blocked',
    viewport: {width: 1300, height: 1000, deviceScaleFactor: 1}, crop: {x: 0, y: 0, width, height},
    opaqueMasks: masks, maskedPixels: masked, unchangedSourcePixels: width * height - masked,
    verifiedDOM: dom, disclosure: 'Saved HTML report / held for readability'});
} finally {
  await browser.close({silent: true});
}
assert.equal(hash(readFileSync(source)), sourceHash, 'Original recording changed');
assert.equal(hash(readFileSync(report)), reportHash, 'Original report changed');
writeFileSync(path.join(root, 'out/suggest-source-validation.json'), JSON.stringify({source: 'out/SelectedEMailPlan.mp4', sourceSha256: sourceHash,
  sourceDimensions: [video.width, video.height], sourceDurationSeconds: Number(metadata.format.duration), sourceAndReportUnchanged: true,
  verifiedPlanId: planId, verifiedSender: sender, terminalVerification: 'Manual visual review of source 29s; plan_id matches HTML exactly; approval_created false; mail_changed false',
  inspectedSourceSeconds: [2, 29, 41], assets}, null, 2) + '\n');
console.log(JSON.stringify({planId, sender, assets: assets.map(({file, width, height}) => ({file, width, height})), sourceAndReportUnchanged: true}, null, 2));
