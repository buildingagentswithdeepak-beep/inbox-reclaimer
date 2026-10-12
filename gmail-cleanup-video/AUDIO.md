# Original Audio

## Generate And Verify

Run from the project directory with Node.js, without installation or network access:

```sh
node scripts/generate-audio.mjs
node scripts/generate-audio.mjs --verify
```

The second command synthesizes again in memory and checks every generated file for byte identity without writing files. Paths resolve relative to the script, not the current shell directory. The generator requires the existing project `public/` parent and only writes into `public/audio/`.

- `public/audio/music.wav`: music stem, including exact digital silence from 4.000 through just before 12.000 seconds.
- `public/audio/sfx.wav`: notification, warning, transition, and workflow accents.
- `public/audio/mix-preview.wav`: exact integer-sample sum of the two stems, for audition only.
- `public/audio/stats.json`: generated decoded-PCM measurements, section measurements, seed, and SHA-256 hashes.

All WAVs are exactly 18 seconds: 864,000 stereo frames, 48,000 Hz, signed little-endian 24-bit linear PCM, 5,184,044 bytes each including the WAV header. Each begins and ends at zero. Both stems are aligned to the video start; do not concatenate them or offset the resumed music to 12 seconds. Use the two stems together at unity gain, or the preview alone, never all three. Composition integration is intentionally outside this file scope.

## Composition

Original, understated 100 BPM tech instrumental. Warm, gently detuned sine-based pads support a sparse, softened plucked motif, centered round bass, quiet low percussion, and filtered-noise ticks. There are no hard square waves, arcade leads, triumphant brass, or large cinematic impacts. Conservative shared gain preserves the intended quieter SFX balance rather than independently normalizing effects.

The opening uses close E-minor/add9 voicings and an increasing musical envelope. Accelerating notifications provide most of the pressure. After the interruption, the same restrained vocabulary returns in wider G6/9 and Cmaj9 voicings, with more space and warmth rather than a victory fanfare. Pluck echoes are quiet and finite. The final music gate is applied after all synthesis and echoes, so no musical tail crosses the 4-second boundary.

## Cue Sheet

| Time (seconds) | Sound |
| --- | --- |
| 0.00-4.00 | Tension bed, warm pad, sparse plucks, bass and very soft percussion. Music eases out over the last 75 ms before 4.00. |
| 0.35, 1.10, 1.80, 2.35, 2.85, 3.20, 3.50, 3.75 | Soft, accumulating notification pings with alternating narrow stereo positions; last tail ends by 4.00. |
| 4.00 | Brief 460 ms rounded low warning interval on SFX only, not an alarm. |
| 4.00-12.00 | Music is exactly zero; SFX contains only the warning tail and specified pullback cue. No upgrade click. |
| 10.45 | Quiet 640 ms filtered-noise pullback whoosh. |
| 12.00 | Quiet 520 ms reveal whoosh; music returns with a short fade-in and warmer open voicings. |
| 12.80 | Soft tonal analysis accent. |
| 14.00 | Soft tonal suggestions accent. |
| 15.20 | Soft tonal review accent. |
| 16.80 | Subtle 680 ms monitor-handoff whoosh. |
| 17.55-18.00 | Smooth final 450 ms fade applied to both stems, ending at exact zero. |

Cue times indicate onsets, not envelope peaks. No narration is generated; this is a bed for later creator narration. Leave the stems at their supplied relative levels and make any further narration balancing in the final video mix.

## Measurement

The generator measures encoded-and-decoded PCM, reporting maximum absolute sample value across both channels and unweighted RMS across both channels. Section RMS includes every sample in each named interval. Full-length RMS includes the intentional silent middle, so it is lower than the active musical sections. A full-scale sine has approximately -3.01 dBFS RMS under this convention. `null` dBFS in JSON means digital silence (negative infinity).

The shared gain targets -23 dBFS full-length preview RMS and imposes a -6.2 dBFS pre-quantization sample-peak ceiling. It asserts the final preview stays between -24 and -20 dBFS RMS and at or below -6 dBFS sample peak, checks every sample for clipping, verifies the exact music gap and zero endpoints, and verifies PCM encoding round trips. No limiter or compressor is required. No dither is added at 24 bits, preserving exact digital silence.

These are sample-peak and RMS measurements, **not formal LUFS, perceived loudness, or oversampled true-peak measurements**. Later narration and lossy encoding require a final mix check. Full generated numeric results and hashes are in `public/audio/stats.json`.

Measured generated delivery (dBFS):

| File | Sample peak | Full 18 s RMS | 0-4 s RMS | 4-12 s RMS | 12-18 s RMS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `music.wav` | -7.792 | -23.016 | -21.159 | Digital silence | -20.055 |
| `sfx.wav` | -24.996 | -47.258 | -44.614 | -48.521 | -48.351 |
| `mix-preview.wav` | -7.792 | -23.000 | -21.140 | -48.521 | -20.048 |

The low full-length SFX RMS reflects sparse, quiet cues rather than a continuous bed; the music gap is not a reason to boost that stem. Generation, syntax checking, and a second byte-identical `--verify` pass succeeded. These checks are numerical; no listening review or narration/encoded-video loudness check is claimed.

## Provenance

The composition, note sequence, envelopes, oscillators, percussion, pings, warning interval, and whooshes were authored procedurally for this video. All sound is synthesized locally from mathematical oscillators and filtered xorshift32 pseudorandom noise, using fixed seed `0x5245434c`. No borrowed recordings, samples, third-party musical themes, downloaded assets, external synthesis services, or runtime dependencies are used. Only Node.js built-ins are imported. Repeated runs in the same Node runtime produce byte-identical output; `--verify` checks this directly. This describes the production method, not a legal exclusivity guarantee over individual notes or timbres.
