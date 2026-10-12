import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 5;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = Math.PI * 2;
const BPM = 112;
const output = new URL('../public/audio/', import.meta.url);
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(statSync(output).isDirectory(), 'public/audio must already exist');
const smooth = (x) => {
  const v = Math.max(0, Math.min(1, x));
  return v * v * (3 - 2 * v);
};
const hz = (note) => 440 * 2 ** ((note - 69) / 12);
const db = (value) => value === 0 ? null : 20 * Math.log10(value);
const buffer = new Float64Array(FRAMES * 2);

function addVoice(start, duration, amplitude, pan, sample) {
  const first = Math.round(start * RATE);
  const count = Math.round(duration * RATE);
  const left = amplitude * Math.cos((pan + 1) * Math.PI / 4);
  const right = amplitude * Math.sin((pan + 1) * Math.PI / 4);
  for (let i = 0; i < count && first + i < FRAMES; i++) {
    const value = sample(i / RATE);
    buffer[(first + i) * 2] += value * left;
    buffer[(first + i) * 2 + 1] += value * right;
  }
}

// Brighter, short CTA cue: open pad, pulse bass, and quick motif.
[[50, .09, -.2], [57, .05, .22], [64, .03, -.35], [69, .02, .32]].forEach(([note, amp, pan], i) => {
  const f = hz(note);
  addVoice(0, SECONDS, amp, pan, (t) => (0.93 + 0.07 * Math.cos(TAU * t / 4 + i)) * (Math.sin(TAU * f * t + i) + 0.04 * Math.sin(TAU * f * 2 * t + i)));
});
addVoice(0, SECONDS, 0.05, 0, (t) => {
  const pulse = (0.5 - 0.5 * Math.cos(TAU * BPM / 60 * t)) ** 2;
  return (0.64 + 0.36 * pulse) * Math.sin(TAU * hz(38) * t);
});
const motif = [74, 76, 81, 79, 76, 74, 72, 76];
for (let step = 0; 0.18 + step * 60 / BPM < 4.1; step++) {
  const start = 0.18 + step * 60 / BPM;
  const f = hz(motif[step % motif.length]);
  addVoice(start, 0.44, 0.028, step % 2 ? .2 : -.2, (t) => smooth(t / .03) * smooth((.44 - t) / .16) * Math.exp(-t * 2.5) * (Math.sin(TAU * f * t) + 0.12 * Math.sin(TAU * f * 2 * t)));
}
for (let frame = 0; frame < FRAMES; frame++) {
  const fadeIn = smooth(frame / (.18 * RATE));
  const fadeOut = 1 - smooth((frame - (FRAMES - .7 * RATE)) / (.7 * RATE - 1));
  const fade = fadeIn * fadeOut;
  buffer[frame * 2] *= fade;
  buffer[frame * 2 + 1] *= fade;
}

function measure(samples, scale = 1) {
  let energy = 0;
  let peak = 0;
  let clipped = 0;
  for (let i = 0; i < samples.length; i++) {
    const value = samples[i] / scale;
    energy += value * value;
    peak = Math.max(peak, Math.abs(value));
    if (Math.abs(value) >= 1) clipped++;
  }
  const rms = Math.sqrt(energy / samples.length);
  return {rms, rmsDbfs: db(rms), samplePeakDbfs: db(peak), peak, clipped};
}

const gain = 10 ** (-24.8 / 20) / measure(buffer).rms;
const pcm = Int32Array.from(buffer, (value) => Math.round(value * gain * MAX));

function wav(samples) {
  const out = Buffer.alloc(44 + samples.length * 3);
  out.write('RIFF', 0);
  out.writeUInt32LE(out.length - 8, 4);
  out.write('WAVEfmt ', 8);
  out.writeUInt32LE(16, 16);
  out.writeUInt16LE(1, 20);
  out.writeUInt16LE(2, 22);
  out.writeUInt32LE(RATE, 24);
  out.writeUInt32LE(RATE * 6, 28);
  out.writeUInt16LE(6, 32);
  out.writeUInt16LE(24, 34);
  out.write('data', 36);
  out.writeUInt32LE(samples.length * 3, 40);
  samples.forEach((value, i) => out.writeIntLE(value, 44 + i * 3, 3));
  return out;
}

const expected = wav(pcm);
const file = new URL('endcard-short-mix.wav', output);
const statsFile = new URL('endcard-short-stats.json', output);
const stats = {
  seconds: SECONDS,
  sampleRate: RATE,
  channels: 2,
  bitsPerSample: 24,
  synthesis: 'Original short CTA cue, synthesized locally with Node built-ins only.',
  bpm: BPM,
  rmsTargetDbfs: -24.8,
  measurements: measure(pcm, MAX),
  sha256: createHash('sha256').update(expected).digest('hex'),
  endpoints: {first: [pcm[0], pcm[1]], last: [pcm.at(-2), pcm.at(-1)]},
};
const statsBuffer = Buffer.from(`${JSON.stringify(stats, null, 2)}\n`);

if (verify) {
  assert(readFileSync(file).equals(expected), 'endcard-short-mix.wav differs from deterministic regeneration');
  assert(readFileSync(statsFile).equals(statsBuffer), 'endcard-short-stats.json differs from deterministic regeneration');
} else {
  writeFileSync(file, expected);
  writeFileSync(statsFile, statsBuffer);
}
assert(stats.measurements.clipped === 0, 'Audio clips');
assert(stats.measurements.samplePeakDbfs < -9, 'Peak ceiling exceeded');
console.log(`${verify ? 'Verified' : 'Generated'} ${fileURLToPath(file)}`);
console.log(JSON.stringify(stats, null, 2));
