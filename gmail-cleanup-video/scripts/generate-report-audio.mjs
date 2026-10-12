import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync, statSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const RATE = 48000;
const SECONDS = 19;
const FRAMES = RATE * SECONDS;
const MAX = 8388607;
const TAU = Math.PI * 2;
const BEAT = 60 / 100;
const SEED = 0x52505431;
const ACCENTS = [
  [0.25, 'Reveal'], [2, 'Analyze'], [5, 'Identify'],
  [8, 'Suggest'], [11, 'Review'], [16, 'Text handoff'],
];
const output = new URL('../public/audio/', import.meta.url);
const verify = process.argv.includes('--verify');
assert(process.argv.slice(2).every((arg) => arg === '--verify'), 'Only --verify is supported');
assert(statSync(output).isDirectory(), 'Project public/audio/ must already exist');

// Reuse the intro's synthesis primitives, not its rendered audio or arrangement.
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

// A-minor suspended/common-tone harmony, without a dominant-to-tonic victory cadence.
const chords = [[45, 52, 55, 59], [48, 52, 55, 62], [41, 52, 57, 60], [43, 50, 57, 60]];
chords.forEach((notes, chord) => {
  const start = chord * 4.8 - 0.8;
  const duration = 6.6;
  notes.forEach((note, index) => {
    const f = hz(note);
    const phase = 0.51 * (index + 1);
    voice(music, start, duration, 0.1, (index - 1.5) * 0.2, (t) =>
      envelope(t, duration, 1.0, 1.0) * (
        0.8 * Math.sin(TAU * f * t + phase)
        + 0.2 * Math.sin(TAU * f * 1.0006 * t + phase)
        + 0.045 * Math.sin(TAU * f * 2 * t + phase)));
  });
});

for (let beat = 0; beat * BEAT < SECONDS; beat++) {
  const start = beat * BEAT;
  const chord = chords[Math.min(3, Math.floor(start / 4.8))];
  if (beat % 2 === 0) {
    const f = hz(chord[0] - 12);
    voice(music, start, 1.5, 0.043, 0, (t) =>
      envelope(t, 1.5, 0.065, 0.4) * Math.exp(-t * 2.1)
      * (Math.sin(TAU * f * t) + 0.07 * Math.sin(TAU * f * 2 * t)));
    voice(music, start, 0.26, 0.021, 0, (t) =>
      envelope(t, 0.26, 0.018, 0.09) * Math.exp(-t * 17)
      * Math.sin(TAU * (49 * t + 0.19 * (1 - Math.exp(-t / 0.03)))));
  } else {
    let low = 0;
    voice(music, start, 0.18, 0.018, -0.1, (t) => {
      low += 0.065 * (noise() - low);
      return low * envelope(t, 0.18, 0.025, 0.09) * Math.exp(-t * 10);
    });
  }
  // Sparse soft-key punctuation, not a foreground melody or notification ping.
  if (beat % 4 === 1) {
    const f = hz(chord[beat % 8 === 1 ? 2 : 3]);
    voice(music, start, 1.8, 0.033, beat % 8 === 1 ? -0.2 : 0.2, (t) =>
      envelope(t, 1.8, 0.045, 0.4) * Math.exp(-t * 3.2)
      * (Math.sin(TAU * f * t) + 0.06 * Math.exp(-t * 5) * Math.sin(TAU * f * 2 * t)));
  }
}

// Low, band-limited fabric gestures mark actions without UI chimes or success sounds.
const accents = ACCENTS.map(([start, label], index) => {
  const duration = index === 5 ? 0.55 : 0.4;
  let low = 0;
  let bottom = 0;
  voice(sfx, start, duration, index === 5 ? 0.18 : 0.22, index % 2 ? 0.1 : -0.1, (t) => {
    low += 0.055 * (noise() - low);
    bottom += 0.01 * (low - bottom);
    return (low - bottom) * envelope(t, duration, 0.035, 0.2) * Math.exp(-t * 4);
  });
  return {label, timeSeconds: start, onsetFrame: Math.round(start * RATE), durationSeconds: duration};
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

// Compare against the same faded signal to isolate ducking from the end fade.
const unduckedFinal = [0, 0];
const duckedFinal = [0, 0];
for (let frame = 0; frame < FRAMES; frame++) {
  const t = frame / RATE;
  const fade = smooth(t / 0.2) * (1 - smooth((frame - RATE * 18.55) / (RATE * 0.45 - 1)));
  const duck = 10 ** (-4 * smooth((t - 15.8) / 0.2) / 20);
  for (const [trackIndex, track] of [music, sfx].entries()) {
    for (let channel = 0; channel < 2; channel++) {
      const i = frame * 2 + channel;
      track[i] *= fade;
      if (frame >= 16 * RATE) unduckedFinal[trackIndex] += track[i] ** 2;
      track[i] *= duck;
      if (frame >= 16 * RATE) duckedFinal[trackIndex] += track[i] ** 2;
    }
  }
}
const measuredDuckDb = duckedFinal.map((energy, i) => db(Math.sqrt(energy / unduckedFinal[i])));
measuredDuckDb.forEach((value) => assert(Math.abs(value + 4) < 1e-9, 'Final duck must be -4 dB'));
const rawMix = Float64Array.from(music, (value, i) => value + sfx[i]);
const raw = measure(rawMix);
const gain = Math.min(10 ** (-24 / 20) / raw.rms, 10 ** (-6.2 / 20) / raw.peak);
const pcmMusic = Int32Array.from(music, (sample) => Math.round(sample * gain * MAX));
const pcmSfx = Int32Array.from(sfx, (sample) => Math.round(sample * gain * MAX));
// Sum after quantization so the delivered stems null exactly against the mix.
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
  fadeInSeconds: 0.2, fadeOutSeconds: 0.45, fadeOutStartSeconds: 18.55,
  targetMixRmsDbfs: -24, maximumSamplePeakDbfs: -6,
  duck: {start: 16, end: 19, rampInStart: 15.8, gainDb: -4,
    measuredMusicAttenuationDb: measuredDuckDb[0], measuredSfxAttenuationDb: measuredDuckDb[1],
    measurement: '16-19s energy ratio against identical faded signals without duck; before PCM quantization.'},
  accents,
  measurement: 'Decoded PCM, unweighted stereo RMS and sample peak; not LUFS or true peak. Full scale = 8388607. null means digital silence.',
  repeatability: 'Run node scripts/generate-report-audio.mjs --verify to regenerate in memory and compare all WAV and JSON bytes.',
  files: {},
  checks: {exactDuration: true, exactStemSum: true, zeroEndpoints: true, noClipping: true, finalDuck4Db: true},
};
const assets = new Map();
const decodedTracks = [];
for (const [name, pcm] of [['report-music.wav', pcmMusic], ['report-sfx.wav', pcmSfx], ['report-mix.wav', pcmMix]]) {
  const buffer = wav(pcm);
  assert.equal(buffer.length, 5472044);
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
  stats.files[name] = {
    bytes: buffer.length, frames, durationSeconds: frames / RATE, ...levels,
    sections: Object.fromEntries([[0, 16], [16, 18.55], [18.55, 19]]
      .map(([start, end]) => [`${start}-${end}`, measure(decoded, start, end, MAX)])),
    sha256: createHash('sha256').update(buffer).digest('hex'),
  };
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
accents.forEach((event) => assert(measure(decodedTracks[1], event.timeSeconds,
  event.timeSeconds + event.durationSeconds, MAX).rms > 0, 'Missing accent'));
stats.checks.sixScheduledAccentsOnly = true;
let minimumWindowRmsDbfs = Infinity;
for (let tenth = 2; tenth < 185; tenth++) {
  const rms = measure(decodedTracks[0], tenth / 10, (tenth + 1) / 10, MAX).rms;
  assert(rms > 10 ** (-45 / 20), 'Interior bed is too quiet or silent');
  minimumWindowRmsDbfs = Math.min(minimumWindowRmsDbfs, db(rms));
}
stats.checks.continuity = {windowSeconds: 0.1, start: 0.2, end: 18.5, minimumWindowRmsDbfs};
assert(Math.abs(stats.files['report-mix.wav'].rmsDbfs + 24) < 0.01, 'Mix RMS outside -24 +/- 0.01 dBFS');
assets.set('report-stats.json', Buffer.from(`${JSON.stringify(stats, null, 2)}\n`));
for (const [name, buffer] of assets) {
  const path = new URL(name, output);
  if (verify) assert.deepEqual(readFileSync(path), buffer, `${name} is not byte-identical`);
  else writeFileSync(path, buffer);
}
console.log(`${verify ? 'Verified byte-identical regeneration' : 'Generated report audio'}: ${fileURLToPath(output)}`);
console.table(Object.entries(stats.files).map(([file, entry]) => ({
  file, seconds: entry.durationSeconds, frames: entry.frames,
  'RMS dBFS': entry.rmsDbfs.toFixed(3), 'sample peak dBFS': entry.samplePeakDbfs.toFixed(3),
  'clipped samples': entry.clippedSamples,
})));
console.log('PASS: exact duration/format, exact PCM stem sum, zero endpoints, continuous bed, six accents, -4 dB final duck.');
