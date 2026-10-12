# Analyze Source Assets

Prepared from the existing `out/Review.mp4` recording, not from a new Gmail run.
The original recording is unchanged. All excerpts play at normal speed; no
command typing, terminal output, freeze frames, or interpolated frames were
fabricated. The command is already entered in the selected footage.

## Deliverables

All videos are silent H.264 MP4, 30 fps, yuv420p, CRF 16, with faststart enabled
and source metadata stripped. Paths below are relative to this project.

| Asset | Dimensions | Duration | Frames | Source interval |
| --- | --- | --- | --- | --- |
| `public/analyze-command.mp4` | 1240 x 132 | 4 seconds | 120 | [4, 8) seconds |
| `public/analyze-progress.mp4` | 1240 x 420 | 6 seconds | 180 | [8.5, 14.5) seconds |
| `public/analyze-categories.mp4` | 1240 x 420 | 5 seconds | 150 | [19, 24) seconds |
| `public/analyze-15s.mp4` | 1240 x 570 | 15 seconds | 450 | Assembly below |
| `out/analyze-source-15s-preview.mp4` | 1240 x 570 | 15 seconds | 450 | Byte-identical copy of combined asset |

## Assembly

Use `public/analyze-15s.mp4` for the complete prepared source panel. The command
strip occupies (0, 0), 1240 x 132. An 18-pixel gap separates it from the output
panel at (0, 150), 1240 x 420. The background is `#1a1a1a`.

| Scene interval | Scene frames | Original frames | Content |
| --- | --- | --- | --- |
| [0, 4) seconds | 0-119 | 120-239 | Recorded command; output panel blank |
| [4, 10) seconds | 120-299 | 255-434 | Recorded command and progress/read-only output |
| [10, 15) seconds | 300-449 | 570-719 | Recorded command and scrolling categories/safe summaries |

Frame numbers are zero-based and inclusive in the frame columns. The command
in the composite continues using the actual source frames corresponding to each
excerpt; it is not a loop of the four-second command asset.

Recommended scene labels, to be added by the consuming composition, are
`Recorded command`, `Read-only analysis`, and `Categories and summary`, with a
persistent `Normal-speed excerpts` disclosure. Labels are not baked into these
assets. Cuts omit source time; this is not an uninterrupted 15-second run.
No Remotion composition files were changed as part of this source preparation.

## Privacy Treatment

Cropping excludes account addresses, sender rows, scan identifiers, and returning
shell prompts. Redaction is baked into the exported pixels, not dependent on
overlays in a later composition. No audio is retained.

All coordinates below refer to the original 1920 x 1080 recording, unless noted.
Rectangles use x, y, width, height, with exclusive right and bottom bounds.

| Region | Source rectangle | Processing |
| --- | --- | --- |
| Early command | 400, 644, 1240, 132 | Before command pins at top |
| Pinned command | 400, 150, 1240, 132 | After recorded terminal jump |
| Early progress | 400, 836, 1240, 100 | Top-aligned in 1240 x 420 background |
| Pinned progress | 400, 318, 1240, 360 | Top-aligned; excludes account above and IDs below |
| Categories/summary | 400, 390, 1240, 340 | Top-aligned; excludes sender rows above and shell prompts below |

The command crop has a solid `#1a1a1a` mask at command-relative
(0, 0, 524, 36) covering the prompt/user-path prefix. Its top three pixel rows
are also masked across the full width to suppress preceding-line edge fragments.
The actual command and `--redact-subjects` flag remain visible. There is no broad
mask across the useful output or reconstructed replacement terminal text.

Every selected source frame is checked against early and pinned command
references. The pipeline refuses export if neither command state matches within
the configured mean absolute RGB error threshold (< 3). This selects the safe
crop at the recorded jump instead of relying on a guessed scroll timestamp.
This is a crop-state check, not an automated PII detector.

## Verified Categories

These names and message counts are visible in the recorded category table:

| Name | Messages |
| --- | --- |
| Promotions | 327 |
| Social | 19 |
| Updates | 535 |
| Forums | 87 |
| Other / unclassified | 32 |
| Trash | 1 |
| Spam | 47 |

Additional summary rows include `Category union (unique)` (968),
`Multiple category labels` (0), and `Trash / Spam union (unique)` (48).
Other / unclassified is not Primary. Categories, Trash, and Spam can overlap;
do not add them as if mutually exclusive. These counts describe a limited
1,000-message preview, not the entire mailbox. Estimated sizes are not bytes
freed or exact Google storage quota. The footage makes no deletion recommendation.

## Validation

Regeneration and validation completed successfully using:

```powershell
node scripts/prepare-analyze-source.mjs
```

The script uses Node built-ins and the installed Remotion FFmpeg executable at
`node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe`.

- Re-decoded all three individual exports and checked exact decoded sizes and frame counts, including their last frames.
- Re-decoded all 450 composite frames in ten-frame batches and verified no frame exists at 15 seconds.
- Visually reviewed all 45 decoded composite contact sheets, `out/analyze-source-audit-000.png` through `440.png`, in steps of ten. Each sheet has two columns and five rows in chronological reading order at half resolution.
- Visually reviewed all 20 full-resolution individual samples: command frames 0, 15, 30, 60, 90, 119; progress frames 0, 15, 30, 60, 90, 119, 179; categories frames 0, 15, 30, 60, 90, 119, 149.
- No readable account address, sender address, scan ID, or personal shell path was observed in those reviewed exports.
- Distinct pre-encode source-crop counts were 61 for command, 141 for progress, and 128 for categories. These are provenance checks, not a claim of continuous visible change or typing.
- Verified the original source SHA-256 is unchanged before and after preparation: `2bf0430f29abf65612af48a9c953e5d9de87d93553c2c05d4fe91299f4e61b98`.
- Saved source-frame mappings, per-frame command-state checks, and export metadata in `out/analyze-source-validation.json`.
- Removed generated private source inspection PNGs after successful preparation. The original recording and pre-existing source stills remain private and unchanged.

## Limits

The final five seconds show categories briefly, then the source's real scrolling
size/age tables and caution text. They are not a five-second held category table.
Some table edges are clipped during the recorded scroll. The first four seconds
retain a blank output panel by design. Source cursor movement and waiting periods
are preserved. The full-frame visual audit uses half-size contact sheets plus
full-resolution samples, not OCR or a formal privacy guarantee.

These crop coordinates are specific to this recording. A different source or
new cut points require renewed visual review; a successful command-state check
alone does not establish privacy. Keep `out/Review.mp4` and original inspection
stills out of any public release. Share only the prepared derivatives.
