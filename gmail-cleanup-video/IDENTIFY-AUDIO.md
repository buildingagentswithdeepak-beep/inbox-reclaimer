# Identify Audio

Original deterministic instrumental accompaniment for **2. IDENTIFY - Candidate, not a verdict.** Local oscillator and seeded-noise synthesis only; no samples, downloads, vocals, success stings, alarm tones, or delete sounds. Warm low-register C6/9 voicing without a third, modest stereo width, and four softly attacked low pulses. No melody, resolving cadence, or closing hit.

## Assets

Paths are relative to `C:\Users\v-deegarg\inbox-reclaimer\gmail-cleanup-video`.

| Asset | Purpose | RMS dBFS | Sample peak dBFS |
| --- | --- | ---: | ---: |
| `public/audio/identify-music.wav` | Warm pads and sparse low pulse | -25.001 | -13.632 |
| `public/audio/identify-sfx.wav` | Six soft unpitched filtered-noise accents | -57.645 | -33.669 |
| `public/audio/identify-mix.wav` | Exact integer sum of both stems | -25.000 | -13.514 |

All WAVs: **10.000 seconds, 480,000 stereo frames, 48,000 Hz, signed 24-bit little-endian PCM**, 2,880,044 bytes each. The first and last samples are exactly zero in both channels. Zero clipped samples; all stems and the mix remain below -6 dBFS sample peak.

Use the mix alone, or both stems at unity gain, not all three together. Stems are quantized before integer summation, with no post-sum normalization or limiter, so their decoded PCM sum equals the mix exactly.

`public/audio/identify-stats.json` contains full-precision decoded levels, endpoints, section measurements, cue levels, SHA-256 hashes, seed, normalization gain, and validation results. Levels are unweighted stereo sample RMS and sample peak, **not LUFS or true peak**. Full scale is 8,388,607; JSON `null` denotes a silent dB measurement. SFX full-file RMS includes the silent intervals.

## Timing

| Time (seconds) | Treatment |
| --- | --- |
| 0-0.2 | Smooth fade-in |
| 0.6, 1.5, 2.5, 4, 6.5, 7.3 | Six subdued unpitched accents, with 30 ms soft attacks |
| 0.7-1 | Music ramps into the reading duck |
| 1-6.5 | Music attenuated by exactly 3 dB relative to the identical unducked bed |
| 6.5-7.1 | Smooth music recovery, not a success reveal |
| 0.9, 3.3, 5.7, 8.1 | Sparse rounded low-pulse onsets |
| 9.5-10 | Final 0.5-second smooth fade to exact zero |

Cue timestamps are synthesis onsets, not transient peaks. SFX stay independently quiet and are not ducked; cue peaks range from -35.386 to -33.669 dBFS. There are no SFX outside the six scheduled windows. The final music pulse ends at 9.15 seconds, leaving a quiet pad-only tail.

Measured reading attenuation is -3.000 dB, comparing pre-quantization energy with the identical faded bed without ducking. Decoded mix RMS is -25.594 dBFS during 1-4 seconds and -26.204 dBFS during 4-6.5 seconds. The quietest tested interior 100 ms music window is -26.611 dBFS, confirming continuous accompaniment.

## Generate And Verify

From the project directory, verify the existing parent before generation:

```powershell
if (-not (Test-Path -LiteralPath "public/audio" -PathType Container)) { throw 'Audio output parent missing' }
node scripts/generate-identify-audio.mjs
node scripts/generate-identify-audio.mjs --verify
```

Generation writes only the three identify WAVs and `public/audio/identify-stats.json`. It requires no synthesis dependencies and checks that the output parent already exists. Source: `scripts/generate-identify-audio.mjs`. The analyze and stack generators were read for conventions but not modified; no package or video files were edited.

`--verify` is read-only: it regenerates in memory, compares every WAV and JSON byte, and decodes the on-disk WAVs. It validates headers, exact frame count and duration, all 960,000 interleaved sample sums, zero endpoints, clipping and peak ceilings, cue presence, SFX silence outside cues, reading attenuation, bed continuity, and mix RMS within 0.01 dB of -25 dBFS. Seed: `0x49444e31`. The same Node runtime/platform is the bit-identical reference; cross-engine transcendental math is not guaranteed bit-identical.

## Verification Results

- Generation and subsequent `--verify` passed.
- Exact decoded stem-sum residual: 0 PCM units across all 960,000 interleaved samples.
- All six scheduled accents present; no SFX outside their windows.
- First and last stereo frames are `[0, 0]` for every file.
- No clipping; mix sample peak is -13.514 dBFS, 7.514 dB below the -6 dBFS ceiling.
- Independent bundled `node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe` inspection confirmed `pcm_s24le`, 48,000 Hz, 2 channels, 24-bit samples, 480,000 frames, and 10.000000 seconds for all three WAVs.
- No subjective listening review or video render was performed.
