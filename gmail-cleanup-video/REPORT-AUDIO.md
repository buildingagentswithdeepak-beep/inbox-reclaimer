# Report Soundtrack

Original offline instrumental, 19 seconds at 100 BPM. Warm overlapping sine-based
pads, restrained bass pulses, soft filtered percussion, and sparse low-register
keys leave space for future narration. Suspended/common-tone harmony avoids a
triumphant resolution. The six action accents are unpitched filtered fabric/air
gestures, not notifications, chimes, or a green-success sound. No voice is included.

## Files

- `scripts/generate-report-audio.mjs`: dependency-free Node.js synthesizer and verifier.
- `public/audio/report-music.wav`: continuous instrumental bed.
- `public/audio/report-sfx.wav`: six synchronized accents, otherwise silent.
- `public/audio/report-mix.wav`: exact integer PCM sum of the two stems.
- `public/audio/report-stats.json`: decoded levels, section measurements, SHA-256 hashes, cue frames, and checks.
- `REPORT-AUDIO.md`: this delivery record.

Only these six new files were created. Existing files, including the intro
generator and its audio, were not changed. The new generator reuses the intro's
seeded xorshift noise, smooth envelopes, constant-power panning, additive voices,
PCM encoder, and quantize-before-summing approach. The arrangement, seed, and
rendered audio are new; no borrowed audio, samples, downloads, or services are used.

## Cue Sheet

| Time (s) | Frame | Cue | Gesture length (s) |
| --- | --- | --- | --- |
| 0.25 | 12000 | Reveal | 0.40 |
| 2.00 | 96000 | Analyze | 0.40 |
| 5.00 | 240000 | Identify | 0.40 |
| 8.00 | 384000 | Suggest | 0.40 |
| 11.00 | 528000 | Review | 0.40 |
| 16.00 | 768000 | Text handoff | 0.55 |

Cue times are scheduled envelope onsets; each gesture begins at zero amplitude
and rises softly rather than clicking. The music keeps its independent 0.6-second
beat grid instead of restarting at scene boundaries.

Both stems smoothly duck from 15.8 to 16.0 seconds, hold exactly -4 dB from 16 to
19 seconds, and share the final 0.45-second fade beginning at 18.55 seconds. The
last stereo frame is digital silence. A 0.2-second opening fade avoids a hard edge.
Duck attenuation was verified against identical faded signals without ducking,
before PCM quantization: music -4.000000000000157 dB; SFX -4.000000000000040 dB.
This isolates automation from natural differences between musical sections.

## Measured Results

All WAV files are signed 24-bit PCM, 48,000 Hz, stereo, exactly 912,000 frames
(19.000 seconds), and 5,472,044 bytes each, including the 44-byte RIFF header.

| File | RMS (dBFS) | Sample peak (dBFS) | Clipped samples |
| --- | --- | --- | --- |
| `report-music.wav` | -24.002 | -9.955 | 0 |
| `report-sfx.wav` | -55.398 | -28.407 | 0 |
| `report-mix.wav` | -24.000 | -9.955 | 0 |

Measurements use decoded PCM with full scale 8,388,607: unweighted RMS across
both channels over the entire 19 seconds, and the largest absolute sample across
either channel. These are **sample peak and RMS, not LUFS or true peak**. The SFX
RMS includes the silence between accents. The -24 dBFS RMS target applies to the
complete mix, not independent stem normalization. No limiter or clipping was
needed. The mix remains 3.955 dB below the requested -6 dBFS sample-peak ceiling.

## Verification

`Test-Path` confirmed the script and output directories before generation.
Generation and a separate `--verify` run both passed:

- All three WAV headers, payload sizes, exact durations, and PCM round trips.
- Zero clipped samples and zero first/last stereo frames in every WAV.
- Exact stem sum for all 1,824,000 interleaved PCM samples; null residual is zero.
- Six nonempty accents and digital silence outside their scheduled SFX windows.
- A continuous music bed: every 100 ms window from 0.2 to 18.5 seconds exceeds -45 dBFS RMS; minimum measured -29.692 dBFS.
- Exact -4 dB attenuation on both stems over the final three seconds, independent of the fade.
- Mix RMS within 0.01 dB of -24 dBFS and all sample peaks below -6 dBFS.
- Byte-identical in-memory regeneration against all three saved WAVs and the saved stats JSON.

From the project directory, reproduce with PowerShell:

```powershell
if (!(Test-Path -LiteralPath "public/audio" -PathType Container)) { throw "Audio directory missing" }
node scripts/generate-report-audio.mjs
node scripts/generate-report-audio.mjs --verify
```

Verification mode is read-only. Seed `0x52505431` and fixed event order make
generation deterministic; there are no timestamps, random sources, or external
dependencies. Byte repeatability was tested in the current Node.js environment;
cross-engine floating-point identity is not claimed. SHA-256 hashes are recorded
in `public/audio/report-stats.json`. Checks are numerical; no listening review is
claimed.
