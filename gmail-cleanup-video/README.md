# Gmail Cleanup Agent: 18-second hook

Editable Remotion production, 1920 x 1080, 60 fps, exactly 1,080 frames. Original synthesized stereo instrumental music and notification accents included. No narration is baked in, leaving room for the creator's voiceover.

## Run

```powershell
npm ci
npm run audio
npm run studio
npm run typecheck
npm run stills
npm run render
npm run finalize
```

Final HD output: `out/gmail-cleanup-agent-18s-1080p.mp4`. The Windows finalize script copies the picture without re-encoding and encodes audio directly from the original lossless mix to enforce the exact delivery duration. It validates the 18-second container and 1,080-frame picture and checks decoded audio for clipping. `out/verification.json` contains final measurements.

Optional 3840 x 2160 export: `npm run render:4k`. Source elements are vector/DOM and bundled fonts, not enlarged screenshots.

## Edit map

| Time | Picture | Sound |
| --- | --- | --- |
| 0-4s | Three close framings of a fictional inbox; scrolling promotions; illustrative count grows | Restrained pulse, accumulating original notification tones |
| 4-8s | Privacy-cropped supplied Gmail screenshot showing the actual storage warning and offer | Music cuts at 4s; soft warning accent |
| 8-12s | Cursor approaches but never clicks upgrade; holds still; warning pulls away to unchanged inbox | Negative space; quiet pullback accent |
| 12-16.2s | Agent reveal; source-based analysis report and sender preview; workflow stops at Review | Warmer instrumental returns at 12s; restrained workflow accents |
| 16.2-18s | Same fictional inbox appears, then pulls back into an illustrated desktop monitor | Soft transition; final audio fade |

## Boundaries

- User's 18-second timing overrides the script document's older 20-second hook.
- Inbox and report recreations are labeled illustrative. The storage notice at 4-10.75s uses the supplied screenshot `C:\RockDeveloper\gmailagent\Problem.png`, cropped to x=360, y=280, width=1460, height=196. Only this privacy-safe crop is stored in `public/storage-warning.png`; the original remains unchanged.
- The screenshot's price and date are retained as captured and explicitly labeled not a current offer. Personal messages, browser profile and account details are excluded. Report recreation is source-based, not footage of the live product and not evidence of processing speed.
- No fabricated upgrade price, simulated purchase, auto-deletion, green approval state, or storage-recovery claim. Cursor hesitates over the screenshot's actual Get storage button without clicking.
- Shared Google storage caveat appears with the warning. Upgrade-avoidance caveat remains readable during 4-12s.
- Analysis uses a fictional 37-message sample. This count is deliberately distinct from the illustrative inbox total, and the report is labeled SAMPLE REPORT.
- Report structure follows `src/inbox_reclaimer/render.py` and `src/inbox_reclaimer/sender/render.py`; it has no invented approval button or per-message selection controls.
- Amber editorial highlights mean items worth reviewing, not classifier decisions. No message disappears.
- No creator footage was supplied. The final monitor is an explicitly illustrative handoff, not fabricated real footage. Replace with matched creator footage in the long-form edit if available.
- Audio is original synthesized material. See `AUDIO.md` for timing, provenance and measured levels. Full-length RMS is not a LUFS measurement.

## Implementation

All animation is a pure function of Remotion's current frame, with clamped interpolation and explicit easing. No CSS animation, wall-clock timing, live mailbox access or remote runtime asset loading. Fonts ship from local Fontsource packages. Music and SFX are independent 48 kHz WAV stems referenced through `staticFile()` and `@remotion/media`.

The Remotion 4.0 packages are pinned together. Consult Remotion's licensing requirements for your organization before commercial production.

Dependency audit at creation reports six high-severity entries from one transitive `source-map-js` advisory propagated through the CSS build tooling. The configured npm registry currently offers 1.2.1, while the advisory requires 1.2.2. Do not expose Studio publicly or process untrusted source maps. The delivered MP4 does not execute these dependencies. Recheck `npm audit` before reusing the build environment.
