import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 24;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = Math.PI * 2;
const BEAT = 60 / 100;
const SEED = 0x434c5554;
const ARRIVALS = Array.from({length: 24}, (_, i) => 3 + 16.8 * (1 - 0.89 ** i) / (1 - 0.89 ** 23));
const output = new URL('../public/audio/', import.meta.url);
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(statSync(output).isDirectory(), 'Project public/audio/ must already exist');

const music = new Float64Array(FRAMES * 2);
const activity = new Float64Array(FRAMES * 2);
const percussion = new Float64Array(FRAMES * 2);
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

// Original C-major-family voicings; overlapping common tones avoid hard chord cuts.
const chords = [
  [48, 55, 59, 62, 64], [45, 52, 55, 59, 60], [41, 48, 52, 55, 57],
  [43, 50, 55, 57, 62], [48, 55, 57, 62, 64],
];
chords.forEach((notes, chord) => {
  const start = chord * 4.8 - 1.2;
  const duration = chord === 4 ? 7.5 : 6.8;
  notes.forEach((note, index) => {
    const f = hz(note);
    const phase = 0.47 * (index + 1);
    voice(music, start, duration, 0.085, (index - 2) * 0.19, (t) =>
      envelope(t, duration, 1.25, 0.9) * (
        0.82 * Math.sin(TAU * f * t + phase)
        + 0.18 * Math.sin(TAU * f * 1.0007 * t + phase)
        + 0.055 * Math.sin(TAU * f * 2 * t + phase)));
  });
});

// Each layer enters gently at 100 BPM; the final hold retains only the pad.
for (let beat = 0; beat * BEAT < 19.8; beat++) {
  const start = beat * BEAT;
  const chord = chords[Math.min(4, Math.floor(start / 4.8))];
  if (start >= 2.4 && beat % 2 === 0) {
    const f = hz(chord[0] - 12);
    voice(activity, start, 1.7, 0.048 * smooth((start - 2.4) / 4.8), 0, (t) =>
      envelope(t, 1.7, 0.07, 0.5) * Math.exp(-t * 1.8)
      * (Math.sin(TAU * f * t) + 0.08 * Math.sin(TAU * f * 2 * t)));
  }
  if (start >= 6 && beat % 2 === 0) {
    const note = chord[[2, 4, 3, 1][Math.floor(beat / 2) % 4]] + 12;
    const f = hz(note);
    voice(activity, start, 1.4, 0.032 * smooth((start - 6) / 4.8), beat % 4 ? 0.2 : -0.2, (t) =>
      envelope(t, 1.4, 0.025, 0.3) * Math.exp(-t * 4)
      * (Math.sin(TAU * f * t) + 0.09 * Math.exp(-t * 4) * Math.sin(TAU * f * 2 * t)));
  }
  if (start >= 4.8 && beat % 2 === 0) {
    voice(percussion, start, 0.25, 0.024 * smooth((start - 4.8) / 6), 0, (t) =>
      envelope(t, 0.25, 0.014, 0.09) * Math.exp(-t * 18)
      * Math.sin(TAU * (54 * t + 0.22 * (1 - Math.exp(-t / 0.025)))));
  }
  if (start >= 10.2 && beat % 2 === 1) {
    let low = 0;
    voice(percussion, start, 0.19, 0.024 * smooth((start - 10.2) / 5.4), -0.15, (t) => {
      low += 0.055 * (noise() - low);
      return low * envelope(t, 0.19, 0.025, 0.1) * Math.exp(-t * 9);
    });
  }
  if (start >= 14.4 && start + BEAT / 2 < 19.8) {
    let low = 0;
    voice(percussion, start + BEAT / 2, 0.13, 0.013 * smooth((start - 14.4) / 5.4), 0.18, (t) => {
      low += 0.13 * (noise() - low);
      return low * envelope(t, 0.13, 0.015, 0.07) * Math.exp(-t * 14);
    });
  }
}

// Gap-adaptive duration and gain keep the geometric acceleration soft, not urgent.
const firstGap = ARRIVALS[1] - ARRIVALS[0];
const accents = ARRIVALS.map((start, index) => {
  const gap = index < 23 ? ARRIVALS[index + 1] - start : start - ARRIVALS[index - 1];
  const duration = Math.min(0.48, gap * 1.65);
  const amplitude = 0.075 * Math.sqrt(gap / firstGap);
  const f = hz([76, 74, 71, 74][index % 4]);
  const pan = index % 2 ? 0.12 : -0.12;
  voice(sfx, start, duration, amplitude, pan, (t) =>
    envelope(t, duration, 0.012, Math.min(0.12, duration * 0.45)) * Math.exp(-t * 10)
    * (Math.sin(TAU * f * t) + 0.045 * Math.exp(-t * 12) * Math.sin(TAU * f * 2 * t)));
  return {
    index, timeSeconds: start, onsetFrame: Math.round(start * RATE),
    durationSeconds: duration, durationFrames: Math.round(duration * RATE),
    amplitude, relativeGainDb: db(amplitude / 0.075), midiNote: [76, 74, 71, 74][index % 4],
  };
});
assert.equal(ARRIVALS[0], 3);
assert(Math.abs(ARRIVALS.at(-1) - 19.8) < 1e-12);
const maxPingPolyphony = Math.max(...accents.map((event) => accents.filter((other) =>
  other.onsetFrame <= event.onsetFrame && other.onsetFrame + other.durationFrames > event.onsetFrame).length));
assert(maxPingPolyphony <= 2, 'Too many overlapping notifications');
for (let i = 1; i < accents.length; i++) {
  assert(accents[i].amplitude <= accents[i - 1].amplitude, 'Ping gain must not increase');
  assert(Math.abs(accents[i].onsetFrame / RATE - ARRIVALS[i]) <= 0.5 / RATE, 'Arrival sync error');
}

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

for (let frame = 0; frame < FRAMES; frame++) {
  const t = frame / RATE;
  const fade = smooth(t / 0.3) * smooth((FRAMES - 1 - frame) / (RATE * 0.5));
  const settle = 1 - smooth((t - 19.8) / 0.7);
  const padGain = (0.86 + 0.14 * smooth(t / 19.8)) * (0.82 + 0.18 * settle);
  for (let channel = 0; channel < 2; channel++) {
    const i = frame * 2 + channel;
    percussion[i] *= 1 - smooth((t - 19.65) / 0.15);
    activity[i] *= settle;
    music[i] = (music[i] * padGain + activity[i] + percussion[i]) * fade;
    sfx[i] *= fade;
  }
}
assert.equal(measure(percussion, 19.8).peak, 0, 'Percussion must stop at 19.8');
assert.equal(measure(activity, 20.5).peak, 0, 'Pitched activity must stop by the hold');
assert.equal(measure(sfx, 20.5).peak, 0, 'No notifications during the hold');
const rawMix = Float64Array.from(music, (value, i) => value + sfx[i]);
const raw = measure(rawMix);
const gain = Math.min(10 ** (-24 / 20) / raw.rms, 10 ** (-6.1 / 20) / raw.peak);
const pcmMusic = Int32Array.from(music, (sample) => Math.round(sample * gain * MAX));
const pcmSfx = Int32Array.from(sfx, (sample) => Math.round(sample * gain * MAX));
// Quantize first, then sum: the mix equals the two delivered stems sample for sample.
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
  fadeInSeconds: 0.3, fadeOutSeconds: 0.5, targetMixRmsDbfs: -24, maximumSamplePeakDbfs: -6,
  percussionStopsSeconds: 19.8, padOnlyHold: {start: 20.5, end: 24},
  arrivalFormula: '3 + 16.8 * (1 - 0.89 ** i) / (1 - 0.89 ** 23), i = 0..23',
  accents, maxPingPolyphony,
  measurement: 'Decoded PCM, unweighted stereo RMS and sample peak; not LUFS or true peak. null means digital silence.',
  files: {},
  checks: {exactDuration: true, exactStemSum: true, zeroEndpoints: true, noClipping: true,
    arrivalSyncWithinHalfSample: true, nonIncreasingPingGain: true,
    percussionSilentFrom19_8: true, padOnlyFrom20_5: true},
};
const assets = new Map();
const decodedTracks = [];
for (const [name, pcm] of [['clutter-music.wav', pcmMusic], ['clutter-sfx.wav', pcmSfx], ['clutter-mix.wav', pcmMix]]) {
  const buffer = wav(pcm);
  assert.equal(buffer.length, 6912044);
  assert.equal(buffer.readUInt32LE(4) + 8, buffer.length);
  assert.equal(buffer.readUInt16LE(20), 1);
  assert.equal(buffer.readUInt16LE(22), 2);
  assert.equal(buffer.readUInt32LE(24), RATE);
  assert.equal(buffer.readUInt32LE(28), RATE * 6);
  assert.equal(buffer.readUInt16LE(32), 6);
  assert.equal(buffer.readUInt16LE(34), 24);
  const frames = buffer.readUInt32LE(40) / buffer.readUInt16LE(32);
  assert.equal(frames, FRAMES);
  assert.equal(frames / buffer.readUInt32LE(24), SECONDS);
  const decoded = Int32Array.from({length: frames * 2}, (_, i) => buffer.readIntLE(44 + i * 3, 3));
  assert.deepEqual(decoded, pcm);
  assert([decoded[0], decoded[1], decoded.at(-2), decoded.at(-1)].every((v) => v === 0));
  const levels = measure(decoded, 0, SECONDS, MAX);
  assert.equal(levels.clippedSamples, 0);
  assert(levels.samplePeakDbfs <= -6, 'Stem or mix exceeds peak ceiling');
  stats.files[name] = {
    bytes: buffer.length, frames, durationSeconds: frames / RATE, ...levels,
    sections: Object.fromEntries([[0, 6], [6, 12], [12, 19.8], [19.8, 20.5], [20.5, 23.5], [23.5, 24]]
      .map(([start, end]) => [`${start}-${end}`, measure(decoded, start, end, MAX)])),
    sha256: createHash('sha256').update(buffer).digest('hex'),
  };
  decodedTracks.push(decoded);
  assets.set(name, buffer);
}
for (let i = 0; i < FRAMES * 2; i++) {
  assert.equal(decodedTracks[2][i], decodedTracks[0][i] + decodedTracks[1][i], 'Stem sum mismatch');
}
let minimumWindowRmsDbfs = Infinity;
for (let tenth = 3; tenth < 235; tenth++) {
  const rms = measure(decodedTracks[0], tenth / 10, (tenth + 1) / 10, MAX).rms;
  assert(rms > 10 ** (-45 / 20), 'Interior music window is too quiet or silent');
  minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, db(rms));
}
stats.checks.continuity = {windowSeconds: 0.1, start: 0.3, end: 23.5, minimumWindowRmsDbfs};
assert.equal(measure(decodedTracks[1], 20.5, 24, MAX).peak, 0);
assert(Math.abs(stats.files['clutter-mix.wav'].rmsDbfs + 24) < 0.1, 'Mix RMS outside -24 +/- 0.1 dBFS');
assets.set('clutter-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} is not byte-identical`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated clutter audio'}: ${fileURLToPath(output)}`);
console.table(Object.entries(stats.files).map(([file, entry]) => ({
  file, seconds: entry.durationSeconds, frames: entry.frames,
  'RMS dBFS': entry.rmsDbfs.toFixed(3), 'peak dBFS': entry.samplePeakDbfs.toFixed(3),
  'clipped samples': entry.clippedSamples,
})));
console.log(`PASS: exact stem sum, zero endpoints, continuous bed, 24 synchronized accents, max ping polyphony ${maxPingPolyphony}, pad-only hold.`);
