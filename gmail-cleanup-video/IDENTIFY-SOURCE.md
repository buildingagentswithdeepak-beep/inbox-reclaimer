# Identify Source

Corrected at user request: `out/ReportSender.mp4` replaces the incorrect `Review.mp4` source for this scene. Actual senders remain visible as authorized. Only the `noreply@medium.com` row in the report is outlined.

## Source Treatment

- Timestamp: 3.000 seconds, first decoded frame at or after the requested time.
- Source crop: x48, y446, width864, height396. This retains the left message-count table's headings and four sender rows.
- Crop excludes browser tabs, local file path, desktop taskbar, and the account-identifying right-hand ranking section.
- Output: `public/identify-senders.png`, 1200x550, lossless RGB PNG, 25/18 nearest-neighbor enlargement.
- No sender mask, reconstructed values, or replacement report text.
- Disclosure: `Recorded report / held for readability` and `ACTUAL SENDERS`.
- Requested sender appears in the third row: 27 messages and 2.72 MB estimated size. Size is not bytes freed or exact storage quota.

## Verification

`npm run prepare:identify` verifies unchanged source SHA-256 before/after generation, lossless PNG round trip, and correspondence of all 660,000 exported pixels to the source crop. Source hash and crop audit are saved in `out/identify-source-validation.json`. Crop coordinates must be reviewed again if the input recording changes.

Preview: `out/identify-source-preview.png`. In the composition, the blue outline is at x27,y328,width992,height104 relative to the report window; the image begins at y48. All other report rows stay visible and unchanged.

## Preview Boundary

The ending shows a supported illustrative `sender-cleanup --sender noreply@medium.com` command, not executed. No results, plan ID or approval are fabricated. Fictional inbox rows are independent of the actual senders and are not attributed to Medium. Original recordings and previous scenes are unchanged.
