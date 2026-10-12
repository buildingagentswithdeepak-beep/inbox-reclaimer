import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 30;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = 2 * Math.PI;
const SEED = 0x524f4131;
const BPM = 90;
const output = new URL('../public/audio/', import.meta.url);
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(statSync(output).isDirectory(), 'public/audio must already exist');

const music = new Float64Array(FRAMES * 2);
const sfx = new Float64Array(FRAMES * 2);
let state = SEED;
function noise() {
  state ^= state << 13;
  state ^= state >>> 17;
  state ^= state << 5;
  return (state >>> 0) / 2147483648 - 1;
}
const hz = (note) => 440 * 2 ** ((note - 69) / 12);
const smooth = (x) => {
  const v = Math.max(0, Math.min(1, x));
  return v * v * (3 - 2 * v);
};
const envelope = (t, duration, attack, release) =>
  smooth(t / attack) * smooth((duration - t) / release);
const db = (value) => value === 0 ? null : 20 * Math.log10(value);

function voice(track, start, duration, amplitude, pan, sample) {
  const first = Math.round(start * RATE);
  const length = Math.round(duration * RATE);
  const left = amplitude * Math.cos((pan + 1) * Math.PI / 4);
  const right = amplitude * Math.sin((pan + 1) * Math.PI / 4);
  for (let j = Math.max(0, -first); j < length && first + j < FRAMES; j++) {
    const value = sample(j / RATE);
    assert(Number.isFinite(value), 'Non-finite synthesis sample');
    track[(first + j) * 2] += value * left;
    track[(first + j) * 2 + 1] += value * right;
  }
}

// Static open D-A-E bed avoids a verdict-like harmonic resolution.
const notes = [50, 57, 64];
notes.forEach((note, index) => {
  const f = hz(note);
  const phase = (index + 1) * 0.91;
  voice(music, 0, SECONDS, [0.09, 0.06, 0.034][index], (index - 1) * 0.24, (t) =>
    0.9 * Math.sin(TAU * f * t + phase)
    + 0.1 * Math.sin(TAU * f * 1.00012 * t + phase)
    + 0.025 * Math.sin(TAU * f * 2 * t + phase));
});

// Smooth continuous amplitude modulation, not kicks or UI-triggered hits.
voice(music, 0, SECONDS, 0.066, 0, (t) => {
  const pulse = (0.5 - 0.5 * Math.cos(TAU * BPM / 60 * t)) ** 2;
  return (0.6 + 0.4 * pulse)
    * (Math.sin(TAU * hz(38) * t) + 0.055 * Math.sin(TAU * hz(50) * t));
});

const accents = [
  [0.5, 'Quiet opening texture, not a UI click', 0.32, 0.10],
  [14, 'Later run result transition', 0.38, 0.10],
  [15, 'Actual run output held', 0.32, 0.09],
  [24, 'Later Gmail Trash check', 0.38, 0.10],
].map(([start, label, duration, amplitude], index) => {
  let low = 0;
  let soft = 0;
  let bottom = 0;
  voice(sfx, start, duration, amplitude, index % 2 ? 0.05 : -0.05, (t) => {
    low += 0.05 * (noise() - low);
    soft += 0.07 * (low - soft);
    bottom += 0.01 * (soft - bottom);
    return (soft - bottom) * envelope(t, duration, 0.06, duration * 0.65) * Math.exp(-t * 4);
  });
  return {label, timeSeconds: start, onsetFrame: Math.round(start * RATE), durationSeconds: duration};
});

function measure(samples, start = 0, end = SECONDS, scale = 1) {
  let peak = 0;
  let energy = 0;
  let sum = 0;
  let clippedSamples = 0;
  const first = Math.round(start * RATE) * 2;
  const last = Math.round(end * RATE) * 2;
  for (let i = first; i < last; i++) {
    const value = samples[i] / scale;
    assert(Number.isFinite(value), 'Non-finite measurement sample');
    peak = Math.max(peak, Math.abs(value));
    energy += value * value;
    sum += value;
    if (Math.abs(value) >= 1) clippedSamples++;
  }
  const rms = Math.sqrt(energy / (last - first));
  return {rmsDbfs: db(rms), samplePeakDbfs: db(peak), rms, peak, clippedSamples, dcOffset: sum / (last - first)};
}

let unduckedEnergy = 0;
let duckedEnergy = 0;
for (let frame = 0; frame < FRAMES; frame++) {
  const t = frame / RATE;
  const fade = smooth(t / 0.3) * (1 - smooth((frame - 29.3 * RATE) / (0.7 * RATE - 1)));
  const duckDb = -3 * smooth((t - 0.5) / 0.3) * (1 - smooth((t - 13.8) / 0.5));
  const duck = 10 ** (duckDb / 20);
  if (frame >= 0.8 * RATE && frame <= 13.8 * RATE) assert(Math.abs(duckDb + 3) < 1e-12);
  for (let channel = 0; channel < 2; channel++) {
    const i = frame * 2 + channel;
    music[i] *= fade;
    if (t >= 0.8 && t < 13.8) unduckedEnergy += music[i] ** 2;
    music[i] *= duck;
    if (t >= 0.8 && t < 13.8) duckedEnergy += music[i] ** 2;
    sfx[i] *= fade;
  }
}
const measuredDuckDb = db(Math.sqrt(duckedEnergy / unduckedEnergy));
assert(Math.abs(measuredDuckDb + 3) < 1e-9, 'Bed duck must be -3 dB');
const raw = measure(Float64Array.from(music, (value, i) => value + sfx[i]));
const gain = 10 ** (-25 / 20) / raw.rms;
const pcmMusic = Int32Array.from(music, (value) => Math.round(value * gain * MAX));
const pcmSfx = Int32Array.from(sfx, (value) => Math.round(value * gain * MAX));
// Quantize stems first; no post-sum limiter or gain can break exact PCM equality.
const pcmMix = Int32Array.from(pcmMusic, (value, i) => value + pcmSfx[i]);

function wav(samples) {
  const buffer = Buffer.alloc(44 + samples.length * 3);
  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(buffer.length - 8, 4);
  buffer.write('WAVEfmt ', 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(2, 22);
  buffer.writeUInt32LE(RATE, 24);
  buffer.writeUInt32LE(RATE * 6, 28);
  buffer.writeUInt16LE(6, 32);
  buffer.writeUInt16LE(24, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(samples.length * 3, 40);
  samples.forEach((sample, i) => {
    assert(Number.isInteger(sample) && Math.abs(sample) < MAX, 'Invalid or clipped PCM sample');
    buffer.writeIntLE(sample, 44 + i * 3, 3);
  });
  return buffer;
}

const stats = {
  title: 'Review and organize - restrained neutral ambient instrumental',
  seed: `0x${SEED.toString(16)}`, sampleRate: RATE, channels: 2, bitsPerSample: 24,
  encoding: 'RIFF WAVE PCM signed 24-bit little-endian', durationSeconds: SECONDS, frames: FRAMES,
  commonGain: gain, padMidiNotes: notes, lowPulseMidiNote: 38, pulseBpm: BPM,
  synthesis: 'Original local oscillators and seeded filtered noise; no external audio, voiceover, invented click, approval fanfare, or closing hit.',
  fadeInSeconds: 0.3, fadeOutSeconds: 0.7, fadeOutStartSeconds: 29.3,
  targetMixRmsDbfs: -25, maximumSamplePeakDbfs: -6,
  duck: {start: 0.8, end: 13.8, rampInStart: 0.5, rampOutEnd: 14.3, gainDb: -3,
    measuredMusicAttenuationDb: measuredDuckDb, sfxDucked: false,
    measurement: '0.8-13.8s energy ratio against identical faded bed without duck, before PCM quantization.'},
  timeline: [
    {start: 0, end: 14, intent: 'Genuine native confirmation, continuous 1x',
      sourceClickSeconds: 60.65, sceneClickSeconds: 12.65, sceneDismissalSeconds: 13, addedActionSfx: false},
    {start: 14, end: 15, intent: 'Later run result transition'},
    {start: 15, end: 24, intent: 'Actual run output held'},
    {start: 24, end: 30, intent: 'Later Gmail Trash check'},
  ],
  timelineScope: 'User-supplied synchronization contract, not independent footage verification; generator does not modify or mix source footage audio.',
  accents,
  measurement: 'Decoded PCM; unweighted stereo sample RMS and sample peak, not LUFS or true peak. Full scale = 8388607; null means silence.',
  repeatability: 'node scripts/generate-review-organize-audio.mjs --verify regenerates in memory, compares every WAV and JSON byte, and decodes on-disk WAVs; read-only. Same Node runtime/platform is the bit-identical reference.',
  files: {}, checks: {},
};
const assets = new Map();
const decodedTracks = [];
for (const [suffix, pcm] of [['music', pcmMusic], ['sfx', pcmSfx], ['mix', pcmMix]]) {
  const name = `review-organize-${suffix}.wav`;
  const expected = wav(pcm);
  const buffer = verify ? readFileSync(new URL(name, output)) : expected;
  assert.deepEqual(buffer, expected, `${name} is not byte-identical`);
  assert.equal(buffer.length, 44 + FRAMES * 6);
  assert.equal(buffer.toString('ascii', 0, 4), 'RIFF');
  assert.equal(buffer.toString('ascii', 8, 16), 'WAVEfmt ');
  assert.equal(buffer.toString('ascii', 36, 40), 'data');
  assert.equal(buffer.readUInt32LE(4) + 8, buffer.length);
  assert.equal(buffer.readUInt32LE(16), 16);
  assert.equal(buffer.readUInt16LE(20), 1);
  assert.equal(buffer.readUInt16LE(22), 2);
  assert.equal(buffer.readUInt32LE(24), RATE);
  assert.equal(buffer.readUInt32LE(28), RATE * 6);
  assert.equal(buffer.readUInt16LE(32), 6);
  assert.equal(buffer.readUInt16LE(34), 24);
  assert.equal(buffer.readUInt32LE(40), buffer.length - 44);
  const frames = buffer.readUInt32LE(40) / buffer.readUInt16LE(32);
  assert.equal(frames, FRAMES);
  assert.equal(frames / buffer.readUInt32LE(24), SECONDS);
  const decoded = Int32Array.from({length: frames * 2}, (_, i) => buffer.readIntLE(44 + i * 3, 3));
  assert.deepEqual(decoded, pcm);
  const endpoints = {first: [decoded[0], decoded[1]], last: [decoded.at(-2), decoded.at(-1)]};
  assert([...endpoints.first, ...endpoints.last].every((v) => v === 0), 'Nonzero endpoint');
  const levels = measure(decoded, 0, SECONDS, MAX);
  assert.equal(levels.clippedSamples, 0);
  assert(levels.samplePeakDbfs < -6, 'Stem or mix exceeds peak ceiling');
  stats.files[name] = {bytes: buffer.length, frames, durationSeconds: frames / RATE, ...levels, endpoints,
    sections: Object.fromEntries([[0, 0.3], [0.3, 0.5], [0.5, 0.8], [0.8, 13.8], [13.8, 14],
      [14, 15], [15, 24], [24, 29.3], [29.3, 30]]
      .map(([start, end]) => [`${start}-${end}`, measure(decoded, start, end, MAX)])),
    sha256: createHash('sha256').update(buffer).digest('hex')};
  decodedTracks.push(decoded);
  assets.set(name, expected);
}
for (let i = 0; i < FRAMES * 2; i++) {
  assert.equal(decodedTracks[2][i], decodedTracks[0][i] + decodedTracks[1][i], 'Stem sum mismatch');
}
assert.deepEqual(accents.map((event) => event.timeSeconds), [0.5, 14, 15, 24]);
for (let frame = 0; frame < FRAMES; frame++) {
  const inAccent = accents.some((event) => frame >= event.onsetFrame
    && frame < event.onsetFrame + Math.round(event.durationSeconds * RATE));
  if (!inAccent) {
    assert.equal(decodedTracks[1][frame * 2], 0, 'Unexpected SFX outside cue');
    assert.equal(decodedTracks[1][frame * 2 + 1], 0, 'Unexpected SFX outside cue');
  }
}
accents.forEach((event) => {
  const levels = measure(decodedTracks[1], event.timeSeconds, event.timeSeconds + event.durationSeconds, MAX);
  assert(levels.rms > 0, 'Missing accent');
  assert(levels.samplePeakDbfs < -30, 'Accent exceeds subtle peak ceiling');
  event.rmsDbfs = levels.rmsDbfs;
  event.samplePeakDbfs = levels.samplePeakDbfs;
});
assert.equal(measure(decodedTracks[1], 12.5, 13.2, MAX).peak, 0, 'Added click or dismissal sound');
let minimumWindowRmsDbfs = Infinity;
for (let tenth = 3; tenth < 293; tenth++) {
  const levels = measure(decodedTracks[0], tenth / 10, (tenth + 1) / 10, MAX);
  assert(levels.rms > 10 ** (-40 / 20), 'Interior bed is too quiet or silent');
  minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, levels.rmsDbfs);
}
assert(Math.abs(stats.files['review-organize-mix.wav'].rmsDbfs + 25) < 0.01, 'Mix RMS outside -25 +/- 0.01 dBFS');
stats.checks = {exactDurationAndFormat: true, exactStemSum: true, stemSumResidualPcm: 0,
  interleavedSamplesCompared: FRAMES * 2, zeroEndpoints: true, noClipping: true,
  fourScheduledAccentsOnly: true, noAddedClickOrDismissalSfx: true, musicDuck3Db: true,
  mixRmsTarget: true, allSamplePeaksBelowMinus6: true,
  continuity: {windowSeconds: 0.1, start: 0.3, end: 29.3, minimumWindowRmsDbfs}};
assets.set('review-organize-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} is not byte-identical`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated review-organize audio'}: ${fileURLToPath(output)}`);
console.table(Object.entries(stats.files).map(([file, entry]) => ({file, seconds: entry.durationSeconds,
  frames: entry.frames, 'RMS dBFS': entry.rmsDbfs.toFixed(3),
  'sample peak dBFS': entry.samplePeakDbfs.toFixed(3), 'clipped samples': entry.clippedSamples})));
console.log('PASS: exact duration/format, exact PCM stem sum, zero endpoints, continuous 90 BPM bed, 4 quiet accents, -3 dB dialog duck, no added click/dismissal SFX.');
