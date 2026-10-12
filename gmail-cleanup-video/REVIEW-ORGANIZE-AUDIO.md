# Review And Organize Audio

Original deterministic 30-second ambient instrumental, synthesized locally using only Node built-ins. A warm open D-A-E bed (MIDI 50, 57, 64) supports a rounded low D pulse (MIDI 38) at 90 BPM. The pulse uses continuous amplitude modulation rather than percussion. Static harmony and a quiet fade provide a neutral ending without an approval cadence, fanfare, riser, or closing hit. No external recordings, voiceover, vocals, or invented click sounds.

## Assets And Measurements

Paths are relative to `C:\Users\v-deegarg\inbox-reclaimer\gmail-cleanup-video`.

| Asset | RMS dBFS | Sample peak dBFS | Clipped samples |
| --- | ---: | ---: | ---: |
| `public/audio/review-organize-music.wav` | -25.000 | -14.399 | 0 |
| `public/audio/review-organize-sfx.wav` | -66.672 | -37.862 | 0 |
| `public/audio/review-organize-mix.wav` | -25.000 | -14.399 | 0 |

Each WAV is exactly **30.000 seconds, 1,440,000 stereo frames, 48,000 Hz, signed 24-bit little-endian PCM**, with a 44-byte RIFF/WAVE header and 8,640,044 total bytes. First and last stereo frames are exactly `[0, 0]`. The mix has 8.399 dB of sample-peak headroom below the requested -6 dBFS ceiling. Both stems also meet that ceiling.

These are decoded PCM, unweighted stereo sample RMS and sample peak measurements, **not LUFS or true peak**. Full scale is 8,388,607. JSON `null` means silence. Full-file SFX RMS includes its silent intervals. Full-precision measurements, section levels, cue levels, WAV SHA-256 hashes, synthesis seed, common gain, and checks are in `public/audio/review-organize-stats.json`.

Use the mix alone, or both stems at unity gain, never all three together. The stems are quantized before integer summation, with no post-sum normalization or limiter. All 2,880,000 decoded interleaved mix samples exactly equal the corresponding music plus SFX samples; residual is zero PCM units. The generated mix contains only the original instrumental and designed cues, not source-footage audio.

## Timeline Contract

| Scene time | Supplied picture intent | Audio treatment |
| --- | --- | --- |
| 0-14 | Genuine native confirmation, continuous 1x | Continuous neutral bed; no action-related sound |
| 12.65 | Native click at source 60.65 seconds | No added click sound or musical accent |
| 13 | Native dismissal | No added dismissal sound or approval cue |
| 14-15 | Later run result transition | Quiet unpitched cue at 14 |
| 15-24 | Actual run output held | Quiet unpitched cue at 15; otherwise continuous bed |
| 24-30 | Later Gmail Trash check | Quiet unpitched cue at 24; no success resolution |

This is the user-supplied synchronization contract, not independent verification of the footage. No video source, timing, speed, composition, or native audio is modified by the generator.

## Envelopes And Cues

- Smoothstep fade-in: 0-0.3 seconds.
- Music duck ramps in from 0.5 to 0.8 seconds, stays exactly -3 dB from 0.8 to 13.8 seconds, and recovers smoothly through 14.3 seconds. It measures -3.000 dB by energy ratio against the identical faded, unducked bed before PCM quantization.
- Final smoothstep fade: 29.3-30 seconds, ending at exact zero on the last sample frame.
- Four seeded filtered-noise cues only, each with a soft 60 ms attack. SFX are not ducked.

| Cue onset | End | Sample peak dBFS | Purpose |
| ---: | ---: | ---: | --- |
| 0.50 | 0.82 | -40.205 | Quiet opening texture, not a UI click |
| 14.00 | 14.38 | -38.217 | Later run result transition |
| 15.00 | 15.32 | -40.347 | Actual run output held |
| 24.00 | 24.38 | -37.862 | Later Gmail Trash check |

Cue times are synthesis-window onsets, not transient peaks. Every SFX sample outside these four windows is exactly zero, including the native click and dismissal. The musical pulse is continuous, not triggered by either action. Every tested interior 100 ms music window from 0.3 to 29.3 seconds exceeds -40 dBFS RMS.

## Generate And Verify

```powershell
if (-not (Test-Path -LiteralPath "scripts" -PathType Container)) { throw 'Script parent missing' }
if (-not (Test-Path -LiteralPath "public/audio" -PathType Container)) { throw 'Audio output parent missing' }
node scripts/generate-review-organize-audio.mjs
node scripts/generate-review-organize-audio.mjs --verify
```

The generator checks that its output parent already exists and writes only the three `review-organize-` WAVs and `review-organize-stats.json`. Seed: `0x524f4131`. No packages or external services are needed.

`--verify` is read-only. It regenerates in memory, compares every WAV and JSON byte against disk, decodes the on-disk WAVs, and checks format, exact duration, endpoints, no clipping, sample peaks, exact integer stem sum, the four cue times and presence, silence outside cue windows, absence of added click/dismissal SFX, music duck, bed continuity, and mix RMS within 0.01 dB of -25 dBFS. Byte repeatability is against the same Node runtime/platform; transcendental math across other runtimes is not guaranteed bit-identical.

## Verification Results

- Output parent directories were verified before edits and generation.
- Generation and subsequent `--verify` passed, including byte identity of all four generated outputs.
- Independent bundled `node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe` inspection confirmed `pcm_s24le`, 48,000 Hz, 2 channels, 24-bit samples, 1,440,000 frames, 30.000000 seconds, and 8,640,044 bytes for all three WAVs.
- Exact PCM stem-sum residual: 0 across 2,880,000 interleaved samples.
- All WAV endpoints are exactly zero; no clipped samples; all sample peaks below -6 dBFS.
- Work is confined to the six requested review-organize files. Existing generators were read as conventions, not edited. No existing audio, source files, package configuration, or video composition was modified.
- No subjective listening review, footage validation, or video render was performed.
