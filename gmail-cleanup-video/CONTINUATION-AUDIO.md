# Continuation Audio

Foundation assets only. Original restrained enterprise procedural instrumental, synthesized locally with Node built-ins. One common 44-second bed serves all five scenes. No downloaded or licensed recordings, external services, packages, narration, vocals, percussion, or SFX are used. Existing generators were read for conventions, not edited.

## Sound And Shared Bed

An open D-A-E-B pad (MIDI 50, 57, 64, 71) supports a rounded low D (MIDI 38) amplitude pulse at 84 BPM. Sparse, softly attacked pitched notes add restrained movement without action-synchronized cues. Fixed oscillator phases and deterministic timing provide repeatable synthesis without randomness. The harmony stays open: no fanfare, impact, riser, or closing cadence.

The bed is normalized once to -27 dBFS RMS and quantized to 24-bit PCM. All mixes take the corresponding prefix of this exact PCM bed, starting at frame zero. There is no independent regeneration, per-mix normalization, limiter, or additional gain. Each mix inherits the bed's 0.4-second opening fade and receives its own 0.8-second ending fade. Fades use smoothstep, with exact-zero first and last stereo frames.

The optional final-five-second code duck is omitted. The 44-second code mix inherits both fades and is byte-identical to the bed, avoiding double fades. Shorter mixes exactly equal the bed until their own fade-out starts, then equal the rounded integer bed samples multiplied by that fade envelope.

## Assets And Measurements

All paths below are relative to this project. All six WAVs are **48,000 Hz, stereo, signed 24-bit little-endian PCM** with standard 44-byte RIFF/WAVE headers.

| File in `public/audio/` | Seconds | Stereo frames | Bytes | RMS dBFS | Sample peak dBFS | Fade-out starts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `continuation-bed.wav` | 44 | 2,112,000 | 12,672,044 | -27.000 | -17.396 | 43.2 s |
| `continuation-judgment-mix.wav` | 30 | 1,440,000 | 8,640,044 | -27.119 | -17.396 | 29.2 s |
| `continuation-comparison-mix.wav` | 17 | 816,000 | 4,896,044 | -27.080 | -17.396 | 16.2 s |
| `continuation-architecture-mix.wav` | 28 | 1,344,000 | 8,064,044 | -27.160 | -17.396 | 27.2 s |
| `continuation-code-mix.wav` | 44 | 2,112,000 | 12,672,044 | -27.000 | -17.396 | 43.2 s |
| `continuation-endcard-mix.wav` | 12 | 576,000 | 3,456,044 | -27.078 | -17.396 | 11.2 s |

Every file has zero clipped samples and first/last stereo frames `[0, 0]`. All sample peaks are 7.396 dB below the requested -10 dBFS ceiling. Levels are decoded-PCM unweighted stereo sample RMS and sample peak, **not LUFS or oversampled true peak**. Full scale is 8,388,607; JSON `null` denotes silence. Full-precision levels, DC offsets, continuity measurements, frame counts, endpoints, SHA-256 hashes, synthesis parameters, and checks are in `public/audio/continuation-stats.json`.

## Unity-Gain Handoff

Use the matching scene mix alone at unity gain, starting at scene time zero for its exact duration. Fades are already baked in; do not add another volume envelope, normalize the mix, loop it, or layer the bed underneath it.

For later Remotion integration, the asset reference is ready for `Audio` from `@remotion/media` with `staticFile` from `remotion`, for example:

```tsx
<Audio src={staticFile('audio/continuation-judgment-mix.wav')} volume={1} />
```

For later finalization, select the corresponding `public/audio/continuation-<scene>-mix.wav` as the replacement audio input, map only that audio stream at unity, and use the scene's exact duration. This matches the existing finalizer's replacement-audio pattern (`-map 0:v:0 -map 1:a:0`, video copy, AAC 320k). No resampling, channel conversion, mixing, or gain filter is needed before encoding. AAC re-encoding changes PCM values and packet padding, so final video duration and decoded audio still need delivery verification.

The existing `scripts/finalize.mjs` does not yet have continuation scene selectors. It was intentionally left unchanged; these files are ready inputs, not wired finalizer commands. No compositions, registrations, source footage, package configuration, or finalizer code were created or modified.

## Generate And Verify

Run from `C:\Users\v-deegarg\inbox-reclaimer\gmail-cleanup-video`:

```powershell
node scripts/generate-continuation-audio.mjs
node scripts/generate-continuation-audio.mjs --verify
```

The generator checks that `public/audio` already exists, resolves paths relative to the script, and writes only the six WAVs above and `continuation-stats.json`. It uses only `node:assert/strict`, `node:crypto`, `node:fs`, and `node:url`.

`--verify` is read-only and exits nonzero on any failure. It regenerates expected assets in memory, compares every byte of all six on-disk WAVs and the JSON report, decodes the on-disk PCM, and asserts:

- Exact RIFF/WAVE PCM format, sizes, durations, sample rate, channels, and bit depth.
- Bed RMS within 0.01 dB of -27 dBFS; each mix within 0.5 dB of -27 dBFS.
- Every sample peak strictly below -10 dBFS and no clipping.
- Exact-zero opening and closing stereo frames.
- Exact shared-bed derivation for every mix sample, including each individual fade; residual zero PCM units.
- Byte identity between the code mix and the bed.
- Every tested interior 100 ms window above -40 dBFS RMS, excluding the opening and closing fades.

Bit identity is guaranteed against the same Node runtime/platform; transcendental math on other runtimes is not guaranteed byte-identical. The report has no timestamps or mode-dependent fields.

## Verification Results

- Generation and subsequent `--verify` passed on Node v24.19.0, Windows, including byte comparison of all seven generated outputs.
- `node --check scripts/generate-continuation-audio.mjs` passed.
- Independent bundled `ffprobe.exe` inspection confirmed `pcm_s24le`, 48,000 Hz, 2 channels, 24-bit samples, time base `1/48000`, and exact durations, sample-frame counts, and file sizes for all six WAVs.
- Shared-bed derivation residual is zero. All endpoints are zero, with no clipped samples and peaks below the requested ceiling.
- Changes are confined to `scripts/generate-continuation-audio.mjs`, `public/audio/continuation-*`, and this document.
- No subjective listening review, video render, finalizer execution, or composition work was performed.
