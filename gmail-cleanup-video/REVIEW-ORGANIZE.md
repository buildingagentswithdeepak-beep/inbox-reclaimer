# Review / Organize

Separate Remotion composition `GmailReviewOrganize`: 1920x1080, 60 fps, 1800 frames / 30 seconds. Preserves earlier scenes and original recordings.

## Edit

| Output | Content |
| --- | --- |
| 0-14s | Native confirmation, source 48-62s, continuous normal speed. Original acknowledgment, typing, pointer, button and dismissal. |
| 0-13s | Amber editorial boundary. No automatic approval or animated imitation of native controls. |
| 13-14s | Native window fully dismissed; editorial status becomes Confirmation recorded. Still Review. |
| 14-15s | Organize title and explicit Later: run result card; source time jump disclosed. |
| 15-24s | Original result held for reading; outline draws around actual counts. Summary says 20 confirmed, 0 unknown, 0 skipped. |
| 24-28s | Later Gmail Trash excerpt, source 86-90s, normal speed. |
| 28-30s | Exact decoded Gmail final frame held, explicitly labeled. |

Requested headings are preserved. All motion derives from Remotion frame time. No CSS transitions, random runtime behavior, reconstructed UI, animated selection rows, new folders/labels, or creator footage. Because real footage carries the action, no illustrative rows are needed or removed. Native 30 fps footage is embedded in the 60 fps composition without optical-flow interpolation.

Email addresses, subjects, and Gmail snippets are visible at the user's request. Internal IDs and local paths remain masked in derivatives; native sender/plan and relevant controls remain. The Gmail crop has no masks. Result metadata is not treated as a new remote mailbox observation. Later Gmail rows corroborate a visible Trash view, not all 20 exact IDs. The earlier release-gate discrepancy remains unresolved and is documented in REVIEW-ORGANIZE-SOURCE.md; no compliance claim is made.

Background: original restrained 90 BPM instrumental with quiet editorial accents, ducked for review. No voiceover, simulated mouse click or approval fanfare. See REVIEW-ORGANIZE-AUDIO.md.

## Commands

- `npm run typecheck`
- `node scripts/prepare-review-organize-source.mjs --verify`
- `node scripts/generate-review-organize-audio.mjs --verify`
- `npm run stills:review-organize`
- `npm run render:review-organize`
- `npm run finalize:review-organize`

Delivery: `out/gmail-cleanup-agent-review-organize-30s-1080p.mp4`. Verification: `out/review-organize-verification.json`.
