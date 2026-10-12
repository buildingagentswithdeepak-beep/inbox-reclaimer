import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 44;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = 2 * Math.PI;
const BPM = 84;
const FADE_IN = 0.4;
const FADE_OUT = 0.8;
const output = new URL('../public/audio/', import.meta.url);
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(statSync(output).isDirectory(), 'public/audio must already exist');
const clips = [['judgment', 30], ['comparison', 17], ['architecture', 28], ['code', 44], ['endcard', 12]];
const smooth = (x) => {
  const v = Math.max(0, Math.min(1, x));
  return v * v * (3 - 2 * v);
};
const fadeOut = (frame, frames) => 1 - smooth((frame - (frames - FADE_OUT * RATE)) / (FADE_OUT * RATE - 1));
const hz = (note) => 440 * 2 ** ((note - 69) / 12);
const db = (value) => value === 0 ? null : 20 * Math.log10(value);
const music = new Float64Array(FRAMES * 2);

function voice(start, duration, amplitude, pan, sample) {
  const first = Math.round(start * RATE);
  const count = Math.round(duration * RATE);
  const left = amplitude * Math.cos((pan + 1) * Math.PI / 4);
  const right = amplitude * Math.sin((pan + 1) * Math.PI / 4);
  for (let j = 0; j < count && first + j < FRAMES; j++) {
    const value = sample(j / RATE);
    assert(Number.isFinite(value), 'Non-finite synthesis sample');
    music[(first + j) * 2] += value * left;
    music[(first + j) * 2 + 1] += value * right;
  }
}

// Open D-A-E-B harmony stays neutral across cuts, without a closing cadence.
const padNotes = [50, 57, 64, 71];
padNotes.forEach((note, index) => {
  const frequency = hz(note);
  const phase = 0.73 + index * 1.19;
  voice(0, SECONDS, [0.085, 0.056, 0.032, 0.018][index], [-0.3, 0.28, -0.18, 0.4][index], (t) =>
    (0.94 + 0.06 * Math.cos(TAU * t / 16 + phase))
    * (Math.sin(TAU * frequency * t + phase)
      + 0.09 * Math.sin(TAU * frequency * 1.00017 * t + phase)
      + 0.025 * Math.sin(TAU * frequency * 2 * t + phase)));
});
voice(0, SECONDS, 0.052, 0, (t) => {
  const pulse = (0.5 - 0.5 * Math.cos(TAU * BPM / 60 * t)) ** 2;
  return (0.7 + 0.3 * pulse) * Math.sin(TAU * hz(38) * t);
});
// Soft, sparse pitched notes are part of the instrumental, not action cues.
const motif = [69, 64, 71, 66, 64, 69, 66, 71];
for (let step = 0; 0.6 + step * 2 * 60 / BPM < SECONDS; step++) {
  const frequency = hz(motif[step % motif.length]);
  const duration = 2.2;
  voice(0.6 + step * 2 * 60 / BPM, duration, 0.014, step % 2 ? 0.32 : -0.32, (t) =>
    smooth(t / 0.07) * smooth((duration - t) / 0.65) * Math.exp(-t * 2.2)
    * (Math.sin(TAU * frequency * t) + 0.06 * Math.sin(TAU * frequency * 2 * t)));
}
for (let frame = 0; frame < FRAMES; frame++) {
  const fade = smooth(frame / (FADE_IN * RATE)) * fadeOut(frame, FRAMES);
  music[frame * 2] *= fade;
  music[frame * 2 + 1] *= fade;
}

function measure(samples, scale = 1, first = 0, last = samples.length) {
  let energy = 0;
  let peak = 0;
  let sum = 0;
  let clippedSamples = 0;
  for (let i = first; i < last; i++) {
    const value = samples[i] / scale;
    assert(Number.isFinite(value), 'Non-finite PCM measurement');
    energy += value * value;
    sum += value;
    peak = Math.max(peak, Math.abs(value));
    if (Math.abs(value) >= 1) clippedSamples++;
  }
  const rms = Math.sqrt(energy / (last - first));
  return {rmsDbfs: db(rms), samplePeakDbfs: db(peak), rms, peak, dcOffset: sum / (last - first), clippedSamples};
}

const gain = 10 ** (-27 / 20) / measure(music).rms;
const bed = Int32Array.from(music, (value) => Math.round(value * gain * MAX));
const tracks = new Map([['continuation-bed.wav', bed]]);
for (const [name, seconds] of clips) {
  const frames = seconds * RATE;
  // Inherit the bed's opening fade. The 44s code mix also inherits its tail.
  const mix = Int32Array.from(bed.subarray(0, frames * 2), (value, i) =>
    seconds === SECONDS ? value : Math.round(value * fadeOut(Math.floor(i / 2), frames)));
  tracks.set(`continuation-${name}-mix.wav`, mix);
}

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
  samples.forEach((value, i) => {
    assert(Number.isInteger(value) && Math.abs(value) < MAX, 'Invalid or clipped PCM sample');
    buffer.writeIntLE(value, 44 + i * 3, 3);
  });
  return buffer;
}

const stats = {
  title: 'Continuation - restrained enterprise procedural instrumental',
  encoding: 'RIFF WAVE PCM signed 24-bit little-endian', sampleRate: RATE, channels: 2, bitsPerSample: 24,
  synthesis: 'Original fixed-phase local oscillators only; no recordings, downloads, packages, narration, vocals, percussion, or SFX.',
  padMidiNotes: padNotes, pulseMidiNote: 38, pulseBpm: BPM, motifMidiNotes: motif, commonGain: gain,
  bedDurationSeconds: SECONDS, targetBedRmsDbfs: -27, maximumSamplePeakDbfs: -10,
  fadeInSeconds: FADE_IN, fadeOutSeconds: FADE_OUT, fadeCurve: 'Smoothstep; first and last stereo frames exactly zero.',
  mixDerivation: 'Each mix starts at bed frame zero, inherits the opening fade, and applies only its own tail fade to quantized bed PCM. No per-mix normalization. Code is byte-identical to bed; no optional duck.',
  playback: 'Use exactly one scene mix at unity gain; fades are baked in. Do not layer the bed or another mix.',
  measurement: 'Decoded PCM unweighted stereo sample RMS and sample peak, not LUFS or true peak. Full scale = 8388607; null means silence.',
  repeatability: '--verify is read-only: regenerate in memory, byte-compare all WAVs and this report, decode disk PCM, and check bed derivation. Same Node runtime/platform is the bit-identical reference.',
  files: {}, checks: {},
};
const assets = new Map();
let decodedBed;
for (const [name, pcm] of tracks) {
  const expected = wav(pcm);
  const buffer = verify ? readFileSync(new URL(name, output)) : expected;
  assert(buffer.equals(expected), `${name}: WAV bytes differ from deterministic regeneration`);
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
  assert.equal(buffer.readUInt32LE(40), pcm.length * 3);
  assert.equal(buffer.length, 44 + pcm.length * 3);
  const frames = buffer.readUInt32LE(40) / 6;
  const seconds = frames / RATE;
  assert.equal(seconds, name === 'continuation-bed.wav' ? SECONDS
    : clips.find(([clip]) => name === `continuation-${clip}-mix.wav`)[1]);
  const decoded = Int32Array.from({length: frames * 2}, (_, i) => buffer.readIntLE(44 + i * 3, 3));
  if (name === 'continuation-bed.wav') decodedBed = decoded;
  else {
    for (let i = 0; i < decoded.length; i++) {
      const expectedSample = seconds === SECONDS ? decodedBed[i]
        : Math.round(decodedBed[i] * fadeOut(Math.floor(i / 2), frames));
      assert.equal(decoded[i] - expectedSample, 0, `${name}: shared-bed derivation mismatch`);
    }
  }
  const endpoints = {first: [decoded[0], decoded[1]], last: [decoded.at(-2), decoded.at(-1)]};
  assert([...endpoints.first, ...endpoints.last].every((value) => value === 0), `${name}: nonzero endpoint`);
  const levels = measure(decoded, MAX);
  assert.equal(levels.clippedSamples, 0);
  assert(levels.samplePeakDbfs < -10, `${name}: peak ceiling exceeded`);
  assert(Math.abs(levels.rmsDbfs + 27) < (name === 'continuation-bed.wav' ? 0.01 : 0.5), `${name}: RMS target missed`);
  let minimumWindowRmsDbfs = Infinity;
  for (let frame = FADE_IN * RATE; frame + RATE / 10 <= frames - FADE_OUT * RATE; frame += RATE / 10) {
    const level = measure(decoded, MAX, frame * 2, (frame + RATE / 10) * 2).rmsDbfs;
    assert(level !== null && level > -40, `${name}: silent or excessively quiet interior window`);
    minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, level);
  }
  stats.files[name] = {bytes: buffer.length, frames, durationSeconds: seconds, ...levels, endpoints,
    fadeOutStartSeconds: seconds - FADE_OUT,
    continuity: {windowSeconds: 0.1, minimumWindowRmsDbfs},
    sha256: createHash('sha256').update(buffer).digest('hex')};
  assets.set(name, expected);
}
assert(assets.get('continuation-bed.wav').equals(assets.get('continuation-code-mix.wav')));
stats.checks = {exactDurationAndFormat: true, zeroEndpoints: true, noClipping: true,
  allSamplePeaksBelowMinus10: true, bedRmsWithinPoint01Db: true, mixesRmsWithinPoint5Db: true,
  exactSharedBedPcmDerivation: true, derivationResidualPcm: 0, codeIdenticalToBed: true,
  interior100msWindowsAboveMinus40: true};
assets.set('continuation-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert(readFileSync(path).equals(buffer), `${name}: bytes differ from deterministic regeneration`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated continuation audio'}: ${fileURLToPath(output)}`);
console.log('Format: 48000 Hz, stereo, signed 24-bit PCM; all first/last stereo frames [0, 0].');
console.table(Object.entries(stats.files).map(([file, entry]) => ({file, seconds: entry.durationSeconds,
  frames: entry.frames, bytes: entry.bytes, 'RMS dBFS': entry.rmsDbfs.toFixed(3),
  'sample peak dBFS': entry.samplePeakDbfs.toFixed(3), 'clipped samples': entry.clippedSamples})));
console.log('PASS: duration/format, RMS, peaks below -10 dBFS, zero endpoints, continuity, exact common-bed derivation, 0.4s/0.8s fades. No narration or SFX.');
