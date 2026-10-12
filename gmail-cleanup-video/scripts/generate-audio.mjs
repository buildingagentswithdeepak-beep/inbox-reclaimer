import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {existsSync, mkdirSync, readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 18;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const SEED = 0x5245434c;
const TAU = Math.PI * 2;
const BEAT = 60 / 100;
const output = fileURLToPath(new URL('../public/audio/', import.meta.url));
const publicDir = fileURLToPath(new URL('../public/', import.meta.url));
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(existsSync(publicDir) && statSync(publicDir).isDirectory(), 'Project public/ must exist');

let state = SEED;
function noise() {
  state ^= state << 13;
  state ^= state >>> 17;
  state ^= state << 5;
  return (state >>> 0) / 2147483648 - 1;
}
const music = new Float64Array(FRAMES * 2);
const sfx = new Float64Array(FRAMES * 2);
const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);
const smooth = (x) => {
  const v = Math.max(0, Math.min(1, x));
  return v * v * (3 - 2 * v);
};
const envelope = (t, duration, attack, release) =>
  smooth(t / attack) * smooth((duration - t) / release);

function voice(track, start, duration, amplitude, pan, sample) {
  const first = Math.round(start * RATE);
  const length = Math.round(duration * RATE);
  const left = Math.cos((pan + 1) * Math.PI / 4) * amplitude;
  const right = Math.sin((pan + 1) * Math.PI / 4) * amplitude;
  for (let j = 0; j < length && first + j < FRAMES; j++) {
    if (first + j < 0) continue;
    const value = sample(j / RATE, j);
    assert(Number.isFinite(value), 'Non-finite oscillator sample');
    track[(first + j) * 2] += value * left;
    track[(first + j) * 2 + 1] += value * right;
  }
}

function pad(start, duration, notes, amplitude, open = false) {
  notes.forEach((note, index) => {
    const frequency = hz(note);
    const phase = (index + 1) * 0.79;
    const pan = (index / (notes.length - 1) - 0.5) * (open ? 1.2 : 0.65);
    voice(music, start, duration, amplitude / notes.length, pan, (t) => {
      const fundamental = Math.sin(TAU * frequency * t + phase);
      const detuned = Math.sin(TAU * frequency * 1.0015 * t + phase);
      const harmonics = 0.15 * Math.sin(TAU * frequency * 2 * t + phase)
        + 0.035 * Math.sin(TAU * frequency * 3 * t);
      return envelope(t, duration, 0.48, 0.6)
        * (0.64 * fundamental + 0.36 * detuned + harmonics);
    });
  });
}

function pluck(start, note, amplitude, pan, duration = 0.8) {
  const frequency = hz(note);
  const synth = (t) => envelope(t, duration, 0.012, 0.13)
    * Math.exp(-t * 5.3)
    * (Math.sin(TAU * frequency * t)
      + 0.22 * Math.exp(-t * 7) * Math.sin(TAU * frequency * 2 * t)
      + 0.055 * Math.exp(-t * 12) * Math.sin(TAU * frequency * 3 * t));
  voice(music, start, duration, amplitude, pan, synth);
  voice(music, start + BEAT * 0.75, duration, amplitude * 0.14, -pan, synth);
  voice(music, start + BEAT * 1.5, duration, amplitude * 0.045, pan, synth);
}

function bass(start, note, amplitude, duration = 0.85) {
  const frequency = hz(note);
  voice(music, start, duration, amplitude, 0, (t) =>
    envelope(t, duration, 0.04, 0.24) * Math.exp(-t * 1.7)
    * (Math.sin(TAU * frequency * t) + 0.14 * Math.sin(TAU * frequency * 2 * t)));
}

function percussion(start, strong, amplitude) {
  if (strong) {
    voice(music, start, 0.23, amplitude, 0, (t) =>
      envelope(t, 0.23, 0.009, 0.06) * Math.exp(-t * 20)
      * Math.sin(TAU * (49 * t + 24 * 0.025 * (1 - Math.exp(-t / 0.025)))));
  } else {
    let low = 0;
    let darker = 0;
    voice(music, start, 0.11, amplitude * 0.38, -0.2, (t) => {
      low += 0.16 * (noise() - low);
      darker += 0.025 * (low - darker);
      return (low - darker) * envelope(t, 0.11, 0.007, 0.025) * Math.exp(-t * 35);
    });
  }
}

// E minor/add9 tension resolves to spacious G6/9 and Cmaj9 voicings.
pad(0, 4, [52, 59, 66, 67], 0.53);
pad(1.8, 2.2, [54, 59, 64], 0.13);
[[0.3, 71], [1.2, 66], [2.1, 67], [2.7, 71], [3.3, 66]].forEach(([t, n], i) =>
  pluck(t, n, 0.085 + i * 0.005, i % 2 ? 0.23 : -0.23));
[0, 1.2, 2.4, 3.6].forEach((t) => bass(t, 40, 0.13));
for (let beat = 0; beat < 7; beat++) {
  percussion(beat * BEAT, beat % 2 === 0, 0.05 + beat * 0.003);
  percussion(beat * BEAT + BEAT / 2, false, 0.034);
}
pad(12, 3.1, [55, 62, 64, 69, 71], 0.59, true);
pad(14.4, 3.6, [48, 55, 62, 64, 67], 0.57, true);
[[12.3, 71], [13.2, 69], [13.8, 67], [14.7, 64], [15.6, 67], [16.2, 69], [17.1, 67]]
  .forEach(([t, n], i) => pluck(t, n, 0.10, i % 2 ? 0.32 : -0.32, 1));
[12, 13.2, 14.4, 15.6, 16.8].forEach((t, i) => bass(t, i < 2 ? 43 : 36, 0.14, 1.1));
for (let beat = 0; beat < 9; beat++) {
  percussion(12 + beat * BEAT, beat % 2 === 0, 0.055);
  percussion(12 + beat * BEAT + BEAT / 2, false, 0.027);
}

const pings = [0.35, 1.1, 1.8, 2.35, 2.85, 3.2, 3.5, 3.75];
pings.forEach((start, i) => {
  const frequency = hz([83, 86, 83, 88, 86, 83, 88, 86][i]);
  const duration = Math.min(0.46, 4 - start);
  voice(sfx, start, duration, 0.025 + i * 0.003, i % 2 ? 0.3 : -0.3, (t) =>
    envelope(t, duration, 0.007, 0.07) * Math.exp(-t * 10)
    * (Math.sin(TAU * frequency * t) + 0.13 * Math.sin(TAU * frequency * 2.003 * t)));
});
// A soft low interval, not an alarm or an upgrade/click sound.
voice(sfx, 4, 0.46, 0.060, 0, (t) => envelope(t, 0.46, 0.024, 0.17)
  * Math.exp(-t * 5) * (Math.sin(TAU * 220 * t) + 0.4 * Math.sin(TAU * 261.63 * t)));

function whoosh(start, duration, amplitude, direction) {
  let low = 0;
  let bottom = 0;
  voice(sfx, start, duration, amplitude, direction * 0.16, (t) => {
    const progress = t / duration;
    const cutoff = 480 + 1500 * (direction > 0 ? progress : 1 - progress);
    const alpha = 1 - Math.exp(-TAU * cutoff / RATE);
    low += alpha * (noise() - low);
    bottom += 0.024 * (low - bottom);
    return (low - bottom) * Math.sin(Math.PI * progress) ** 2;
  });
}
whoosh(10.45, 0.64, 0.065, -1);
whoosh(12, 0.52, 0.07, 1);
[[12.8, 76], [14, 79], [15.2, 74]].forEach(([start, note]) => {
  voice(sfx, start, 0.43, 0.037, 0.1, (t) => envelope(t, 0.43, 0.014, 0.13)
    * Math.exp(-t * 8) * (Math.sin(TAU * hz(note) * t)
      + 0.18 * Math.sin(TAU * hz(note + 7) * t)));
});
whoosh(16.8, 0.68, 0.055, -1);

// Gate after all tails/delays. No residual pad, reverb, or dither in the gap.
for (let frame = 0; frame < FRAMES; frame++) {
  const t = frame / RATE;
  const finalFade = smooth((FRAMES - 1 - frame) / (RATE * 0.45));
  const musicGate = t < 4
    ? smooth(t / 0.08) * smooth((4 - t) / 0.075) * (0.74 + 0.26 * t / 4)
    : t < 12 ? 0 : smooth((t - 12) / 0.16);
  for (let channel = 0; channel < 2; channel++) {
    music[frame * 2 + channel] *= musicGate * finalFade;
    sfx[frame * 2 + channel] *= finalFade;
  }
}

function measure(samples, start = 0, end = SECONDS, scale = 1) {
  let peak = 0;
  let energy = 0;
  let sum = 0;
  const first = Math.round(start * RATE) * 2;
  const last = Math.round(end * RATE) * 2;
  for (let i = first; i < last; i++) {
    const value = samples[i] / scale;
    peak = Math.max(peak, Math.abs(value));
    energy += value * value;
    sum += value;
  }
  const rms = Math.sqrt(energy / (last - first));
  const db = (value) => value === 0 ? null : Number((20 * Math.log10(value)).toFixed(3));
  return {samplePeak: peak, samplePeakDbfs: db(peak), rms, rmsDbfs: db(rms), dcOffset: sum / (last - first)};
}
const rawMix = Float64Array.from(music, (value, i) => value + sfx[i]);
const raw = measure(rawMix);
const gain = Math.min(10 ** (-23 / 20) / raw.rms, 10 ** (-6.2 / 20) / raw.samplePeak);
const pcmMusic = Int32Array.from(music, (sample) => Math.round(sample * gain * MAX));
const pcmSfx = Int32Array.from(sfx, (sample) => Math.round(sample * gain * MAX));
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
    assert(Math.abs(sample) <= MAX, 'Clipping detected');
    buffer.writeIntLE(sample, 44 + i * 3, 3);
  });
  return buffer;
}

const stats = {
  seed: `0x${SEED.toString(16)}`,
  sampleRate: RATE,
  channels: 2,
  bitsPerSample: 24,
  durationSeconds: SECONDS,
  frames: FRAMES,
  bpm: 100,
  commonGain: gain,
  measurement: 'Decoded PCM sample peak and unweighted RMS across both channels; full-scale sine RMS is -3.01 dBFS. Not LUFS or true peak. null dBFS means digital silence.',
  files: {},
};
const assets = new Map();
for (const [name, pcm] of [['music.wav', pcmMusic], ['sfx.wav', pcmSfx], ['mix-preview.wav', pcmMix]]) {
  const buffer = wav(pcm);
  assert.equal(buffer.length, 5184044);
  // Read back the encoded samples so reported statistics include quantization.
  const decoded = Int32Array.from({length: FRAMES * 2}, (_, i) => buffer.readIntLE(44 + i * 3, 3));
  assert.deepEqual(decoded, pcm);
  assert.equal(decoded[0], 0);
  assert.equal(decoded[1], 0);
  assert.equal(decoded.at(-1), 0);
  assert.equal(decoded.at(-2), 0);
  stats.files[name] = {
    ...measure(decoded, 0, 18, MAX),
    sections: {
      opening0to4: measure(decoded, 0, 4, MAX),
      middle4to12: measure(decoded, 4, 12, MAX),
      return12to18: measure(decoded, 12, 18, MAX),
    },
    sha256: createHash('sha256').update(buffer).digest('hex'),
  };
  assets.set(name, buffer);
}
assert.equal(stats.files['music.wav'].sections.middle4to12.samplePeak, 0, 'Music gap must be exact silence');
assert(stats.files['mix-preview.wav'].samplePeakDbfs <= -6, 'Mix sample peak exceeds -6 dBFS');
assert(stats.files['mix-preview.wav'].rmsDbfs >= -24 && stats.files['mix-preview.wav'].rmsDbfs <= -20,
  'Full-length mix RMS outside narration-bed target');
assets.set('stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
if (!verify) mkdirSync(output, {recursive: true});
for (const [name, buffer] of assets) {
  const path = fileURLToPath(new URL(`../public/audio/${name}`, import.meta.url));
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} differs from deterministic synthesis`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical files' : 'Generated audio'}: ${output}`);
console.log('48000 Hz | stereo | 24-bit PCM | 864000 frames | exactly 18 seconds');
console.table(Object.entries(stats.files).map(([file, entry]) => ({
  file,
  'sample peak dBFS': entry.samplePeakDbfs,
  'full RMS dBFS': entry.rmsDbfs,
  '0-4 RMS dBFS': entry.sections.opening0to4.rmsDbfs,
  '4-12 RMS dBFS': entry.sections.middle4to12.rmsDbfs ?? '-Infinity',
  '12-18 RMS dBFS': entry.sections.return12to18.rmsDbfs,
})));
console.log('PASS: exact music silence [4, 12), zero endpoints, no clipping, mix peak <= -6 dBFS.');
