import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {deflateSync} from 'node:zlib';
import {once} from 'node:events';

const root = fileURLToPath(new URL('../', import.meta.url));
const source = path.join(root, 'out/ApprovalAndMoveToTrash.mp4');
const tools = path.join(root, 'node_modules/@remotion/compositor-win32-x64-msvc');
for (const dir of ['scripts', 'public', 'out']) assert(existsSync(path.join(root, dir)));
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
const before = sha(readFileSync(source));
assert.equal(before,'7e7b680199bd8ea2f4f8d0bef5e46d5dc2c309cc2ebb0a9a43a5e880a3382eb0','Masks are approved only for the reviewed source bytes');
const run = (tool, args, input) => {
  const p = spawnSync(path.join(tools, `${tool}.exe`), args, {input, maxBuffer: 256 * 1024 * 1024});
  if (p.error || p.status !== 0) throw p.error ?? new Error(p.stderr.toString());
  return p.stdout;
};
const probe = (file) => JSON.parse(run('ffprobe', ['-v', 'error', '-show_entries',
  'stream=codec_type,width,height,nb_frames,r_frame_rate:format=duration', '-of', 'json', file]));
if(process.argv.includes('--verify')) {
  const manifest=JSON.parse(readFileSync(path.join(root,'public/review-organize-source.json')));
  const audit=JSON.parse(readFileSync(path.join(root,'out/review-organize-source-audit.json')));
  assert.equal(audit.sourceSha256Before,before); assert.equal(audit.sourceSha256After,before);
  for(const asset of manifest.assets) {
    const file=path.join(root,asset.file);
    assert.equal(sha(readFileSync(file)),asset.sha256,asset.file);
    const meta=probe(file); assert.equal(meta.streams[0].width,asset.width); assert.equal(meta.streams[0].height,asset.height);
    assert.equal(meta.streams.length,1);
    if(asset.frames) {
      assert.equal(Number(meta.streams[0].nb_frames),asset.frames);
      assert.equal(Number(meta.format.duration),asset.duration);
      const entry=audit.assets.find(a=>a.file===asset.file);
      assert.equal(entry.records.length,asset.frames);
      assert(entry.records.every(r=>r.outsideMasksSourceIdentical && r.exportMaskMaxError<=8));
      for(const sheet of entry.contactSheets) assert(existsSync(path.join(root,sheet)));
    }
  }
  console.log(JSON.stringify({sourceUnchanged:true,sourceSha256:before,assetsVerified:manifest.assets.length,
    auditedVideoFrames:540,contactSheets:18,events:manifest.approvalEvents},null,2));
  process.exit(0);
}
const metadata = probe(source);
assert.equal(metadata.streams[0].width, 1920);
assert.equal(metadata.streams[0].height, 1080);
assert(Math.abs(Number(metadata.format.duration) - 91.445556) < .0001);
const sourceFrames = JSON.parse(run('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_frames',
  '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', source])).frames
  .map((f, index) => ({index, pts: Number(f.best_effort_timestamp_time)}));

const crcTable = Array.from({length: 256}, (_, n) => {
  for (let b = 0; b < 8; b++) n = (n >>> 1) ^ ((n & 1) ? 0xedb88320 : 0);
  return n >>> 0;
});
function png(pixels, width, height) {
  const chunk = (name, data) => {
    const body = Buffer.concat([Buffer.from(name), data]);
    let crc = 0xffffffff;
    for (const byte of body) crc = (crc >>> 8) ^ crcTable[(crc ^ byte) & 255];
    const head = Buffer.alloc(4), tail = Buffer.alloc(4);
    head.writeUInt32BE(data.length); tail.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
    return Buffer.concat([head, body, tail]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 2;
  const rows = Buffer.alloc((width * 3 + 1) * height);
  for (let y = 0; y < height; y++) pixels.copy(rows, y * (width * 3 + 1) + 1, y * width * 3, (y + 1) * width * 3);
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', header), chunk('IDAT', deflateSync(rows, {level: 3})), chunk('IEND', Buffer.alloc(0))]);
}
function crop(raw, sourceWidth, box) {
  const out = Buffer.alloc(box.width * box.height * 3);
  for (let y = 0; y < box.height; y++) raw.copy(out, y * box.width * 3,
    ((box.y + y) * sourceWidth + box.x) * 3, ((box.y + y) * sourceWidth + box.x + box.width) * 3);
  return out;
}
function mask(pixels, width, height, boxes) {
  const out = Buffer.from(pixels);
  for (const [x, y, w, h] of boxes) {
    assert(x >= 0 && y >= 0 && x + w <= width && y + h <= height);
    for (let row = y; row < y + h; row++) out.fill(24, (row * width + x) * 3, (row * width + x + w) * 3);
  }
  // Verify every source row: outside opaque boxes the crop must remain byte-identical.
  for (let y = 0; y < height; y++) {
    const spans = boxes.filter((b) => y >= b[1] && y < b[1] + b[3]).map((b) => [b[0], b[0] + b[2]]).sort((a,b) => a[0]-b[0]);
    let x = 0;
    for (const [left, right] of [...spans, [width, width]]) {
      if (left > x) assert(out.subarray((y*width+x)*3,(y*width+left)*3).equals(pixels.subarray((y*width+x)*3,(y*width+left)*3)));
      if (right > x && left < width) assert(out.subarray((y*width+left)*3,(y*width+right)*3).every((v) => v === 24));
      x = Math.max(x, right);
    }
  }
  return out;
}
async function* decode(file, start, duration, width, height) {
  const p = spawn(path.join(tools, 'ffmpeg.exe'), ['-hide_banner', '-loglevel', 'error', '-i', file,
    '-ss', String(start), '-t', String(duration), '-an', '-fps_mode', 'passthrough', '-c:v', 'rawvideo', '-pix_fmt', 'rgb24', '-f', 'image2pipe', 'pipe:1']);
  let error = ''; p.stderr.on('data', (d) => error += d);
  const exit = once(p, 'close');
  const size = width * height * 3;
  let pending = Buffer.allocUnsafe(size), filled = 0;
  for await (const part of p.stdout) {
    let offset = 0;
    while (offset < part.length) {
      const count = Math.min(size - filled, part.length - offset);
      part.copy(pending, filled, offset, offset + count); filled += count; offset += count;
      if (filled === size) { yield pending; pending = Buffer.allocUnsafe(size); filled = 0; }
    }
  }
  assert.equal((await exit)[0], 0, error); assert.equal(filled, 0);
}
const nativeMasks = [[188,275,600,27], [31,459,360,314]];
// During the OS close animation both windows are alpha-composited. These union masks
// retain identifier/path protection, not independent email or subject boxes.
const closingMasks = [[0,0,335,80], [0,80,78,735], [228,143,107,30], [155,270,650,63],
  [30,448,385,337], [335,185,1335,650],
  [0,80,335,55], [0,243,335,27], [0,335,335,75], [0,785,335,30], [1670,0,250,910], [0,842,78,166]];
const terminalMasks = [[0,0,340,1008], [1670,0,250,1008], [340,185,1330,649]];
const configs = [
  {name: 'approval', start: 48, duration: 14, frames: 420, crop: {x:0,y:0,width:1920,height:1008}},
  {name: 'gmail', start: 86, duration: 4, frames: 120, crop: {x:340,y:180,width:1484,height:798}},
];
function boxesFor(name, pts) {
  if (name === 'gmail') return [];
  if (pts < 60.78) return nativeMasks;
  if (pts < 61.02) return closingMasks;
  return terminalMasks;
}
const audit = {source: 'out/ApprovalAndMoveToTrash.mp4', sourceSha256Before: before, sourceDuration: Number(metadata.format.duration),
  sourceDimensions:[1920,1080], outputFps:30, audio:'Removed; unreviewed source audio is not exported',
  timing:'30 fps sample-and-hold of latest source PTS at or before target time. Boundary samples can precede requested start by less than one source frame. No time compression, optical flow, synthetic cursor, or internal cuts.',
  maskCoordinateSpace:'Output pixels, [x,y,width,height], opaque RGB 24', masks:{nativeMasks,closingMasks,terminalMasks,gmail:[]}, assets:[]};
const publicMeta = {fps:30, planId:'c147c7a16a1b407b8bb1b9db1e4d487b', sender:'noreply@medium.com',
  result:{status:'sender_run_finished',confirmed:20,unknown:0,skipped:0,dry_run:false,failed:null,failedNote:'No separate failed counter shown'},
  timeline:[{frames:[0,420],seconds:[0,14],asset:'review-organize-approval.mp4',sourceSeconds:[48,62],rate:1,label:'Recorded native approval; privacy redactions'},
    {frames:[420,450],seconds:[14,15],asset:null,label:'Later: run result',editorial:true},
    {frames:[450,720],seconds:[15,24],asset:'review-organize-result.png',sourceSeconds:81,label:'Later: run result / held for readability'},
    {frames:[720,840],seconds:[24,28],asset:'review-organize-gmail.mp4',sourceSeconds:[86,90],rate:1,label:'Later: Gmail Trash / visual check only'},
    {frames:[840,900],seconds:[28,30],asset:'review-organize-gmail-hold.png',label:'Gmail Trash / held frame; visual check only'}],
  privacy:'Email/subject-visible revision supersedes the previous mask version. Approval account email, typed email, and subjects are visible; Gmail has no masks. Message IDs, membership digest, result account hash and approval ID, and local paths remain masked. Broad closing/terminal masks can incidentally cover emails or subjects.',
  gmailEvidence:'Original senders, subjects, snippets, dates, in:trash, and Gmail controls are visible with no masks. This later visual check is not independent proof of all 20 exact message IDs or a before/after delta.',
  discontinuities:'Approval recorded at desktop 22:04; result at 22:08; Gmail at 22:10. Source contains recording cuts; not an uninterrupted run.',
  gmailTimingDecision:'Explicit requested four-second asset (86..90) followed by two-second hold, rather than earlier 86..90.5 proposal.',assets:[]};

// Tiny numeric labels keep every contact-sheet cell traceable without a browser/font dependency.
const digits = ['111101101101111','010110010010111','111001111100111','111001111001111','101101111001001','111100111001111','111100111101111','111001001001001','111101111101111','111101111001111'];
function numberLabel(pixels, width, x, y, n) {
  for (const ch of String(n).padStart(3,'0')) {
    const bits = digits[Number(ch)];
    for (let yy=0;yy<5;yy++) for(let xx=0;xx<3;xx++) if(bits[yy*3+xx]==='1')
      for(let dy=0;dy<2;dy++) for(let dx=0;dx<2;dx++) pixels.fill(230,((y+yy*2+dy)*width+x+xx*2+dx)*3,((y+yy*2+dy)*width+x+xx*2+dx)*3+3);
    x += 8;
  }
}
for (const cfg of configs) {
  const {width,height} = cfg.crop;
  const file = path.join(root, `public/review-organize-${cfg.name}.mp4`);
  const encoder = spawn(path.join(tools,'ffmpeg.exe'), ['-hide_banner','-loglevel','error','-y','-f','image2pipe','-framerate','30','-c:v','png','-i','pipe:0',
    '-an','-map_metadata','-1','-c:v','libx264','-preset','medium','-crf','12','-pix_fmt','yuv420p','-movflags','+faststart',file]);
  let stderr=''; encoder.stderr.on('data',d=>stderr+=d); const encoded = once(encoder,'close');
  const pts = sourceFrames;
  // Decode from zero so ffmpeg's output-seek rounding cannot offset the PTS ledger.
  const iterator = decode(source,0,92,1920,1080)[Symbol.asyncIterator]();
  let current = await iterator.next(), next = await iterator.next(), nativeIndex=0;
  const records=[], expected=[];
  for (let i=0;i<cfg.frames;i++) {
    const target = cfg.start+i/30;
    while (!next.done && pts[nativeIndex+1].pts <= target + .000001) { current=next; next=await iterator.next(); nativeIndex++; }
    assert(!current.done); assert(pts[nativeIndex]);
    const boxes=boxesFor(cfg.name,pts[nativeIndex].pts);
    if(cfg.name==='approval' && pts[nativeIndex].pts<61.02) for(const [x,y,w,h] of boxes) {
      for(const [px,py,pw,ph] of [[1400,930,492,65],[30,820,28,22]])
        assert(x+w<=px || x>=px+pw || y+h<=py || y>=py+ph,'Privacy mask overlaps protected checkbox or button action');
    }
    const original=crop(current.value,1920,cfg.crop), safe=mask(original,width,height,boxes);
    const bytes=png(safe,width,height); expected.push(sha(safe));
    if(!encoder.stdin.write(bytes)) await once(encoder.stdin,'drain');
    records.push({frame:i,sceneFrame:cfg.name==='approval'?i:720+i,targetSourceSeconds:target,sourceFrame:pts[nativeIndex].index,sourcePts:pts[nativeIndex].pts,
      masks:boxes,maskedRgbSha256:expected[i],outsideMasksSourceIdentical:true});
  }
  while(!next.done) {next=await iterator.next();nativeIndex++;}
  assert.equal(nativeIndex+1,pts.length,'PTS/decode count mismatch');
  encoder.stdin.end(); assert.equal((await encoded)[0],0,stderr);
  const info=probe(file); assert.equal(info.streams.length,1); assert.equal(info.streams[0].nb_frames,String(cfg.frames));
  assert.equal(info.streams[0].width,width); assert.equal(info.streams[0].height,height);
  assert.equal(info.streams[0].r_frame_rate,'30/1'); assert.equal(Number(info.format.duration),cfg.duration);
  const thumbW=320,thumbH=Math.round(height/width*thumbW),cellH=thumbH+16,sheetW=1920,sheetH=cellH*5;
  let sheet=Buffer.alloc(sheetW*sheetH*3,12), index=0; const sheets=[];
  for await (const frame of decode(file,0,cfg.duration+.1,width,height)) {
    assert(index<cfg.frames);
    // Decode EVERY exported frame and ensure interiors of every privacy box stay opaque.
    let maxMaskError=0;
    for(const [x,y,w,h] of records[index].masks) for(let yy=y+8;yy<y+h-8;yy++) for(let xx=x+8;xx<x+w-8;xx++) {
      const p=(yy*width+xx)*3;
      for(let c=0;c<3;c++) maxMaskError=Math.max(maxMaskError,Math.abs(frame[p+c]-24));
    }
    assert(maxMaskError<=8,`${cfg.name} ${index}: mask interior changed ${maxMaskError}`);
    records[index].exportMaskMaxError=maxMaskError; records[index].decodedExportSha256=sha(frame);
    const cell=index%30,left=(cell%6)*thumbW,top=Math.floor(cell/6)*cellH;
    numberLabel(sheet,sheetW,left+4,top+2,index);
    for(let y=0;y<thumbH;y++) for(let x=0;x<thumbW;x++) {
      const p=(Math.floor(y*height/thumbH)*width+Math.floor(x*width/thumbW))*3;
      frame.copy(sheet,((top+16+y)*sheetW+left+x)*3,p,p+3);
    }
    if(cfg.name==='approval' && ([0,105,150,360,419].includes(index) || (index>=377&&index<=394)))
      writeFileSync(path.join(root,`out/review-organize-source-approval-edge-${String(index).padStart(3,'0')}.png`),png(frame,width,height));
    if(cfg.name==='gmail' && [0,53,54,57,60,74,79,80,119].includes(index)) writeFileSync(path.join(root,`out/review-organize-source-gmail-edge-${index}.png`),png(frame,width,height));
    if(cfg.name==='gmail' && index===119) {
      const bytes=png(frame,width,height); writeFileSync(path.join(root,'public/review-organize-gmail-hold.png'),bytes);
      publicMeta.gmailHold={sourcePts:records[index].sourcePts,fromDecodedVideoFrame:index,width,height,sha256:sha(bytes)};
    }
    if(cell===29||index===cfg.frames-1) {
      const name=`out/review-organize-source-${cfg.name}-sheet-${String(index-cell).padStart(3,'0')}.png`;
      writeFileSync(path.join(root,name),png(sheet,sheetW,sheetH)); sheets.push(name); sheet=Buffer.alloc(sheetW*sheetH*3,12);
    }
    index++;
  }
  assert.equal(index,cfg.frames);
  const asset={file:`public/review-organize-${cfg.name}.mp4`,width,height,frames:index,duration:cfg.duration,sha256:sha(readFileSync(file)),crop:cfg.crop};
  audit.assets.push({...asset,records,contactSheets:sheets,allExportedFramesDecoded:true}); publicMeta.assets.push(asset);
  if(cfg.name==='approval') publicMeta.approvalEvents=[
    {event:'Last frame before button gains focus indication',frame:380},
    {event:'First recorded confirmation focus indication; visual click evidence, not input telemetry',frame:381},
    {event:'First visible native closing animation',frame:384},
    {event:'First fully dismissed native window',frame:390},
  ].map(e=>({...e,sceneFrame:e.frame,sceneSeconds:e.frame/30,sourceFrame:records[e.frame].sourceFrame,sourcePts:records[e.frame].sourcePts}));
  console.log(`${cfg.name}: ${index} frames exported and audited; ${width}x${height}`);
}
const resultCrop={x:400,y:472,width:980,height:440};
const resultBoxes=[[200,96,755,29],[214,151,755,27],[212,178,500,27]];
const resultIterator=decode(source,0,92,1920,1080);
let resultRaw, resultIndex=0;
const selectedResult=sourceFrames.find(f=>f.pts>=81);
for await(const frame of resultIterator) { if(resultIndex===selectedResult.index) resultRaw=frame; resultIndex++; }
assert.equal(resultIndex,sourceFrames.length);
const resultPixels=mask(crop(resultRaw,1920,resultCrop),resultCrop.width,resultCrop.height,resultBoxes);
const resultBytes=png(resultPixels,resultCrop.width,resultCrop.height);
const roundTrip=run('ffmpeg',['-v','error','-f','image2pipe','-c:v','png','-i','pipe:0','-frames:v','1','-c:v','rawvideo','-pix_fmt','rgb24','-f','image2pipe','pipe:1'],resultBytes);
assert(roundTrip.equals(resultPixels),'Result PNG round-trip mismatch');
writeFileSync(path.join(root,'public/review-organize-result.png'),resultBytes);
writeFileSync(path.join(root,'out/review-organize-source-result-preview.png'),resultBytes);
const resultAsset={file:'public/review-organize-result.png',width:980,height:440,sourcePts:selectedResult.pts,crop:resultCrop,masks:resultBoxes,sha256:sha(resultBytes)};
audit.assets.push(resultAsset); publicMeta.assets.push(resultAsset);
const holdAsset={file:'public/review-organize-gmail-hold.png',...publicMeta.gmailHold};
audit.assets.push(holdAsset); publicMeta.assets.push(holdAsset);
const after=sha(readFileSync(source)); assert.equal(after,before,'Original source changed');
audit.sourceSha256After=after; audit.sourceUnchanged=true;
audit.privacy=publicMeta.privacy;
audit.manualVisualReview='See REVIEW-ORGANIZE-SOURCE.md for the exact manual review scope tied to current asset hashes. Generated contact sheets are not automatically manually reviewed; regeneration alone is not visual sign-off.';
writeFileSync(path.join(root,'out/review-organize-source-audit.json'),JSON.stringify(audit,null,2)+'\n');
writeFileSync(path.join(root,'public/review-organize-source.json'),JSON.stringify(publicMeta,null,2)+'\n');
console.log(JSON.stringify({sourceSha256:before,sourceUnchanged:true,result:resultAsset,hold:publicMeta.gmailHold},null,2));
