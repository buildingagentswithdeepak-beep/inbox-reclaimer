# Analyze Audio

Original deterministic instrumental accompaniment for the read-only Gmail analysis recording. Local oscillator and seeded-noise synthesis only: no downloaded audio, vocals, notification tones, alarms, or success fanfare. Warm low-register D6/9 suspension without a third, restrained stereo width, and one soft low pulse every 2.4 seconds. No melody or closing cadence; no new events in the 14-15 second hold.

## Assets

Paths are relative to `C:\Users\v-deegarg\inbox-reclaimer\gmail-cleanup-video`.

| Asset | Purpose | RMS dBFS | Sample peak dBFS |
| --- | --- | ---: | ---: |
| `public/audio/analyze-music.wav` | Ambient bed and sparse low pulse | -25.003 | -12.828 |
| `public/audio/analyze-sfx.wav` | Seven soft filtered-noise accents | -57.465 | -31.695 |
| `public/audio/analyze-mix.wav` | Exact integer sum of both stems | -25.000 | -12.819 |

All WAVs: **15.000 seconds, 720,000 stereo frames, 48,000 Hz, signed 24-bit little-endian PCM**, 4,320,044 bytes each. First and last samples are exactly zero in both channels. Zero clipped samples; every stem and the mix remain below -6 dBFS sample peak.

Use the mix alone, or the two stems at unity gain, not all three together. No limiter or post-sum normalization changes the mix: quantization happens on each stem before integer summation.

`public/audio/analyze-stats.json` contains full-precision decoded measurements, section levels, cue levels, SHA-256 hashes, synthesis seed, gain, and validation results. Measurements are unweighted RMS across all interleaved samples and sample peak, **not LUFS or true peak**. Full scale is 8,388,607; a JSON `null` dB value denotes silence. The SFX full-file RMS includes its silent intervals.

## Timing

| Time (seconds) | Treatment |
| --- | --- |
| 0-0.6 | Intro; 0.25-second smooth fade-in, soft accent at 0.5 |
| 0.8-10.5 | Scan; quiet sustained harmony and sparse low pulse |
| 1-10.5 | Bed attenuated by exactly 3 dB relative to the same unducked signal |
| 4 | Soft unpitched accent on output cut; no extra music hit |
| 10.5-11.5 | Category transition; accent at 10.5, gentle bed recovery through 11.3 |
| 11.3, 11.7, 12.1, 12.5 | Four equally restrained category highlight accents; no pitch ascent |
| 14-15 | Hold, no new pulses or accents; final 0.5-second fade from 14.5 to zero |

The reading duck ramps down from 0.65 to 1 second and recovers from 10.5 to 11.3 seconds. Its measured energy-ratio attenuation is -3.000 dB. Accents remain independently low-level and are not ducked. Cue timestamps are synthesis onsets with a 25 ms soft attack, not hard impulses. Music pulse onsets: 0.8, 3.2, 5.6, 8, 10.4, 12.8 seconds.

Decoded mix RMS is -25.450 dBFS during 1-4 seconds and -26.379 dBFS during 4-10.5 seconds. The quietest tested interior 100 ms music window is -26.698 dBFS, confirming a continuous bed rather than silent gaps.

## Generate And Verify

From the project directory, verify the existing output parent before generation:

```powershell
if (-not (Test-Path -LiteralPath "public/audio" -PathType Container)) { throw 'Audio output parent missing' }
node scripts/generate-analyze-audio.mjs
node scripts/generate-analyze-audio.mjs --verify
```

Generation writes only the three analyze WAVs and `public/audio/analyze-stats.json`. The source is `scripts/generate-analyze-audio.mjs`; it does not modify the stack generator, package configuration, or video. No third-party synthesis dependencies are required.

`--verify` is read-only. It regenerates in memory, compares all WAV and JSON bytes, decodes the on-disk WAVs, validates duration and PCM headers, checks all 1,440,000 interleaved samples for exact stem summation, verifies zero endpoints and peak ceilings, and checks cue presence, SFX silence outside cues, reading attenuation, continuous music, and the -25 dBFS mix RMS target. Seed: `0x414e4c31`. Same Node runtime/platform is the bit-identical reference; cross-engine transcendental math is not promised bit-identical.

## Verification Results

- Generation and subsequent `--verify` passed.
- Decoded stem-sum residual: exactly 0 PCM units across all samples.
- All seven scheduled accents present, with no SFX outside their windows.
- All endpoints zero, no clipping, all sample peaks below -6 dBFS.
- Independent bundled `node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe` inspection confirmed `pcm_s24le`, 48,000 Hz, 2 channels, 24-bit samples, 720,000 frames, and 15.000000 seconds for all three files. Its `s32` sample format is the decoder container, not a 32-bit source file.
- No subjective listening review or video render was performed.
