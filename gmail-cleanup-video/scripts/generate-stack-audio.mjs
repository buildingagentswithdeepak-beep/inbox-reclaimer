import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 10;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = 2 * Math.PI;
const BEAT = 60 / 100;
const SEED = 0x53544b31;
const output = new URL('../public/audio/', import.meta.url);
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(statSync(output).isDirectory(), 'public/audio must already exist');

// Independent arrangement; only synthesis/PCM patterns are shared with the report generator.
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

// Common-tone Dm9 / Bbmaj9 colors; no dominant cadence or rising approval motif.
const chords = [[50, 57, 60, 64], [46, 53, 60, 62], [50, 57, 60, 64]];
chords.forEach((notes, chord) => {
  const start = chord * 4.8 - 0.75;
  const duration = 6.3;
  notes.forEach((note, index) => {
    const f = hz(note);
    const phase = (index + 1) * 0.73;
    voice(music, start, duration, 0.105, (index - 1.5) * 0.24, (t) =>
      envelope(t, duration, 0.9, 1.1) * (
        0.82 * Math.sin(TAU * f * t + phase)
        + 0.18 * Math.sin(TAU * f * 1.0004 * t + phase)
        + 0.035 * Math.sin(TAU * f * 2 * t + phase)));
  });
});

for (let beat = 0; beat * BEAT < SECONDS; beat++) {
  const start = beat * BEAT;
  const chord = chords[Math.floor(start / 4.8)];
  if (beat % 2 === 0) {
    const f = hz(chord[0] - 12);
    voice(music, start, 1.1, 0.048, 0, (t) =>
      envelope(t, 1.1, 0.045, 0.3) * Math.exp(-t * 2.3)
      * (Math.sin(TAU * f * t) + 0.06 * Math.sin(TAU * 2 * f * t)));
    voice(music, start, 0.23, 0.025, 0, (t) =>
      envelope(t, 0.23, 0.014, 0.09) * Math.exp(-t * 14) * Math.sin(TAU * 56 * t));
  } else {
    let low = 0;
    voice(music, start, 0.16, 0.035, -0.12, (t) => {
      low += 0.075 * (noise() - low);
      return low * envelope(t, 0.16, 0.015, 0.08) * Math.exp(-t * 12);
    });
  }
  // Sparse, low-register keys remain subordinate to the reading, including the workflow cue.
  if (beat % 4 === 1) {
    const f = hz(chord[beat % 8 === 1 ? 2 : 1]);
    voice(music, start, 1.3, 0.03, beat % 8 === 1 ? -0.22 : 0.22, (t) =>
      envelope(t, 1.3, 0.04, 0.35) * Math.exp(-t * 3.4)
      * (Math.sin(TAU * f * t) + 0.05 * Math.exp(-t * 5) * Math.sin(TAU * f * 2 * t)));
  }
}

const accents = [
  [0.15, 'Stack name 1', 0.22, 0.24],
  [0.75, 'Stack name 2', 0.22, 0.24],
  [1.35, 'Stack name 3', 0.22, 0.24],
  [1.95, 'Stack name 4', 0.22, 0.24],
  [2.65, 'Dependency highlight', 0.34, 0.27],
  [4.5, 'No runtime LLM', 0.30, 0.21],
  [5.3, 'Metadata flow 1', 0.18, 0.22],
  [5.65, 'Metadata flow 2', 0.18, 0.22],
  [6, 'Metadata flow 3', 0.18, 0.22],
  [6.35, 'Metadata flow 4', 0.18, 0.22],
  [8, 'Workflow', 0.38, 0.24],
].map(([start, label, duration, amplitude], index) => {
  let low = 0;
  let bottom = 0;
  voice(sfx, start, duration, amplitude, index % 2 ? 0.1 : -0.1, (t) => {
    low += 0.065 * (noise() - low);
    bottom += 0.012 * (low - bottom);
    return (low - bottom) * envelope(t, duration, 0.018, duration * 0.55) * Math.exp(-t * 5);
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

const unduckedEnergy = [0, 0];
const duckedEnergy = [0, 0];
for (let frame = 0; frame < FRAMES; frame++) {
  const t = frame / RATE;
  const fade = smooth(t / 0.2) * (1 - smooth((frame - 9.6 * RATE) / (0.4 * RATE - 1)));
  const duckDb = -4 * smooth((t - 4.3) / 0.2) * (1 - smooth((t - 7.5) / 0.2));
  const duck = 10 ** (duckDb / 20);
  if (frame >= 4.5 * RATE && frame <= 7.5 * RATE) assert(Math.abs(duckDb + 4) < 1e-12);
  for (const [trackIndex, track] of [music, sfx].entries()) {
    for (let channel = 0; channel < 2; channel++) {
      const i = frame * 2 + channel;
      track[i] *= fade;
      if (t >= 4.5 && t < 7.5) unduckedEnergy[trackIndex] += track[i] ** 2;
      track[i] *= duck;
      if (t >= 4.5 && t < 7.5) duckedEnergy[trackIndex] += track[i] ** 2;
    }
  }
}
const measuredDuckDb = duckedEnergy.map((energy, i) => db(Math.sqrt(energy / unduckedEnergy[i])));
measuredDuckDb.forEach((value) => assert(Math.abs(value + 4) < 1e-9, 'Duck must be -4 dB'));
const raw = measure(Float64Array.from(music, (value, i) => value + sfx[i]));
const gain = 10 ** (-24 / 20) / raw.rms;
const pcmMusic = Int32Array.from(music, (value) => Math.round(value * gain * MAX));
const pcmSfx = Int32Array.from(sfx, (value) => Math.round(value * gain * MAX));
// Quantize stems first: an integer mix preserves an exactly zero null residual.
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
    assert(Math.abs(sample) < MAX, 'Clipping detected');
    buffer.writeIntLE(sample, 44 + i * 3, 3);
  });
  return buffer;
}

const stats = {
  seed: `0x${SEED.toString(16)}`, sampleRate: RATE, channels: 2, bitsPerSample: 24,
  durationSeconds: SECONDS, frames: FRAMES, bpm: 100, commonGain: gain,
  fadeInSeconds: 0.2, fadeOutSeconds: 0.4, fadeOutStartSeconds: 9.6,
  targetMixRmsDbfs: -24, maximumSamplePeakDbfs: -6,
  duck: {start: 4.5, end: 7.5, rampInStart: 4.3, rampOutEnd: 7.7, gainDb: -4,
    measuredMusicAttenuationDb: measuredDuckDb[0], measuredSfxAttenuationDb: measuredDuckDb[1],
    measurement: '4.5-7.5s energy ratio against identical faded signals without duck, before PCM quantization.'},
  accents,
  measurement: 'Decoded PCM; unweighted stereo RMS and sample peak, not LUFS or true peak. Full scale = 8388607; null means silence.',
  repeatability: 'node scripts/generate-stack-audio.mjs --verify regenerates in memory and compares every WAV and JSON byte; read-only.',
  files: {}, checks: {},
};
const assets = new Map();
const decodedTracks = [];
for (const [name, pcm] of [['stack-music.wav', pcmMusic], ['stack-sfx.wav', pcmSfx], ['stack-mix.wav', pcmMix]]) {
  const buffer = wav(pcm);
  assert.equal(buffer.length, 2880044);
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
  assert([decoded[0], decoded[1], decoded.at(-2), decoded.at(-1)].every((v) => v === 0));
  const levels = measure(decoded, 0, SECONDS, MAX);
  assert.equal(levels.clippedSamples, 0);
  assert(levels.samplePeakDbfs < -6, 'Stem or mix exceeds peak ceiling');
  stats.files[name] = {bytes: buffer.length, frames, durationSeconds: frames / RATE, ...levels,
    sections: Object.fromEntries([[0, 4.3], [4.5, 7.5], [7.7, 9.6], [9.6, 10]]
      .map(([start, end]) => [`${start}-${end}`, measure(decoded, start, end, MAX)])),
    sha256: createHash('sha256').update(buffer).digest('hex')};
  decodedTracks.push(decoded);
  assets.set(name, buffer);
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
  event.rmsDbfs = levels.rmsDbfs;
  event.samplePeakDbfs = levels.samplePeakDbfs;
});
let minimumWindowRmsDbfs = Infinity;
for (let tenth = 2; tenth < 96; tenth++) {
  const levels = measure(decodedTracks[0], tenth / 10, (tenth + 1) / 10, MAX);
  assert(levels.rms > 10 ** (-45 / 20), 'Interior bed is too quiet or silent');
  minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, levels.rmsDbfs);
}
assert(Math.abs(stats.files['stack-mix.wav'].rmsDbfs + 24) < 0.01, 'Mix RMS outside -24 +/- 0.01 dBFS');
stats.checks = {exactDurationAndFormat: true, exactStemSum: true, stemSumResidualPcm: 0,
  interleavedSamplesCompared: FRAMES * 2, zeroEndpoints: true, noClipping: true,
  elevenScheduledAccentsOnly: true, duck4Db: true, mixRmsTarget: true, allSamplePeaksBelowMinus6: true,
  continuity: {windowSeconds: 0.1, start: 0.2, end: 9.6, minimumWindowRmsDbfs}};
assets.set('stack-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} is not byte-identical`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated stack audio'}: ${fileURLToPath(output)}`);
console.table(Object.entries(stats.files).map(([file, entry]) => ({file, seconds: entry.durationSeconds,
  frames: entry.frames, 'RMS dBFS': entry.rmsDbfs.toFixed(3),
  'sample peak dBFS': entry.samplePeakDbfs.toFixed(3), 'clipped samples': entry.clippedSamples})));
console.log('PASS: exact duration/format, exact PCM stem sum, zero endpoints, continuous bed, 11 accents, -4 dB reading duck.');
