# Suggest Sequence

Remotion `GmailSuggest`: 1920x1080, 60fps, 480 frames, 8 seconds.

- 0-2.3s: actual recorded sender-cleanup preview command without --execute; original wrapping preserved, prompt masked. Editorial sender label matches source.
- 2.3-4.5s: actual JSON crop. Highlight the saved plan ID, then approval_created:false and mail_changed:false.
- 4.5-8s: actual local HTML report summary, matched to recorded sender and plan. Account masked; internal IDs/digest excluded.
- 5.5-6.1s: restrained emphasis on the amber Awaiting review badge, followed by a stable ending for editorial cut.

No creator footage, per explicit user clarification. No approval or cleanup shown. Source stills are labeled held for readability; report screenshot is from the actual matching local HTML, not invented UI. Source uses a 20-candidate cap and its own sender search, not the earlier analysis sample. No Gmail commands executed in production.

Existing source has contradictory release-gate prose beyond the selected summary crops, documented in SUGGEST-SOURCE.md. The video only asserts the verified saved selection and unchanged mail, not current execution capability.

All animation uses deterministic Remotion frames; assets are local. See SUGGEST-SOURCE.md and SUGGEST-AUDIO.md for provenance and measurement scope.

Build: `npm run typecheck`, `npm run stills:suggest`, `npm run render:suggest`, `npm run finalize:suggest`.
Delivery: `out/gmail-cleanup-agent-suggest-8s-1080p.mp4`.
