# Suggest Source Assets

## Deliverables

These are genuine source-pixel stills for the existing 8-second Remotion Suggest scene, not a fabricated dashboard or reconstructed terminal. No scenes, source recordings, package files, or other preparation scripts were changed. No Gmail commands were issued. No creator footage is included.

| Asset | Dimensions | Intended use in a roughly 1300x500 product area |
| --- | --- | --- |
| `public/suggest-command.png` | 1250x154 | Contain at up to 1300px wide, centered. Original wrapped command and flags. |
| `public/suggest-plan.png` | 650x282 | Contain at approximately 1152x500. Primary readable proof of saved plan ID and unchanged mail. |
| `public/suggest-report.png` | 1300x415 | Display at native width, centered. Actual saved HTML report summary, with plan ID visible. |

Use `Img` with `staticFile('suggest-command.png')`, `staticFile('suggest-plan.png')`, and `staticFile('suggest-report.png')`. Preserve aspect ratio with `objectFit: 'contain'`; do not stretch these into a common aspect ratio or crop away the plan ID. Suggested allocation is command 0-2s, JSON 2-5s, report 5-8s. This is usage guidance only, not an edit to the scene.

Use the scene labels **Recorded terminal / held for readability** and **Saved HTML report / held for readability**. Labels are not baked into the pixels. Stills deliberately avoid scrolling into private message IDs. The report ID is small in the original styling; the preceding JSON still is the close, readable ID proof. No moving excerpts were exported.

## Exact Match

- Saved plan ID: `c147c7a16a1b407b8bb1b9db1e4d487b`.
- Sender: `noreply@medium.com`, explicitly allowed to remain visible.
- Recording at 29s: `candidate_limit: 20`, `examined_count: 20`, `eligible_count: 20`, `approval_created: false`, and `mail_changed: false`.
- Actual HTML DOM: `Plan: c147c7a16a1b407b8bb1b9db1e4d487b`, `Exact sender: noreply@medium.com`, `20 eligible messages from 20 inspected candidates; candidate cap 20.`, and `No approval` / `No mail changed`.
- The 32-character plan ID was visually checked against the recording and compared exactly with the source HTML and rendered DOM. Sender identity was checked in the original terminal frame and matched exactly against HTML and DOM.
- The recorded command has `--sender $sender`, `--max-messages 20`, `--redact-subjects`, and `--html $report`. There is no `--execute`. The `sender-cl` / `eanup` wrap is original and intentionally preserved, not repaired or retyped.

The original sources contain a release-gate inconsistency: terminal output below the selected crop says `live_mutation_released: true` and `release_gate: "B_passed"`, while later HTML prose says live trash/restore is release-disabled pending Gate B verification. Neither was rewritten; both are outside the delivered summary crops. These assets establish the matching saved selection and no-change preview, not execution capability or approval.

## Provenance And Privacy

Source recording: `out/SelectedEMailPlan.mp4`, 1920x1080, FFprobe duration **44.164444 seconds**.

SHA-256: `3b8ff86100f95d67380cf1c692739914cfce428319312824ce11192a28c766ec`.

Source HTML: `C:\Users\v-deegarg\AppData\Local\hermes\profiles\coder\inbox_reclaimer\reports\demo-suggest-20261008-213941.html`.

SHA-256: `ba3319a0b5bb8810c13717a739dcdc177713c3277ad50aec4096b95b6abe3e4d`.

Coordinates below are half-open pixel intervals; dimensions are unscaled source dimensions.

| Asset | Source and crop | Permanent privacy treatment |
| --- | --- | --- |
| Command | First decoded frame at or after 2s; x400..1650, y574..728 | Opaque RGB(26,26,26) mask over source x400..920, y574..602. Only the prompt prefix is removed; continuation and command characters remain source pixels. |
| Plan | First decoded frame at or after 29s; x405..1055, y320..602 | No mask. Crop includes counts, plan ID, and both false values; excludes all subsequent sender/digest/message-list rows and shell paths. |
| Report | Actual browser viewport x0..1300, y0..415 | Opaque RGB(18,18,18) mask at x271, y143, width225, height24 covers the account field and separator. Sender is retained. Crop ends before digest begins at y416.56; message-list panel begins at y616.55. |

Report capture opens the original HTML directly by `file:` URL using Remotion's installed Chrome Headless Shell and `@remotion/renderer` `openBrowser`. HTTP/HTTPS requests are blocked. The existing CSP and stylesheet are retained, fonts are awaited, and the expected 44px title style is verified. Viewport is 1300x1000 at device scale factor 1. DOM ranges identify the real plan line, account field, digest, and message table. `Page.captureScreenshot` captures only the safe summary rectangle; an opaque pixel mask is burned into the in-memory screenshot before writing any image. No data, text, styles, or DOM are rewritten. There is no browser chrome/address bar in the capture.

The raw report is never copied into `public`, served by a project server, or written as a raw screenshot. Only masked/cropped PNGs are exported. Account address, filesystem paths, internal message IDs, and digest are absent from all new public images and audit previews; the saved plan ID is intentionally visible.

## Reproduction And Checks

Run from this project:

```powershell
node scripts/prepare-suggest-source.mjs
```

`SUGGEST_REPORT_PATH` can point to the same report at another local path; preparation refuses a different plan ID or sender. Uses only existing Remotion FFmpeg/FFprobe/Chromium dependencies and a dependency-free PNG encoder. No dependency installation is required.

- Inspected existing source stills at 2s, 29s, and 41s. The 41s frame contains message IDs and a local report-opening command, not a rendered report; it is not used as a public asset.
- Preparation decodes fresh full-resolution source frames, crops in RGB memory without chroma-coordinate rounding, and preserves all unmasked pixels exactly.
- Command: 177,940 unchanged source pixels; 14,560 opaque mask pixels.
- Plan: all 183,300 pixels match the decoded recording crop exactly.
- Report: 534,100 unchanged browser-capture pixels; 5,400 opaque mask pixels.
- Lossless PNG encode/decode round-trip checks pass for all three assets. Every unmasked pixel is verified against its original; every report mask pixel is checked for opacity/color.
- Source recording and HTML SHA-256 hashes are checked before and after preparation and remain unchanged.
- Visually reviewed all three delivered assets through `out/suggest-source-command-preview.png`, `out/suggest-source-plan-preview.png`, and `out/suggest-source-report-preview.png`, each centered with contain sizing in a 1300x500 frame. No private fields were observed. Preview scaling is nearest-neighbor for audit purposes; the deliverable PNGs are unscaled.
- `out/suggest-source-validation.json` records dimensions, hashes, exact crop/mask rectangles, verified safe DOM text, range geometry, pixel counts, and disclosure labels. It contains no raw account address, digest, or message IDs.

The visual check is human/model inspection, not automated OCR. Source/DOM equality and pixel preservation checks are automated. Full-scene timing/render validation belongs to the scene integration; this task only prepares and validates source assets.
