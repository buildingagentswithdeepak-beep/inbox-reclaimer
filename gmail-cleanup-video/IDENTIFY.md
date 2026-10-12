# Identify Sequence

Remotion composition `GmailIdentify`: 1920x1080, 60fps, 600 frames, exactly 10 seconds.

- 0-1.5s: headline arrives; blue outline draws around only noreply@medium.com in the corrected browser report from ReportSender.mp4. Actual senders are visible at the user's explicit request; account details, paths, and internal IDs remain outside the crop.
- 1.5-2.5s: two fictional promotional messages are outlined as a candidate group.
- 4-4.8s: a fictional newsletter is outlined without classifying it as unwanted. All other rows remain visible, unchanged, and at full opacity.
- 6.5-7.5s: report shrinks upward to reveal a supported exact-sender preview command. Fictional inbox stays fixed.
- 7.5-10s: hold. Command is explicitly illustrative and not executed. No fabricated preview results, plan ID, or approval.

The final command is an illustrative bridge into the next scene, not a claimed recording of execution. It uses the requested `noreply@medium.com` sender and the source-supported `sender-cleanup --sender` contract without `--execute`. No command was executed. The fictional rows remain independent examples, not messages attributed to Medium.

Contract evidence: `../src/inbox_reclaimer/sender/commands.py:84-100,129-143`, `../src/inbox_reclaimer/sender/selection.py:23-40,53-102`, `../README.md:104-119`. Preview performs its own sender search, not a subset of earlier analysis. No Gmail command was run for this production.

See IDENTIFY-SOURCE.md and IDENTIFY-AUDIO.md for provenance and verification. All motion is frame-driven; local images and audio use Remotion components. Original recording and earlier videos are unchanged.

Build: `npm run typecheck`, `npm run stills:identify`, `npm run render:identify`, `npm run finalize:identify`.

Delivery: `out/gmail-cleanup-agent-identify-10s-1080p.mp4`.
