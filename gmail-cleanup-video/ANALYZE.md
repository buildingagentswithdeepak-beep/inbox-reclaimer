# Analyze Sequence

Separate Remotion composition `GmailAnalyze`: 1920x1080, 60 fps, 900 frames.

- 0-4s: actual recorded analysis command, including --redact-subjects and --max-messages 1000. Editorial flag callouts sit outside the capture.
- 4-10s: expanded recorded read-only output at normal playback speed.
- 10-11.3s: real category/summary excerpt; product window scales left while the external blue scan travels to the category highlights.
- 11.3-13s: Promotions, Social, Updates, Forums light sequentially. These are labeled editorial highlights, not product controls.
- 13-15s: hold the category highlights and no-permission message while the supplied excerpt continues.

The blue scan always sits outside captured pixels. All animation is deterministic and frame-driven with Remotion interpolation. Existing films and original recording are preserved. See ANALYZE-SOURCE.md for privacy treatment and source cut mapping; ANALYZE-AUDIO.md for original instrumental audio and measurement scope.

Build: `npm run typecheck`, `npm run stills:analyze`, `npm run render:analyze`, `npm run finalize:analyze`.

Delivery: `out/gmail-cleanup-agent-analyze-15s-1080p.mp4`.
