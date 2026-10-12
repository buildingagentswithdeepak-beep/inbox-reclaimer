# Gmail Introduction Audio

Original, locally synthesized instrumental for the 18-second Gmail introduction.
No downloaded media, external samples, runtime dependencies, or modifications to
the existing audio generator or its outputs.

## Sound

- 100 BPM, warm overlapping Dmaj9 / Bm7 / Gmaj9 / Asus2 voicings.
- Sparse, rounded plucked motif, quiet low pulses, and restrained filtered texture.
- Continuous music across the full introduction, including the storage caveat.
- Both stems duck by 4 dB from 7.0 through 11.0 seconds. Smooth ramps run
  6.8-7.0 and 11.0-11.25 seconds; the reported duck compares identical music
  samples before and after automation, not unrelated musical passages.
- Soft non-tonal fabric/air accents begin at 0.3, 4, 7, 11.3, 12.15, 13,
  14.4, 15.4, and 16.1 seconds. No notifications or triumphant success chime.
- Shared smooth fade over the first 0.3 and last 0.6 seconds, with exact zero endpoints.

## Files

- `scripts/generate-intro-audio.mjs`: standalone seeded synthesis and verification.
- `public/audio/intro-music.wav`: independent music stem, including duck and fades.
- `public/audio/intro-sfx.wav`: independent accent stem, including duck and fades.
- `public/audio/intro-mix.wav`: exact integer PCM sum of the two stems.
- `public/audio/intro-stats.json`: decoded levels, format, SHA-256 hashes, and checks.

All WAV files are uncompressed 48,000 Hz, stereo, signed 24-bit PCM, exactly
864,000 frames / 18 seconds. Each is 5,184,044 bytes. A common fixed gain targets
-23.5 dBFS full-length stereo RMS while retaining sample peak below -6 dBFS.
No limiter or independent stem normalization changes their balance.

## Verified Levels

| File | RMS dBFS | Sample peak dBFS | Clipped samples |
| --- | ---: | ---: | ---: |
| `intro-music.wav` | -23.501 | -9.372 | 0 |
| `intro-sfx.wav` | -55.600 | -30.448 | 0 |
| `intro-mix.wav` | -23.500 | -9.372 | 0 |

Fresh-process regeneration matched all four generated files byte-for-byte.
Measured caveat attenuation: -4.000 dB. Quietest interior 100 ms music window:
-28.855 dBFS RMS, with zero digitally silent interior stereo frames.
The mix equals the decoded stem sum at all 1,728,000 channel samples.

## Regenerate And Verify

From the project directory in PowerShell, check parents before generation:

```powershell
Test-Path -LiteralPath "scripts" -PathType Container
Test-Path -LiteralPath "public/audio" -PathType Container
node scripts/generate-intro-audio.mjs
node scripts/generate-intro-audio.mjs --verify
```

Generation writes only the four `intro-*` assets above. Verification writes
nothing: a fresh process synthesizes the same seed and compares every byte of
all WAV files and the stats JSON. Repeatability is scoped to the same Node.js
runtime; floating-point transcendental implementations may vary across platforms.

Checks include encoded WAV format/duration, decoded PCM round-trip, clipping,
zero endpoints, exact decoded stem summation, mix level bounds, and measured
4 dB automation. Continuity is checked over 0.3-17.4 seconds: every 100 ms music
window must exceed -45 dBFS RMS and no stereo frame may be digitally silent.
The intentional endpoint fades are excluded from that continuity floor.

RMS is unweighted across both channels, not LUFS. Peak is sample peak, not an
oversampled true-peak measurement. Independent SFX silence between accents is
intentional. No video timeline or package scripts are changed; use the mix alone
or the two stems together at unity, never both playback options simultaneously.
