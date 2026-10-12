import {spawnSync} from 'node:child_process';
import {writeFileSync} from 'node:fs';
import path from 'node:path';

const bin = path.resolve('node_modules/@remotion/compositor-win32-x64-msvc');
const intro = process.argv[2] === 'intro';
const clutter = process.argv[2] === 'clutter';
const reportScene = process.argv[2] === 'report';
const stack = process.argv[2] === 'stack';
const analyze = process.argv[2] === 'analyze';
const identify = process.argv[2] === 'identify';
const suggest = process.argv[2] === 'suggest';
const reviewOrganize = process.argv[2] === 'review-organize';
const seconds = reviewOrganize ? 30 : suggest ? 8 : identify ? 10 : analyze ? 15 : stack ? 10 : reportScene ? 19 : clutter ? 24 : 18;
const output = reviewOrganize ? 'out/gmail-cleanup-agent-review-organize-30s-1080p.mp4' : suggest ? 'out/gmail-cleanup-agent-suggest-8s-1080p.mp4' : identify ? 'out/gmail-cleanup-agent-identify-10s-1080p.mp4' : analyze ? 'out/gmail-cleanup-agent-analyze-15s-1080p.mp4' : stack ? 'out/gmail-cleanup-agent-stack-10s-1080p.mp4' : reportScene ? 'out/gmail-cleanup-agent-report-19s-1080p.mp4' : clutter ? 'out/gmail-cleanup-agent-clutter-24s-1080p.mp4' : intro ? 'out/gmail-cleanup-agent-introduction-18s-1080p.mp4' : 'out/gmail-cleanup-agent-18s-1080p.mp4';
function run(tool, args, binary = false) {
  const result = spawnSync(path.join(bin, `${tool}.exe`), args, {encoding: binary ? undefined : 'utf8', maxBuffer: 64 * 1024 * 1024});
  if (result.status !== 0) throw new Error(result.stderr?.toString() || `${tool} failed`);
  return result.stdout;
}

// AAC packet padding must not extend the editorial duration of the delivery.
run('ffmpeg', ['-y', '-v', 'error', '-i', reviewOrganize ? 'out/gmail-review-organize-render.mp4' : suggest ? 'out/gmail-suggest-render.mp4' : identify ? 'out/gmail-identify-render.mp4' : analyze ? 'out/gmail-analyze-render.mp4' : stack ? 'out/gmail-stack-render.mp4' : reportScene ? 'out/gmail-report-render.mp4' : clutter ? 'out/gmail-clutter-render.mp4' : intro ? 'out/gmail-introduction-render.mp4' : 'out/gmail-cleanup-agent-hook-1080p.mp4', '-i', reviewOrganize ? 'public/audio/review-organize-mix.wav' : suggest ? 'public/audio/suggest-mix.wav' : identify ? 'public/audio/identify-mix.wav' : analyze ? 'public/audio/analyze-mix.wav' : stack ? 'public/audio/stack-mix.wav' : reportScene ? 'public/audio/report-mix.wav' : clutter ? 'public/audio/clutter-mix.wav' : intro ? 'public/audio/intro-mix.wav' : 'public/audio/mix-preview.wav', '-t', String(seconds), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', output]);
const metadata = JSON.parse(run('ffprobe', ['-v', 'error', '-show_entries', 'format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels', '-of', 'json', output]));
const video = metadata.streams.find(s => s.codec_type === 'video');
const audio = metadata.streams.find(s => s.codec_type === 'audio');
if (Number(metadata.format.duration) !== seconds || Number(video.nb_frames) !== seconds * 60 || video.width !== 1920 || video.height !== 1080 || video.r_frame_rate !== '60/1' || audio.channels !== 2) throw new Error('Delivery metadata did not match the production contract');
const wav = run('ffmpeg', ['-v', 'error', '-i', output, '-vn', '-t', String(seconds), '-f', 'wav', '-acodec', 'pcm_s16le', 'pipe:1'], true);
let offset = 12;
while (wav.toString('ascii', offset, offset + 4) !== 'data') {
  const size = wav.readUInt32LE(offset + 4);
  offset += 8 + size + (size % 2);
  if (offset + 8 > wav.length) throw new Error('No decoded WAV data');
}
const pcm = wav.subarray(offset + 8);
let peak = 0;
let squares = 0;
for (let i = 0; i < pcm.length; i += 2) {
  const value = pcm.readInt16LE(i) / 32768;
  peak = Math.max(peak, Math.abs(value));
  squares += value * value;
}
if (peak >= 1) throw new Error('Encoded audio clips');
const report = {file: output, ...metadata, audioMeasurements: {samplePeakDbfs: 20 * Math.log10(peak), rmsDbfs: 10 * Math.log10(squares / (pcm.length / 2)), clipped: false}, notes: ['Measured after decoding to 16-bit PCM: sample peak and RMS, not LUFS or oversampled true peak.', stack ? 'Graphics-only stack; source-verified dependency; illustrative metadata flow; no runtime LLM calls.' : reportScene ? 'Supplied report with visible senders as requested; editorial workflow stops at Review; text-only handoff.' : clutter ? 'Fictional inbox, 24 accelerating arrivals, anchored important mail, no deletions, final picture hold from 20.5 seconds.' : intro ? 'Animated title opening without presenter footage; genuine screenshot with illustrative email rows; tidy inbox is a concept, not verified cleanup.' : 'Final monitor handoff is illustrative.']};
if (analyze) report.notes[1] = 'Privacy-baked normal-speed excerpts of supplied Review.mp4. Recorded --redact-subjects; limited 1000-message preview. External scan and editorial category highlights; no cleanup approved.';
if (identify) report.notes[1] = 'Corrected source ReportSender.mp4, browser sender-frequency report held for readability. noreply@medium.com row highlighted; actual senders visible. Browser chrome, account details, paths and IDs excluded by crop. Independent fictional inbox rows unchanged. Sender-specific illustrative command not executed; no approval or plan ID fabricated.';
if (suggest) report.notes[1] = 'Actual preview command without --execute and saved-plan output from SelectedEMailPlan.mp4; matching local HTML report, source frames held for readability. Plan ID intentionally visible; private fields excluded. Amber Awaiting review editorial badge. No creator footage or approval.';
if (reviewOrganize) report.notes[1] = 'Continuous normal-speed native confirmation excerpt; email addresses and subjects visible as requested, internal IDs and paths masked. Gmail crop has no masks. Amber until full recorded dismissal at 13s, Organize only at 14s. Explicit Later cuts to held result and Gmail Trash footage. Reported counts 20 confirmed, 0 unknown, 0 skipped; Gmail visible rows not proof of all 20 IDs. No fabricated clicks, approval, rows, folders, labels, or creator footage.';
writeFileSync(reviewOrganize ? 'out/review-organize-verification.json' : suggest ? 'out/suggest-verification.json' : identify ? 'out/identify-verification.json' : analyze ? 'out/analyze-verification.json' : stack ? 'out/stack-verification.json' : reportScene ? 'out/report-verification.json' : clutter ? 'out/clutter-verification.json' : intro ? 'out/introduction-verification.json' : 'out/verification.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
