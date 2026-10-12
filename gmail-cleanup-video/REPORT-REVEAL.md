# Suggestions First: Real Report Reveal

`GmailReportReveal`: separate 19-second, 1920x1080, 60fps / 1140-frame Remotion composition. Existing scenes are unchanged.

## Output

`out/gmail-cleanup-agent-report-19s-1080p.mp4`

```powershell
npm run audio:report
npm run typecheck
npm run stills:report
npm run render:report
npm run finalize:report
```

## Edit

- 0-4s: overview from the supplied real report, held for readability and labeled accordingly. No synthetic report data or invented controls.
- 4-8s: actual sender ranking footage from source 7-11s, normal speed, sender identities visible at the user's explicit request. Uses `public/report-senders.mp4`; no identity overlays.
- 8-16s: actual aggregate tables from source 14-22s, normal speed. The wider recording is cropped into a readable editorial window, with no number substitution.
- The five-step editorial strip stays outside the report: Analyze illuminates blue at2s, Identify at5s, Suggest at8s. Review remains amber, with extra emphasis at11s; Organize remains inactive. This explains the workflow, not an execution progress indicator.
- 16-19s: cut to the text-only handoff chosen by the user: "Here's what I actually built underneath." No creator footage or fabricated speech.

The report is a read-only limited inventory, not a storage recovery forecast. An analysis does not authorize cleanup. The first frame is frozen for readability, not presented as live processing. Source audio is removed; there is only original background music and restrained accents, with a4dB dip under the ending and a final fade. No voiceover is baked in.

See `REPORT-SOURCE.md` for source provenance and permanent privacy masks, and `REPORT-AUDIO.md` for the original soundtrack and measurements. `out/Report.mp4` remains untouched. All animation is frame-driven and seek-safe.
