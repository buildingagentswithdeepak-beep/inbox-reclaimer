# Suggest Audio

Original deterministic 8-second ambient instrumental synthesized locally from oscillators and seeded filtered noise. Static D-A-E voicing (MIDI 50, 57, 64), no third, chord changes, melody, rhythmic pulses, or closing hit. No external recordings, samples, narrator, creator voice, vocals, approval stings, or success stings. Four unpitched filtered-noise accents have 30 ms attacks; the amber badge does not introduce a tonal resolution or approval cue.

## Assets And Measurements

Paths are relative to `C:\Users\v-deegarg\inbox-reclaimer\gmail-cleanup-video`.

| Asset | RMS dBFS | Sample peak dBFS | Clipped samples |
| --- | ---: | ---: | ---: |
| `public/audio/suggest-music.wav` | -25.003 | -14.690 | 0 |
| `public/audio/suggest-sfx.wav` | -58.410 | -34.176 | 0 |
| `public/audio/suggest-mix.wav` | -25.000 | -14.589 | 0 |

Every WAV is exactly **8.000 seconds, 384,000 stereo frames, 48,000 Hz, signed 24-bit little-endian PCM**, with a 44-byte RIFF/WAVE header and 2,304,044 total bytes. First and last stereo frames are exactly `[0, 0]`. Mix sample peak is 8.589 dB below the -6 dBFS ceiling; both stems also satisfy that ceiling.

Levels are decoded PCM unweighted stereo sample RMS and sample peak, not LUFS or true peak. Full scale is 8,388,607; JSON `null` indicates silence. SFX full-file RMS includes silent intervals. Full-precision measurements, section levels, cue measurements, SHA-256 hashes, synthesis seed, common gain, and validation results are in `public/audio/suggest-stats.json`.

Use the mix alone, or music and SFX at unity gain, never all three together. Each stem is quantized before summation; no limiter or normalization is applied after integer summation. All 768,000 decoded interleaved mix samples equal their corresponding stem sums exactly, with zero PCM residual.

## Timing

| Time (seconds) | Treatment |
| --- | --- |
| 0-0.2 | Smoothstep fade-in |
| 0.5-0.72 | Command accent; peak -35.789 dBFS |
| 0.7-1 | Music ramps into reading duck |
| 1-6.5 | Music held at -3 dB relative to identical unducked bed |
| 2.3-2.56 | Saved-plan accent; peak -34.176 dBFS |
| 4.5-4.74 | Local-report accent; peak -34.698 dBFS |
| 5.5-5.78 | Amber-badge accent; peak -35.573 dBFS |
| 6.5-7.1 | Smooth music recovery without an additional cue |
| 7.5-8 | Final 0.5-second smoothstep fade to exact zero |

Cue times are synthesis window onsets, not transient peaks. SFX samples outside these four windows are exactly zero. SFX are not ducked. Reading attenuation measures -3.000 dB using the pre-quantization energy ratio against the identical faded bed without ducking. Every tested interior 100 ms music window from 0.2 to 7.5 seconds exceeds -40 dBFS RMS.

## Generate And Verify

```powershell
if (-not (Test-Path -LiteralPath "public/audio" -PathType Container)) { throw 'Audio output parent missing' }
node scripts/generate-suggest-audio.mjs
node scripts/generate-suggest-audio.mjs --verify
```

The generator uses only Node built-ins and writes only the three suggest WAVs and `public/audio/suggest-stats.json`. The seed is `0x53554731`. `--verify` is read-only: it regenerates the outputs in memory, compares every WAV and JSON byte against disk, decodes each on-disk WAV, and checks format, exact duration, clipping, peaks, endpoints, integer stem sums, cue presence, SFX silence outside cues, reading duck, continuous bed, and mix RMS within 0.01 dB of -25 dBFS. Byte identity is guaranteed against the same Node runtime/platform; transcendental math across other runtimes is not guaranteed identical.

## Verification Results

- Generation and subsequent `--verify` passed.
- Independent bundled `node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe` inspection confirmed `pcm_s24le`, 48,000 Hz, 2 channels, 24-bit samples, 384,000 frames, and 8.000000 seconds for all three files.
- Exact PCM stem-sum residual: 0 across 768,000 interleaved samples.
- Zero clipped samples and exact zero endpoints in every WAV.
- All four accents present; none outside the scheduled windows.
- Existing identify conventions were read but not modified. Before/after SHA-256 checks confirmed all 42 pre-existing files matching `public/audio/*`, `scripts/*audio.mjs`, and `*AUDIO.md` were unchanged, excluding suggest files. Aggregate fingerprint of sorted absolute-path/hash pairs: `BA76B616CF253AF88A4BB458B8394735BC1EA5635C8FC436919903DE75B02F19`.
- Changes are confined to the six requested suggest files. No packages, video sources, or existing audio files were edited.
- No subjective listening review or video render was performed.
