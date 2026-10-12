import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 18;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = Math.PI * 2;
const BEAT = 60 / 100;
const SEED = 0x494e5452;
const ACCENTS = [0.3, 4, 7, 11.3, 12.15, 13, 14.4, 15.4, 16.1];
const output = new URL('../public/audio/', import.meta.url);
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(statSync(output).isDirectory(), 'Project public/audio/ must already exist');

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
  for (let j = 0; j < length && first + j < FRAMES; j++) {
    if (first + j < 0) continue;
    const value = sample(j / RATE);
    assert(Number.isFinite(value), 'Non-finite synthesis sample');
    track[(first + j) * 2] += value * left;
    track[(first + j) * 2 + 1] += value * right;
  }
}

// Common tones and overlapping releases keep the bed continuous, not scene-gated.
const chords = [[50, 57, 61, 64], [47, 54, 57, 62], [43, 54, 57, 62], [45, 52, 57, 59]];
chords.forEach((notes, chord) => {
  const start = chord * 4.8 - 0.6;
  notes.forEach((note, index) => {
    const f = hz(note);
    const phase = 0.63 * (index + 1);
    voice(music, start, 6.3, 0.115, (index - 1.5) * 0.22, (t) =>
      envelope(t, 6.3, 0.9, 1.25) * (
        0.72 * Math.sin(TAU * f * t + phase)
        + 0.28 * Math.sin(TAU * f * 1.0009 * t + phase)
        + 0.07 * Math.sin(TAU * f * 2 * t + phase)));
  });
});

const motif = [66, 64, 61, 64, 62, 61, 57, 61, 62, 57, 54, 57, 59, 57, 64];
motif.forEach((note, i) => {
  const f = hz(note);
  const start = 0.6 + i * 1.2;
  const pan = i % 2 ? 0.24 : -0.24;
  const sample = (t) => envelope(t, 1.65, 0.018, 0.3) * Math.exp(-t * 3.7)
    * (Math.sin(TAU * f * t) + 0.12 * Math.exp(-t * 5) * Math.sin(TAU * f * 2 * t));
  voice(music, start, 1.65, 0.055, pan, sample);
  voice(music, start + BEAT * 0.75, 1.65, 0.008, -pan, sample);
});

for (let beat = 0; beat < 30; beat++) {
  const start = beat * BEAT;
  if (beat % 2 === 0) {
    const f = hz(chords[Math.min(3, Math.floor(start / 4.8))][0] - 12);
    voice(music, start, 1.35, 0.07, 0, (t) =>
      envelope(t, 1.35, 0.045, 0.35) * Math.exp(-t * 2.4)
      * (Math.sin(TAU * f * t) + 0.09 * Math.sin(TAU * f * 2 * t)));
    voice(music, start, 0.28, 0.027, 0, (t) =>
      envelope(t, 0.28, 0.012, 0.08) * Math.exp(-t * 18)
      * Math.sin(TAU * (51 * t + 0.32 * (1 - Math.exp(-t / 0.024)))));
  } else {
    let low = 0;
    voice(music, start, 0.17, 0.018, -0.1, (t) => {
      low += 0.09 * (noise() - low);
      return low * envelope(t, 0.17, 0.015, 0.09) * Math.exp(-t * 12);
    });
  }
}

// Short filtered fabric/air accents: no pitched pings or success cadence.
ACCENTS.forEach((start, index) => {
  let low = 0;
  let bottom = 0;
  voice(sfx, start, 0.38, index === 2 ? 0.12 : 0.15, index % 2 ? 0.12 : -0.12, (t) => {
    low += 0.075 * (noise() - low);
    bottom += 0.009 * (low - bottom);
    return (low - bottom) * envelope(t, 0.38, 0.045, 0.18) * Math.exp(-t * 5);
  });
});

function measure(samples, start = 0, end = SECONDS, scale = 1) {
  let peak = 0;
  let energy = 0;
  let clippedSamples = 0;
  let sum = 0;
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
  return {samplePeakDbfs: db(peak), rmsDbfs: db(rms), peak, rms, clippedSamples, dcOffset: sum / (last - first)};
}

const beforeDuck = measure(music, 7, 11).rms;
for (let frame = 0; frame < FRAMES; frame++) {
  const t = frame / RATE;
  const fade = smooth(t / 0.3) * smooth((FRAMES - 1 - frame) / (RATE * 0.6));
  const duck = 10 ** (-4 * smooth((t - 6.8) / 0.2) * (1 - smooth((t - 11) / 0.25)) / 20);
  for (let channel = 0; channel < 2; channel++) {
    music[frame * 2 + channel] *= fade * duck;
    sfx[frame * 2 + channel] *= fade * duck;
  }
}
const measuredDuckDb = db(measure(music, 7, 11).rms / beforeDuck);
assert(Math.abs(measuredDuckDb + 4) < 1e-9, 'Caveat duck must be exactly -4 dB');
const rawMix = Float64Array.from(music, (value, i) => value + sfx[i]);
const raw = measure(rawMix);
const gain = Math.min(10 ** (-23.5 / 20) / raw.rms, 10 ** (-6.2 / 20) / raw.peak);
const pcmMusic = Int32Array.from(music, (sample) => Math.round(sample * gain * MAX));
const pcmSfx = Int32Array.from(sfx, (sample) => Math.round(sample * gain * MAX));
// Sum quantized stems, so the lossless mix is their exact integer PCM sum.
const pcmMix = Int32Array.from(pcmMusic, (sample, i) => sample + pcmSfx[i]);

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
    assert(Math.abs(sample) < MAX, 'Clipping detected');
    buffer.writeIntLE(sample, 44 + i * 3, 3);
  });
  return buffer;
}

const stats = {
  seed: `0x${SEED.toString(16)}`, sampleRate: RATE, channels: 2, bitsPerSample: 24,
  durationSeconds: SECONDS, frames: FRAMES, bpm: 100, commonGain: gain,
  fadeInSeconds: 0.3, fadeOutSeconds: 0.6,
  duck: {start: 7, end: 11, rampInStart: 6.8, rampOutEnd: 11.25, measuredMusicAttenuationDb: measuredDuckDb},
  accentOnsetsSeconds: ACCENTS,
  measurement: 'Decoded PCM, unweighted stereo RMS and sample peak; not LUFS or true peak. null means digital silence.',
  files: {},
  checks: {exactStemSum: true, zeroEndpoints: true, noClipping: true},
};
const assets = new Map();
const decodedTracks = [];
for (const [name, pcm] of [['intro-music.wav', pcmMusic], ['intro-sfx.wav', pcmSfx], ['intro-mix.wav', pcmMix]]) {
  const buffer = wav(pcm);
  assert.equal(buffer.length, 5184044);
  assert.equal(buffer.readUInt32LE(4) + 8, buffer.length);
  assert.equal(buffer.readUInt16LE(20), 1);
  assert.equal(buffer.readUInt16LE(22), 2);
  assert.equal(buffer.readUInt32LE(24), RATE);
  assert.equal(buffer.readUInt16LE(34), 24);
  const frames = buffer.readUInt32LE(40) / buffer.readUInt16LE(32);
  assert.equal(frames, FRAMES);
  assert.equal(frames / buffer.readUInt32LE(24), SECONDS);
  const decoded = Int32Array.from({length: frames * 2}, (_, i) => buffer.readIntLE(44 + i * 3, 3));
  assert.deepEqual(decoded, pcm);
  assert([decoded[0], decoded[1], decoded.at(-2), decoded.at(-1)].every((v) => v === 0));
  const levels = measure(decoded, 0, SECONDS, MAX);
  assert.equal(levels.clippedSamples, 0);
  stats.files[name] = {
    bytes: buffer.length, frames, durationSeconds: frames / RATE, ...levels,
    caveat7to11: measure(decoded, 7, 11, MAX),
    sha256: createHash('sha256').update(buffer).digest('hex'),
  };
  decodedTracks.push(decoded);
  assets.set(name, buffer);
}
for (let i = 0; i < FRAMES * 2; i++) {
  assert.equal(decodedTracks[2][i], decodedTracks[0][i] + decodedTracks[1][i], 'Stem sum mismatch');
}
let minimumWindowRmsDbfs = Infinity;
let silentRun = 0;
let maxSilentFrames = 0;
for (let frame = Math.round(0.3 * RATE); frame < Math.round(17.4 * RATE); frame++) {
  silentRun = pcmMusic[frame * 2] === 0 && pcmMusic[frame * 2 + 1] === 0 ? silentRun + 1 : 0;
  maxSilentFrames = Math.max(maxSilentFrames, silentRun);
}
for (let tenth = 3; tenth < 174; tenth++) {
  const rms = measure(decodedTracks[0], tenth / 10, (tenth + 1) / 10, MAX).rms;
  assert(rms > 10 ** (-45 / 20), 'Interior music window is too quiet or silent');
  minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, db(rms));
}
assert.equal(maxSilentFrames, 0, 'Interior music must have no digitally silent stereo frames');
stats.checks.continuity = {windowSeconds: 0.1, start: 0.3, end: 17.4, minimumWindowRmsDbfs, maxSilentFrames};
const mix = stats.files['intro-mix.wav'];
assert(mix.samplePeakDbfs < -6, 'Mix peak must be below -6 dBFS');
assert(mix.rmsDbfs >= -25 && mix.rmsDbfs <= -22, 'Mix RMS outside -25 to -22 dBFS');
assets.set('intro-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} is not byte-identical`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated intro audio'}: ${fileURLToPath(output)}`);
console.table(Object.entries(stats.files).map(([file, entry]) => ({
  file, seconds: entry.durationSeconds, frames: entry.frames,
  'RMS dBFS': entry.rmsDbfs.toFixed(3), 'peak dBFS': entry.samplePeakDbfs.toFixed(3),
  'clipped samples': entry.clippedSamples,
})));
console.log(`PASS: exact stem sum, zero endpoints, continuous bed (minimum 100ms RMS ${minimumWindowRmsDbfs.toFixed(3)} dBFS), ${measuredDuckDb.toFixed(3)} dB duck.`);
