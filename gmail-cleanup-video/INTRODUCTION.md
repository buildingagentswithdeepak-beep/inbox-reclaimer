# Introduction: Less Repetitive Review

Separate 18-second composition `GmailIntroduction`, 1920 x 1080, 60 fps. The original hook composition and its output remain unchanged.

## Build

```powershell
npm run audio:intro
npm run typecheck
npm run stills:intro
npm run render:intro
npm run finalize:intro
```

Delivery: `out/gmail-cleanup-agent-introduction-18s-1080p.mp4`.

## Timeline

| Time | Visual |
| --- | --- |
| 0-4s | Full-screen animated typography, without presenter footage: Less repetitive review. Not less control. |
| 4-7s | Genuine supplied Gmail screenshot crop, with visibly separate fictional email rows and illustrative pointer navigation. |
| 7-11s | Gmail, Drive and Photos connect to one shared-storage allowance. No percentages or invented allocations. Both shared-storage and Trash caveats are visible. |
| 11-14s | Find, Review, Decide appear sequentially; human control remains amber. |
| 14-18s | Push into a single fictional project-update row, match cut on that row, and pull out to a simplified tidy inbox. Explicitly a concept illustration, not an execution or before/after claim. |

## Source And Limits

- Presenter footage was removed at the user's request. The opening is now animated text only; the source recording remains untouched and its earlier local derivative is unused.
- No voiceover is fabricated from the longer script, which does not fit in 18 seconds verbatim.
- Samples from `Timeline 1.mov` at 40, 100, 180, 260, 340 and 410 seconds showed presenter footage, not inbox navigation. This is not an exhaustive footage review.
- No genuine moving inbox recording was identified. The real screenshot is `C:\RockDeveloper\gmailagent\Problem.png`, cropped to x=0, y=128, width=1838, height=350 to omit browser profile and message details. Its storage price and date are historical as captured. Animated rows are explicitly illustrative, not passed off as genuine navigation.
- The final tidy inbox is an explanatory transition, not evidence of deletion or regained storage. No live Gmail access, confirmation, or cleanup action occurs.
- Source videos and screenshot remain unchanged. Only short/cropped derivatives are included under `public/`.

## Audio

Original continuous 100 BPM instrumental with gentle accents, no vocals or notification overload. Level dips by 4 dB for the storage caveat, leaving space for later narration. Start/end fades prevent abrupt cuts. See `INTRO-AUDIO.md` and `public/audio/intro-stats.json`. Encoded output measurements are in `out/introduction-verification.json`.

All animation uses frame-driven Remotion interpolation and easing. Media is local, fonts are bundled, and there are no CSS animations or wall-clock dependencies.
