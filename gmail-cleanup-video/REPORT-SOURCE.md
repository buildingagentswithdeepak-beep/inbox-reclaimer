# Report Source and Sanitization

## Sender Visibility Update

The user explicitly requested visible sender identities. The composition now uses `public/report-senders.mp4` for its 4-8s ranking shot: source 7-11s, same crop, 120 frames at30fps, no sender masking. The original sanitized derivative below remains unchanged for other excerpts; account/inventory identifiers are not reintroduced. Ranking privacy overlays and the blanket privacy-masked badge were removed. The following verification describes the retained sanitized derivative, not the now-visible sender excerpt.

## Deliverable

- Source: `out/Report.mp4`, unchanged.
- Derivative: `public/report-safe.mp4`.
- Verified output: exactly 16.000000 seconds, 480 decoded frames, constant 30/1 fps, 1894x876, H.264 encoded with libx264 CRF 17, yuv420p, square pixels.
- Silent: one video stream and no audio stream. Source metadata and chapters are not copied.
- MP4 faststart verified: `moov` precedes `mdat`.

## Cuts

Times are seconds; intervals include their start and exclude their end.

| Source interval | Output interval | Duration | Output frames |
| --- | --- | --- | --- |
| 0-4 | 0-4 | 4 seconds | 0-119 |
| 7-11 | 4-8 | 4 seconds | 120-239 |
| 14-22 | 8-16 | 8 seconds | 240-479 |

All excerpts play at normal speed. There are no crossfades, substituted stills, invented data, or extra holds. The source has irregular presentation timestamps despite its nominal 30 fps. Timestamp-based normalization to constant 30 fps precedes trimming; it duplicates/drops frames as needed without accelerating or slowing the recording.

## Crop and Permanent Masks

The same static crop applies to all excerpts: source `x=12, y=102, width=1894, height=876`. No scaling is applied to the video. All masks are opaque black rectangles burned into the encoded pixels, not blur or removable overlay tracks.

| Excerpt | Source-space rectangle (x, y, width, height) | Post-crop rectangle (x, y, width, height) | Active time |
| --- | --- | --- | --- |
| Opening identifier area | 60, 542, 1190, 436 | 48, 440, 1190, 436 | Source/output 1-4 seconds |
| Ranking, left sender column | 60, 102, 406, 876 | 48, 0, 406, 876 | Source 7-11 / output 4-8 seconds |
| Ranking, right sender column | 990, 102, 412, 876 | 978, 0, 412, 876 | Source 7-11 / output 4-8 seconds |

The opening mask covers account and inventory identifiers throughout their observed scrolling path, with conservative coverage of adjacent content. It begins before those identifiers enter the frame. Both ranking masks span the entire cropped height for the whole excerpt, covering all sender rows as they scroll. Their right edges extend through source x=465 and x=1401 respectively. Numeric ranking columns remain original; no replacement sender names or addresses are introduced.

The 14-22 second excerpt contains aggregate size/age tables, attachment-status text, and caveats in the inspected frames; no private addresses or identifiers were observed there, so no additional mask was applied. A small blank recording UI strip appears near the top late in that excerpt and is retained.

## Reproduction

The bundled tools are under `node_modules/@remotion/compositor-win32-x64-msvc`. Bundled FFprobe was used for stream and frame-count verification. Bundled FFmpeg was used for initial source-frame extraction, but its minimal build lacks `drawbox`, `setpts`, and `fps`. Rendering therefore used the full Windows x64 FFmpeg binary from the `eugeneware/ffmpeg-static` GitHub release `b6.1.1`, downloaded and unpacked only in the approved temporary directory. No project dependency or configuration was changed.

Exact `-filter_complex` graph:

```text
[0:v]setpts=PTS-STARTPTS,fps=30,split=3[a][b][c];
[a]trim=start=0:end=4,setpts=PTS-STARTPTS,crop=1894:876:12:102,drawbox=x=48:y=440:w=1190:h=436:color=black:t=fill:enable='gte(t,1)'[s0];
[b]trim=start=7:end=11,setpts=PTS-STARTPTS,crop=1894:876:12:102,drawbox=x=48:y=0:w=406:h=876:color=black:t=fill,drawbox=x=978:y=0:w=412:h=876:color=black:t=fill[s1];
[c]trim=start=14:end=22,setpts=PTS-STARTPTS,crop=1894:876:12:102[s2];
[s0][s1][s2]concat=n=3:v=1:a=0,setsar=1[v]
```

Output arguments:

```text
-map [v] -an -map_metadata -1 -map_chapters -1 -c:v libx264 -crf 17 -pix_fmt yuv420p -r 30 -fps_mode cfr -frames:v 480 -movflags +faststart public/report-safe.mp4
```

## Verification

- Read and visually inspected source frames at 0, 3.9, 7, 10.9, 14, 16, 18, 20, and 21.9 seconds.
- Also inspected opening frames at 1, 2, 2.5, 3, 3.5, and 3.966667 seconds, plus 4 fps contact sheets for the opening and final excerpts to check scrolling coverage.
- Extracted sanitized previews at output 0, 1, 2, 3.9, 4, 5, 7.9, 8, 10, 12, 14, and 15.9 seconds under `out/stills/report-check-*.png`.
- Read and visually reviewed full-size sanitized previews at 0, 3.9, 4, 5, 7.9, 8, and 15.9 seconds, and the complete 2 fps sanitized contact sheet `out/stills/report-check-contact.png`. No exposed private addresses or account/inventory identifiers were observed in these previews.
- Automated decoded-pixel audit checked the interior of the opening mask across all 90 active frames and each sender mask across all 120 ranking frames. Every checked pixel was black (maximum grayscale value 0/255); an 8-pixel edge inset excluded compression-boundary artifacts.
- Bundled FFprobe counted exactly 480 decoded frames, duration 16.000000 seconds, 30/1 fps, 1894x876, yuv420p, and no audio stream.
- Complete output decode passed with error-fatal checking and no errors. MP4 atom order was `ftyp, moov, free, mdat`.

Visual inspection is sampled, not an OCR-based guarantee for every source frame. Mask persistence was tested across every affected output frame. Unredacted inspection images remain outside the workspace in the approved temporary directory and are not deliverable previews. This document intentionally contains no sender addresses or identifier values.
