import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 15;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = 2 * Math.PI;
const SEED = 0x414e4c31;
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

// Static D6/9 suspension without a third: no cadence, melody, or approval motif.
const notes = [50, 57, 59, 64];
notes.forEach((note, index) => {
  const f = hz(note);
  const phase = (index + 1) * 0.91;
  voice(music, 0, SECONDS, [0.1, 0.074, 0.049, 0.055][index], (index - 1.5) * 0.28, (t) => {
    const color = 0.045 + 0.015 * smooth((t - 10.5) / 1);
    return 0.9 * Math.sin(TAU * f * t + phase)
      + 0.1 * Math.sin(TAU * f * 1.0003 * t + phase)
      + color * Math.sin(TAU * f * 2 * t + phase);
  });
});

// One softly attacked low pulse every 2.4 seconds; no kick, hats, or final hit.
const pulseTimes = [0.8, 3.2, 5.6, 8, 10.4, 12.8];
for (const start of pulseTimes) {
  voice(music, start, 1.15, 0.055, 0, (t) =>
    envelope(t, 1.15, 0.09, 0.4) * Math.exp(-t * 2.4)
    * (Math.sin(TAU * hz(38) * t) + 0.06 * Math.sin(TAU * hz(50) * t)));
}

const accents = [
  [0.5, 'Intro settles', 0.26, 0.13],
  [4, 'Output cut', 0.24, 0.12],
  [10.5, 'Category transition', 0.34, 0.16],
  [11.3, 'Category highlight 1', 0.22, 0.12],
  [11.7, 'Category highlight 2', 0.22, 0.12],
  [12.1, 'Category highlight 3', 0.22, 0.12],
  [12.5, 'Category highlight 4', 0.22, 0.12],
].map(([start, label, duration, amplitude], index) => {
  let low = 0;
  let bottom = 0;
  voice(sfx, start, duration, amplitude, index % 2 ? 0.08 : -0.08, (t) => {
    low += 0.045 * (noise() - low);
    bottom += 0.01 * (low - bottom);
    return (low - bottom) * envelope(t, duration, 0.025, duration * 0.6) * Math.exp(-t * 5);
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
  const fade = smooth(t / 0.25) * (1 - smooth((frame - 14.5 * RATE) / (0.5 * RATE - 1)));
  const duckDb = -3 * smooth((t - 0.65) / 0.35) * (1 - smooth((t - 10.5) / 0.8));
  const duck = 10 ** (duckDb / 20);
  if (t >= 1 && t <= 10.5) assert(Math.abs(duckDb + 3) < 1e-12);
  for (let channel = 0; channel < 2; channel++) {
    const i = frame * 2 + channel;
    music[i] *= fade;
    if (t >= 1 && t < 10.5) unduckedEnergy += music[i] ** 2;
    music[i] *= duck;
    if (t >= 1 && t < 10.5) duckedEnergy += music[i] ** 2;
    sfx[i] *= fade;
  }
}
const measuredDuckDb = db(Math.sqrt(duckedEnergy / unduckedEnergy));
assert(Math.abs(measuredDuckDb + 3) < 1e-9, 'Bed duck must be -3 dB');
const raw = measure(Float64Array.from(music, (value, i) => value + sfx[i]));
const gain = 10 ** (-25 / 20) / raw.rms;
const pcmMusic = Int32Array.from(music, (value) => Math.round(value * gain * MAX));
const pcmSfx = Int32Array.from(sfx, (value) => Math.round(value * gain * MAX));
// Quantize stems first so every decoded mix sample equals their integer sum.
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
  seed: `0x${SEED.toString(16)}`, sampleRate: RATE, channels: 2, bitsPerSample: 24,
  encoding: 'RIFF WAVE PCM signed 24-bit little-endian', durationSeconds: SECONDS, frames: FRAMES,
  commonGain: gain, pulseTimesSeconds: pulseTimes,
  fadeInSeconds: 0.25, fadeOutSeconds: 0.5, fadeOutStartSeconds: 14.5,
  targetMixRmsDbfs: -25, maximumSamplePeakDbfs: -6,
  duck: {start: 1, end: 10.5, rampInStart: 0.65, rampOutEnd: 11.3, gainDb: -3,
    measuredMusicAttenuationDb: measuredDuckDb, sfxDucked: false,
    measurement: '1-10.5s energy ratio against the identical faded bed without duck, before PCM quantization.'},
  accents,
  measurement: 'Decoded PCM; unweighted stereo sample RMS and sample peak, not LUFS or true peak. Full scale = 8388607; null means silence.',
  repeatability: 'node scripts/generate-analyze-audio.mjs --verify regenerates in memory, compares every WAV and JSON byte, and decodes the on-disk WAVs; read-only. Same Node runtime/platform is the bit-identical reference.',
  files: {}, checks: {},
};
const assets = new Map();
const decodedTracks = [];
for (const [name, pcm] of [['analyze-music.wav', pcmMusic], ['analyze-sfx.wav', pcmSfx], ['analyze-mix.wav', pcmMix]]) {
  const expected = wav(pcm);
  const buffer = verify ? readFileSync(new URL(name, output)) : expected;
  assert.deepEqual(buffer, expected, `${name} is not byte-identical`);
  assert.equal(buffer.length, 4320044);
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
  assert([decoded[0], decoded[1], decoded.at(-2), decoded.at(-1)].every((v) => v === 0), 'Nonzero endpoint');
  const levels = measure(decoded, 0, SECONDS, MAX);
  assert.equal(levels.clippedSamples, 0);
  assert(levels.samplePeakDbfs < -6, 'Stem or mix exceeds peak ceiling');
  stats.files[name] = {bytes: buffer.length, frames, durationSeconds: frames / RATE, ...levels,
    sections: Object.fromEntries([[0, 0.6], [0.8, 1], [1, 4], [4, 10.5], [10.5, 11.5], [11.5, 14], [14, 15]]
      .map(([start, end]) => [`${start}-${end}`, measure(decoded, start, end, MAX)])),
    sha256: createHash('sha256').update(buffer).digest('hex')};
  decodedTracks.push(decoded);
  assets.set(name, expected);
}
for (let i = 0; i < FRAMES * 2; i++) {
  assert.equal(decodedTracks[2][i], decodedTracks[0][i] + decodedTracks[1][i], 'Stem sum mismatch');
}
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
  assert(levels.samplePeakDbfs < -30, 'Accent is not subtle');
  event.rmsDbfs = levels.rmsDbfs;
  event.samplePeakDbfs = levels.samplePeakDbfs;
});
let minimumWindowRmsDbfs = Infinity;
for (let frame = 0.25 * RATE; frame + 0.1 * RATE <= 14.5 * RATE; frame += 0.1 * RATE) {
  const levels = measure(decodedTracks[0], frame / RATE, frame / RATE + 0.1, MAX);
  assert(levels.rms > 10 ** (-40 / 20), 'Interior bed is too quiet or silent');
  minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, levels.rmsDbfs);
}
assert(Math.abs(stats.files['analyze-mix.wav'].rmsDbfs + 25) < 0.01, 'Mix RMS outside -25 +/- 0.01 dBFS');
stats.checks = {exactDurationAndFormat: true, exactStemSum: true, stemSumResidualPcm: 0,
  interleavedSamplesCompared: FRAMES * 2, zeroEndpoints: true, noClipping: true,
  sevenScheduledAccentsOnly: true, musicDuck3Db: true, mixRmsTarget: true, allSamplePeaksBelowMinus6: true,
  continuity: {windowSeconds: 0.1, firstWindowStart: 0.25, lastWindowEnd: 14.45, minimumWindowRmsDbfs}};
assets.set('analyze-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} is not byte-identical`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated analyze audio'}: ${fileURLToPath(output)}`);
console.table(Object.entries(stats.files).map(([file, entry]) => ({file, seconds: entry.durationSeconds,
  frames: entry.frames, 'RMS dBFS': entry.rmsDbfs.toFixed(3),
  'sample peak dBFS': entry.samplePeakDbfs.toFixed(3), 'clipped samples': entry.clippedSamples})));
console.log('PASS: exact duration/format, exact PCM stem sum, zero endpoints, continuous bed, 7 soft accents, -3 dB reading duck.');
