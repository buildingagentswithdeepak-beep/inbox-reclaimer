# Technical Stack Audio

Original local synthesis: exactly 10 seconds, 100 BPM, instrumental, no vocals,
samples, downloads, services, or external dependencies. The arrangement uses
overlapping sine-based Dm9 / Bbmaj9 colors, restrained bass pulses, filtered
percussion, and sparse low-register keys. Its design avoids bright notification
chimes, sci-fi chatbot gestures, pitch sweeps, and triumphant approval cadences.
The 11 accents are soft, unpitched filtered-noise taps rather than pitched alerts.
These are design descriptions, not claims of a listening review.

## Owned Files

- `scripts/generate-stack-audio.mjs`: standalone Node.js synthesizer and verifier.
- `public/audio/stack-music.wav`: continuous instrumental bed.
- `public/audio/stack-sfx.wav`: synchronized accents, silent outside cue windows.
- `public/audio/stack-mix.wav`: exact integer PCM sum of both stems.
- `public/audio/stack-stats.json`: levels, cue frames, section metrics, SHA-256 hashes, and checks.
- `STACK-AUDIO.md`: this delivery record.

Only these six files were created for this task. The report generator was read
for reusable synthesis and verification patterns, but is not imported or invoked.
This arrangement, seed, and rendered audio are independent. No other files were
changed by this task.

## Cue Sheet

| Onset (s) | Frame | Cue | Length (s) |
| --- | --- | --- | --- |
| 0.15 | 7200 | Stack name 1 | 0.22 |
| 0.75 | 36000 | Stack name 2 | 0.22 |
| 1.35 | 64800 | Stack name 3 | 0.22 |
| 1.95 | 93600 | Stack name 4 | 0.22 |
| 2.65 | 127200 | Dependency highlight | 0.34 |
| 4.50 | 216000 | No runtime LLM | 0.30 |
| 5.30 | 254400 | Metadata flow 1 | 0.18 |
| 5.65 | 271200 | Metadata flow 2 | 0.18 |
| 6.00 | 288000 | Metadata flow 3 | 0.18 |
| 6.35 | 304800 | Metadata flow 4 | 0.18 |
| 8.00 | 384000 | Workflow | 0.38 |

Onsets identify the start of each envelope; accents rise from zero over 18 ms.
The music retains its independent 0.6-second beat grid. The workflow accent
does not trigger a musical swell or victory resolution.

## Automation

Both stems share a smooth 0.2-second opening fade and a final 0.4-second fade
starting at 9.6 seconds, reaching digital silence at the final stereo frame.
Both duck smoothly from 4.3 to 4.5 seconds, hold exactly -4 dB throughout
4.5-7.5 seconds, and recover smoothly from 7.5 to 7.7 seconds. The ramps are
outside the requested clarification interval so the full attenuation is already
present at the 4.5-second cue.

Attenuation measured against the identical faded but unducked signals, before
PCM quantization: music -4.000000000000121 dB; SFX -3.9999999999999996 dB.
This comparison isolates automation from natural musical dynamics.

## Measured Results

Each WAV is signed 24-bit integer PCM, 48,000 Hz, stereo, exactly 480,000 frames
(10.000 seconds), and 2,880,044 bytes including its 44-byte RIFF header.

| File | RMS (dBFS) | Sample peak (dBFS) | Clipped samples |
| --- | --- | --- | --- |
| `stack-music.wav` | -24.016 | -11.090 | 0 |
| `stack-sfx.wav` | -50.203 | -24.916 | 0 |
| `stack-mix.wav` | -24.000 | -11.090 | 0 |

Measurements use decoded PCM with full scale 8,388,607: unweighted RMS across
both channels over the entire file, and the largest absolute sample in either
channel. These are sample-peak/RMS measurements, not true peak or LUFS. The SFX
RMS includes inter-cue silence. The -24 dBFS target applies to the complete mix;
the stems are not independently normalized. No limiter or clipping was needed.
The mix has 5.090 dB margin below the requested -6 dBFS sample-peak ceiling.

## Verification

`Test-Path` confirmed the project, script, and output parent directories before
creation. Generation and a separate read-only `--verify` process both passed:

- Exact WAV format, header/payload sizes, duration, and PCM encode/decode round trips.
- Zero clipped samples and zero first/last stereo frames in all three WAVs.
- Exact stem sum across all 960,000 interleaved samples; integer null residual is zero.
- All 11 nonempty accents at the scheduled frames; SFX silence outside cue windows.
- Continuous music: every 100 ms window from 0.2 to 9.6 seconds exceeds -45 dBFS RMS; minimum -27.189 dBFS.
- Full -4 dB attenuation on both stems throughout 4.5-7.5 seconds.
- Mix RMS within 0.01 dB of -24 dBFS; all sample peaks below -6 dBFS.
- Byte-identical regenerated WAVs and stats JSON compared with the saved files.

From the project directory:

```powershell
if (!(Test-Path -LiteralPath "public/audio" -PathType Container)) { throw "Audio directory missing" }
node scripts/generate-stack-audio.mjs
node scripts/generate-stack-audio.mjs --verify
```

Seed `0x53544b31`, fixed event order, and no timestamps or external inputs make
generation deterministic. Repeatability was verified in the current Node.js
environment; cross-engine floating-point identity is not claimed. WAV SHA-256
hashes are in `public/audio/stack-stats.json`. Verification is numerical only;
no subjective listening review is claimed.
