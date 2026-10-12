# Clutter Arrives Gradually

Separate Remotion composition `GmailClutterAccumulation`: 24 seconds, 1920 x 1080, 60 fps / 1440 frames. No presenter footage. Existing hook and introduction remain unchanged.

## Render

```powershell
npm run audio:clutter
npm run typecheck
npm run stills:clutter
npm run render:clutter
npm run finalize:clutter
```

Final video: `out/gmail-cleanup-agent-clutter-24s-1080p.mp4`.

## Choreography

- 0-3s: clean fictional inbox with three messages and breathing room.
- 3-19.8s: 24 new rows arrive, with geometrically decreasing intervals. The recurring store, newsletter and community senders show repetition without implying that all promotional mail is unwanted.
- At 10.5s: the headline changes to "Promotional != automatically unwanted." The film renders the actual not-equal symbol.
- The fictional Northstar Studio project update remains anchored at the same coordinates from the first to last frame. The anchor is explicitly editorial, not a claimed automatic sorting feature.
- New rows push older rows below the viewport. No row is deleted, faded out, or removed from the mailbox; the count increases monotonically from 3 to 27.
- Last arrival at 19.8s settles by 20.14s. The entire picture is frozen from 20.5-24s, holding on the crowded inbox without a fade to black.

## Accuracy And Audio

All messages, counts, category badges and time passage are illustrative and labeled. No real account is accessed, no percentages or storage savings are shown, and no important mail is removed. There is no narration track.

Original 100 BPM instrumental gradually adds texture under accelerating soft notification accents. Faster arrivals use quieter pings to avoid overload. The ending settles to a pad-only bed with a final half-second audio fade. See `CLUTTER-AUDIO.md` for provenance and measured levels. Independent music and SFX stems and their exact lossless sum are stored in `public/audio/`.

All motion is driven by the current Remotion frame. No wall clock, CSS animations, nondeterministic randomness or remote runtime assets. The stills script compares frames at 21s and 23.98s byte-for-byte to verify the final visual hold. Finalization verifies exact video/container duration, frame count and decoded audio headroom.
