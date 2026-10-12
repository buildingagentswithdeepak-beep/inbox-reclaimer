# GmailClutterAccumulation Audio

Original, deterministic 24-second instrumental and notification accents. Synthesized
locally using Node.js built-ins only: no network, samples, external dependencies,
or borrowed melodies. The generator adapts the WAV/verification approach of
`scripts/generate-intro-audio.mjs` without changing that script or its assets.

## Files

- `scripts/generate-clutter-audio.mjs`: synthesis, PCM encoding, measurements, and verification.
- `public/audio/clutter-music.wav`: warm instrumental stem.
- `public/audio/clutter-sfx.wav`: 24 soft notification accents, otherwise silent.
- `public/audio/clutter-mix.wav`: exact integer-PCM sum of the two stems.
- `public/audio/clutter-stats.json`: decoded PCM levels, section measurements, arrival timing, and SHA-256 hashes.
- `CLUTTER-AUDIO.md`: this document.

All WAVs are stereo, 48,000 Hz, signed 24-bit PCM, exactly 1,152,000 frames
(24.000 seconds), and 6,912,044 bytes. The full stereo mix targets -24 dBFS
unweighted RMS with a sample-peak ceiling of -6 dBFS. Both stems share the same
master gain; they are not independently normalized. Play either the mix or both
stems at unity gain starting at scene time zero, never all three together.

## Score and Timing

- 100 BPM (0.6-second quarter note), warm sine-based pads with sparse upper harmonics and narrow stereo placement.
- Five original overlapping voicings: Cmaj9, Am9, Fmaj9, G suspended, and C6/9. The last voicing sustains rather than signaling a success event.
- 0-19.8 seconds: pad level gently rises; bass enters after 2.4 seconds, soft low percussion after 4.8, felt-key notes after 6, filtered brushes after 10.2, and quiet offbeat texture after 14.4. Layer entrances ramp in gradually.
- Percussion is silent from 19.8 seconds onward. Remaining pitched activity settles out over 19.8-20.5 seconds.
- 20.5-24 seconds: pad-only hold, no notifications, percussion, alarm, deletion, or success sounds.
- Smooth 0.3-second fade-in and final 0.5-second fade-out on both stems. First and last stereo sample frames are exactly zero.

The 24 notification times are computed, not hand-positioned:

```js
times[i] = 3 + 16.8 * (1 - 0.89 ** i) / (1 - 0.89 ** 23); // i = 0..23
```

The first onset is 3.0 seconds and the last is 19.8 seconds. Onsets are rounded
to the nearest PCM frame (maximum half-sample error). Each notification is a
soft, short sine-based ping, with no delay or reverb tail. Its amplitude scales
with the square root of its following gap relative to the first gap; the last
uses its preceding gap. Duration is `min(0.48, 1.65 * gap)` seconds. This limits
overlap to two voices and makes late pings shorter and quieter, not harsher.
Full onset frames, durations, notes, and relative gains are in the stats JSON.

## Reproduce and Verify

Run from the project directory in PowerShell. Check the parent before generation:

```powershell
if (-not (Test-Path -LiteralPath './public/audio' -PathType Container)) { throw 'Missing audio directory' }
node ./scripts/generate-clutter-audio.mjs
node ./scripts/generate-clutter-audio.mjs --verify
```

Generation writes only the three clutter WAVs and `clutter-stats.json`. The
read-only `--verify` invocation synthesizes everything again with fixed seed
`0x434c5554`, compares all four output files byte-for-byte, and repeats the
format, duration, peak, RMS, clipping, endpoint, timing, two-voice overlap,
pad-only hold, continuous-bed, and exact decoded-stem-sum assertions.
Repeatability is checked in the same Node.js runtime; no cross-engine floating
point identity is claimed. There is no timestamp or random external input.

## Measurements

Levels are decoded-PCM sample peak and unweighted RMS across both channels over
the entire 24 seconds, including fades and silence. They are **not LUFS** and
are not oversampled true-peak measurements. JSON `null` dB values mean digital
silence. No limiter, clipping, or nonlinear processing is applied to the mix.

| File | RMS dBFS | Sample Peak dBFS | Clipped Samples |
| --- | ---: | ---: | ---: |
| `clutter-music.wav` | -24.016 | -9.415 | 0 |
| `clutter-sfx.wav` | -48.348 | -27.449 | 0 |
| `clutter-mix.wav` | -24.000 | -9.633 | 0 |

Generation and a separate read-only `--verify` run both passed. All three WAVs
and the stats JSON were byte-identical on regeneration. Decoding verified
24.000-second duration, stereo 48 kHz/24-bit PCM, exact integer stem summation,
zero endpoints, no clipping, and the -6 dBFS sample-peak ceiling on every file.
All 24 arrival events passed nearest-frame synchronization and non-increasing
gain checks; maximum overlapping notification voices was two. Percussion was
silent from 19.8 seconds and non-pad activity/SFX from 20.5 seconds. Every
100 ms music window from 0.3 to 23.5 seconds exceeded -45 dBFS RMS.

These are synthesis and signal checks, not a subjective listening review.
