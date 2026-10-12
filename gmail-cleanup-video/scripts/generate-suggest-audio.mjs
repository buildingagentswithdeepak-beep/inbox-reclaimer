import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 8;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = 2 * Math.PI;
const SEED = 0x53554731;
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

// Static D-A-E voicing: no third, melody, chord resolution, or closing hit.
const notes = [50, 57, 64];
notes.forEach((note, index) => {
  const f = hz(note);
  const phase = (index + 1) * 1.17;
  voice(music, 0, SECONDS, [0.105, 0.068, 0.039][index], (index - 1) * 0.22, (t) =>
    0.9 * Math.sin(TAU * f * t + phase)
    + 0.1 * Math.sin(TAU * f * 1.00018 * t + phase)
    + 0.025 * Math.sin(TAU * f * 2 * t + phase));
});

const accents = [
  [0.5, 'Command', 0.22, 0.12],
  [2.3, 'Saved plan', 0.26, 0.12],
  [4.5, 'Local report', 0.24, 0.12],
  [5.5, 'Amber badge', 0.28, 0.10],
].map(([start, label, duration, amplitude], index) => {
  let low = 0;
  let soft = 0;
  let bottom = 0;
  voice(sfx, start, duration, amplitude, index % 2 ? 0.06 : -0.06, (t) => {
    low += 0.065 * (noise() - low);
    soft += 0.09 * (low - soft);
    bottom += 0.012 * (soft - bottom);
    return (soft - bottom) * envelope(t, duration, 0.03, duration * 0.6) * Math.exp(-t * 5);
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
  const fade = smooth(t / 0.2) * (1 - smooth((frame - 7.5 * RATE) / (0.5 * RATE - 1)));
  const duckDb = -3 * smooth((t - 0.7) / 0.3) * (1 - smooth((t - 6.5) / 0.6));
  const duck = 10 ** (duckDb / 20);
  if (frame >= RATE && frame <= 6.5 * RATE) assert(Math.abs(duckDb + 3) < 1e-12);
  for (let channel = 0; channel < 2; channel++) {
    const i = frame * 2 + channel;
    music[i] *= fade;
    if (t >= 1 && t < 6.5) unduckedEnergy += music[i] ** 2;
    music[i] *= duck;
    if (t >= 1 && t < 6.5) duckedEnergy += music[i] ** 2;
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
  title: 'Suggest - neutral ambient instrumental',
  seed: `0x${SEED.toString(16)}`, sampleRate: RATE, channels: 2, bitsPerSample: 24,
  encoding: 'RIFF WAVE PCM signed 24-bit little-endian', durationSeconds: SECONDS, frames: FRAMES,
  commonGain: gain, padMidiNotes: notes,
  synthesis: 'Original local oscillators and seeded filtered noise; no external audio, narrator, creator voice, approval or success stings.',
  fadeInSeconds: 0.2, fadeOutSeconds: 0.5, fadeOutStartSeconds: 7.5,
  targetMixRmsDbfs: -25, maximumSamplePeakDbfs: -6,
  duck: {start: 1, end: 6.5, rampInStart: 0.7, rampOutEnd: 7.1, gainDb: -3,
    measuredMusicAttenuationDb: measuredDuckDb, sfxDucked: false,
    measurement: '1-6.5s energy ratio against the identical faded bed without duck, before PCM quantization.'},
  accents,
  measurement: 'Decoded PCM; unweighted stereo sample RMS and sample peak, not LUFS or true peak. Full scale = 8388607; null means silence.',
  repeatability: 'node scripts/generate-suggest-audio.mjs --verify regenerates in memory, compares every WAV and JSON byte, and decodes the on-disk WAVs; read-only. Same Node runtime/platform is the bit-identical reference.',
  files: {}, checks: {},
};
const assets = new Map();
const decodedTracks = [];
for (const [name, pcm] of [['suggest-music.wav', pcmMusic], ['suggest-sfx.wav', pcmSfx], ['suggest-mix.wav', pcmMix]]) {
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
    sections: Object.fromEntries([[0, 0.2], [0.2, 0.7], [0.7, 1], [1, 6.5], [6.5, 7.1], [7.1, 7.5], [7.5, 8]]
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
  assert(levels.samplePeakDbfs < -30, 'Accent exceeds subtle peak ceiling');
  event.rmsDbfs = levels.rmsDbfs;
  event.samplePeakDbfs = levels.samplePeakDbfs;
});
let minimumWindowRmsDbfs = Infinity;
for (let tenth = 2; tenth < 75; tenth++) {
  const levels = measure(decodedTracks[0], tenth / 10, (tenth + 1) / 10, MAX);
  assert(levels.rms > 10 ** (-40 / 20), 'Interior bed is too quiet or silent');
  minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, levels.rmsDbfs);
}
assert(Math.abs(stats.files['suggest-mix.wav'].rmsDbfs + 25) < 0.01, 'Mix RMS outside -25 +/- 0.01 dBFS');
stats.checks = {exactDurationAndFormat: true, exactStemSum: true, stemSumResidualPcm: 0,
  interleavedSamplesCompared: FRAMES * 2, zeroEndpoints: true, noClipping: true,
  fourScheduledAccentsOnly: true, musicDuck3Db: true, mixRmsTarget: true, allSamplePeaksBelowMinus6: true,
  continuity: {windowSeconds: 0.1, start: 0.2, end: 7.5, minimumWindowRmsDbfs}};
assets.set('suggest-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} is not byte-identical`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated suggest audio'}: ${fileURLToPath(output)}`);
console.table(Object.entries(stats.files).map(([file, entry]) => ({file, seconds: entry.durationSeconds,
  frames: entry.frames, 'RMS dBFS': entry.rmsDbfs.toFixed(3),
  'sample peak dBFS': entry.samplePeakDbfs.toFixed(3), 'clipped samples': entry.clippedSamples})));
console.log('PASS: exact duration/format, exact PCM stem sum, zero endpoints, continuous bed, 4 unpitched accents, -3 dB reading duck.');
