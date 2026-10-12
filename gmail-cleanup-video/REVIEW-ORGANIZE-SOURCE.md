# Review / Organize Source Assets

Prepared from `out/ApprovalAndMoveToTrash.mp4` using the bundled ffmpeg/ffprobe and Node pixel masking. No application, approval UI, or Gmail operation was executed. No composition, project configuration, or other source file was edited.

## Assets

| Public file | Dimensions | Duration / provenance |
| --- | --- | --- |
| `review-organize-approval.mp4` | 1920x1008 | 420 frames, 30 fps, 14 seconds; source 48..62 at 1x |
| `review-organize-result.png` | 980x440 | Original result at source PTS 81.015016; intended nine-second hold |
| `review-organize-gmail.mp4` | 1484x798 | 120 frames, 30 fps, four seconds; source 86..90 at 1x |
| `review-organize-gmail-hold.png` | 1484x798 | Exact decoded final Gmail video frame 119; source PTS 89.958023 |
| `review-organize-source.json` | Metadata | Asset hashes, timeline, provenance, event frames, evidence limitations |

Both MP4s are H.264, yuv420p, CRF 12, with no audio. Unreviewed source audio is deliberately omitted; separate audio assets were not touched. This email/subject-visible revision explicitly supersedes the previous mask version and its hashes/review claims. Gmail now contains the original unmasked crop. Source, crops, source-time selection, durations, and frame counts are unchanged. Composition labels and finalization are outside this change's scope.

## Normalized Timeline

Frame ranges are zero-based and end-exclusive, at 30 fps. These are assembly instructions, not an edited final film; the editorial card and labels are specified in metadata, not burned into the source pixels.

| Scene frames | Scene seconds | Treatment |
| --- | --- | --- |
| 0..420 | 0..14 | Continuous approval asset, playbackRate 1; no internal cut, speed ramp, freeze, interpolation, or fabricated pointer |
| 420..450 | 14..15 | Editorial transition: `Later: run result` |
| 450..720 | 15..24 | Result still held nine seconds; `Later: run result / held for readability` |
| 720..840 | 24..28 | Gmail asset, playbackRate 1; `Later: Gmail Trash / visual check only` |
| 840..900 | 28..30 | Gmail final-frame still held two seconds; disclose held frame |

The explicit request for a four-second Gmail export (86..90) takes precedence over the earlier 86..90.5 outline. The final six-second Gmail section is four seconds of footage plus two seconds of hold, not 4.5 seconds plus 1.5 seconds.

Source timing is irregular (2771 video frames over 91.445556 seconds, nominal 30 fps). The script decodes the source sequentially, associates every decoded frame with ffprobe PTS, and selects the latest source frame at or before each target timestamp. This preserves elapsed time rather than speeding the clip up. Boundary samples can precede the requested start by less than one source frame. The per-frame audit records every actual source index and PTS. Export encoding is lossy; unchanged-source-pixel assertions apply before encoding, not to decoded H.264 bytes.

## Confirmation Evidence

Approval starts at scene frame zero, so approval-local and scene frame numbers are identical.

| Event | Asset / scene frame | Scene time | Source frame | Source PTS |
| --- | --- | --- | --- | --- |
| Last frame without button focus indication | 380 | 12.666667 | 1838 | 60.654016 |
| First dotted focus indication on confirmation button | 381 | 12.700000 | 1839 | 60.687017 |
| First visible native closing animation | 384 | 12.800000 | 1842 | 60.786021 |
| First fully dismissed native window | 390 | 13.000000 | 1848 | 60.984027 |

The visual confirmation change is bracketed by source PTS 60.654016..60.687017. It is recorded pointer/button evidence, not input-event telemetry. No claim of an exact operating-system mouse-down timestamp is made. The original checkbox, native button labels, pointer, and closing animation are retained. The broad closing masks begin only with the native animation, after the visible confirmation focus change. The final second remains the actual terminal aftermath rather than a prematurely cut or recreated dialog.

## Privacy Masks

All rectangles use `(x,y,width,height)` in output pixels and solid RGB `(24,24,24)`. No blur, text substitution, or reconstructed native controls are used. Outside masks, source crop pixels are asserted byte-identical before encoding on every frame.

Approval crop: source `(0,0,1920,1008)`, excluding taskbar/clock.

| Native field | Rectangle |
| --- | --- |
| Membership digest value | `(188,275,600,27)` |
| Message-ID cells | `(31,459,360,314)` |

The account email value, typed account email, and approval subject cells have no masks before dismissal, as explicitly requested. Sender and plan ID remain visible. Labels, count, date/size columns, warnings, checkbox, cancel, and confirmation controls remain native pixels. No replacement cursor or fabricated UI is drawn. The confirmation pointer/button area is unobstructed.

Closing animation masks, source PTS `[60.78,61.02)`: `(0,0,335,80)`, `(0,80,78,735)`, `(228,143,107,30)`, `(155,270,650,63)`, `(30,448,385,337)`, `(335,185,1335,650)`, `(0,80,335,55)`, `(0,243,335,27)`, `(0,335,335,75)`, `(0,785,335,30)`, `(1670,0,250,910)`, `(0,842,78,166)`.

The independent closing account-email, subject-column, and typed-email rectangles were removed. Broad union masks still protect moving IDs/digest and underlying terminal paths/sidebar/chat during this 0.24-second interval, including the profile avatar. The narrow `(228,143,107,30)` box protects a truncated local path in the underlying editor's Open Editors row; it incidentally covers part of the fading email. The broad central/right masks still incidentally cover subjects. These necessary masks temporarily cover nonessential labels too, but never the confirmation action. They do not make the underlying dialog stationary or replace it. They remain through two already-dismissed frames for safety.

Terminal aftermath masks, source PTS >=61.02: `(0,0,340,1008)`, `(1670,0,250,1008)`, `(340,185,1330,649)`. This covers profile/sidebar/chat and terminal commands, paths, account values, and identifiers while retaining safe terminal framing and native warning text. It does not purport to show a completed result.

Result crop: source `(400,472,980,440)`, excluding surrounding shell paths/account line. Unchanged value masks: account hash (`account_id`) `(200,96,755,29)`, digest `(214,151,755,27)`, approval ID `(212,178,500,27)`. All result labels, plan ID, status, and counts remain original pixels. Result PNG hash is unchanged.

Gmail crop: source `(340,180,1484,798)`, excluding browser identity, account avatar, sidebar and taskbar. ALL Gmail masks are removed, including the former `(396,200,982,598)` subject/snippet rectangle. Original subjects, snippets, sender names, dates, Trash-retention banner, `in:trash`, navigation and pagination remain visible throughout the recorded scroll and final hold. Hover states may temporarily show native action icons in place of a row's date. The hold is the exact decoded last Gmail frame, not fabricated UI.

## Evidence Limits

- Plan: `c147c7a16a1b407b8bb1b9db1e4d487b`; sender: `noreply@medium.com`.
- Native dialog says `TRASH`, exact messages `20`, `LIVE MAILBOX`. Trash is not immediate permanent deletion.
- Recorded result: `sender_run_finished`, `confirmed: 20`, `unknown: 0`, `skipped: 0`, `dry_run: false`; `fixture: null` remains visible.
- There is no separate failure counter. Do not turn absence of that field into a measured `0 failures` claim.
- Gmail shows original Medium subjects/snippets and sender rows/dates under `in:trash`, alongside another sender. Visible subjects can be compared with the native approval list, but pagination `1-50 of 106` is not a 20-message verification count. This is only a later visual check, not proof of all 20 exact IDs or a before/after delta.
- Source desktop times jump: approval 22:04, result 22:08, Gmail 22:10. Preserve the `Later` disclosures; this is not one uninterrupted execution.
- The earlier preview's release-disabled/Gate B statement is not resolved by this recording. These assets do not establish release-gate compliance.

## Verification

Regenerated all 18 contact sheets covering every exported frame: approval starts 000,030,...,390 (14 sheets); Gmail starts 000,030,060,090 (four sheets). Cells are left-to-right, top-to-bottom, with zero-based asset-frame labels. These current contact sheets were generated, NOT manually opened in this revision; the previous mask version's contact-sheet review is superseded and is not claimed as review of the current exports.

Full-resolution review after the final regeneration opened approval start 000, pointer/confirmation frame 381, closing-mask frames 384 and 389, the last closing-mask frame 391, and Gmail mid-scroll 60 and last frame 119. The result PNG was also inspected during this revision and retains its original hash. Additional approval frames 383/385/387/390/392/419 were inspected in the first regeneration, before the narrow closing-path correction; that inspection is not claimed as a final-hash review of those frames.

The first regeneration exposed a truncated editor local path after removal of the old broad closing email box. It was rejected and replaced with the narrow path-only protection above; final frames 384/389/391 were reopened to inspect that correction. The temporary unmasked closing reference was removed. Only the final hashes below identify the accepted assets. No remaining identifier/path exposure was detected in the final full-resolution frames inspected. Emails and subjects are intentionally visible and are not treated as privacy failures.

Regeneration decoded and audited all 540 exported video frames (420 approval + 120 Gmail), validated dimensions/count/duration and absence of audio, asserted solid-mask interiors (maximum allowed decoded RGB deviation 8), and recorded decoded frame hashes. Gmail has an empty mask list on every frame; its entire crop is source-identical before lossy encoding. The audit has source PTS, active mask boxes, pre-encode hashes, and source-pixel-identity assertions for each frame. Result PNG also passed a lossless decode round trip. The final `--verify` run passed for all four assets, source hash, metadata, audit coverage, and existence of 18 contact sheets. Automated pixel/mask checks are not a semantic privacy review of all text, and generated contact sheets are not a manual sign-off.

Audit: `out/review-organize-source-audit.json`. Sheets and edge PNGs: `out/review-organize-source-*`.

Source SHA-256 before and after, identical:

`7e7b680199bd8ea2f4f8d0bef5e46d5dc2c309cc2ebb0a9a43a5e880a3382eb0`

| Current verified asset | SHA-256 |
| --- | --- |
| Approval MP4 | `5188523f0561815a66b4067bd989e33be3542bdcffb82da48e630a3963bf95ca` |
| Result PNG | `b7dcce110a336f0859d1be0e9636790906e454b8ad84af92790b864da4566f2d` |
| Gmail MP4 | `812f7e7e7a31b9ecff84b525dc7476311a4249efd8cc258cbab8fb1d3b3377f7` |
| Gmail hold PNG | `1c0406341a083f720275b17c56f404efacd5ff19348aef9d7680390beeb93ade` |

Reproduce: `node scripts/prepare-review-organize-source.mjs`. Verify existing hashes/metadata/audit coverage without rebuilding: `node scripts/prepare-review-organize-source.mjs --verify`. Source hash is pinned: a different recording requires new mask review. Regeneration by itself is not visual sign-off.
