# Continuation Source Foundation

This is source extraction and provenance data, not a composition or a render. The only owned outputs are `scripts/prepare-continuation-source.mjs`, `src/data/continuation-code.json`, `public/building-agents-logo.png`, and this document. No application code, composition, Root, package file, credentials, or mailbox is modified or executed. No AGENTS.md was found in the applicable ancestor paths or script/source/public locations.

## Generate And Verify

From `gmail-cleanup-video` (the script also resolves paths independently of the working directory):

```powershell
node scripts/prepare-continuation-source.mjs
node scripts/prepare-continuation-source.mjs --verify
```

Generation uses Node built-ins only. It reads current Python files under `../src/inbox_reclaimer`, preserves each selected source line including indentation and its original line terminator, and serializes the resulting strings into JSON. No dedenting, hand-copied code, synthetic ellipses, code execution, or application import occurs. Incomplete blocks remain incomplete excerpts, not runnable examples. JSON escaping is serialization only; the decoded code string retains the source characters.

The manifest pins SHA-256 of each entire source file, not only the displayed lines. Every excerpt also has its own hash. An existing manifest is never silently refreshed when source, selections, timing, or logo change: generation and verification both refuse mismatched pins. Repinning requires deliberate review of the changed source and manifest. `--verify` performs no writes: it recomputes the manifest, compares all fields, checks every current whole-file hash and excerpt, checks the public logo against the supplied file byte-for-byte, and checks inputs again for changes during the operation. This is source/data verification, not a runtime application test or visual composition validation.

The logo is copied without conversion using `fs.copyFileSync` from `C:/RockDeveloper/BuildingAgentsLogo.png`. Both hashes and its byte length are recorded under `logo`. No replacement logo is generated.

## Schema

- `schemaVersion`: 1.
- `sourceRoot`: `..`, relative to the video project root, not the JSON directory.
- `sources[]`: repository-relative `file`, whole-file `sourceSha256`, `byteLength`.
- `excerpts[]`: unique `id`, repository-relative `file`, enclosing `symbol`, `language`, inclusive `startLine`/`endLine`, verbatim `code`, whole-file `sourceSha256`, `excerptSha256`, `highlightRanges[]`, `lineCount`, `maxLineChars`.
- `highlightRanges[]`: inclusive, absolute source `startLine`/`endLine`, not excerpt-relative indices. A later UI may highlight these lines without altering code.
- `maxLineChars`: Unicode code points in the longest selected line, including indentation and excluding its line terminator. Tabs count as one character, not a visual column. This is not a pixel-width measurement.
- `timeline`: seconds, start-inclusive/end-exclusive intervals, duration 39, five ordered `groups[]`, each with timed `cards[]` referencing excerpt IDs and a `single` or `paired` layout hint.
- `logo`: source and destination paths, source/output SHA-256 and byte length.

Syntax token highlighting, layout, font sizing, line-number gutters, camera movement, and composition wiring are deferred to the later UI task. Pairing is editorial metadata only. Keep actual file paths visible, especially root versus `sender/` names. Disjoint ranges must remain separate cards or explicitly labeled panels, never pasted together as apparently contiguous source.

## Timing And Excerpts

All file names below are relative to `../src/inbox_reclaimer/`. There are 15 independent excerpts rather than 14 so the executor's intent boundary and the journal's actual intent event are not conflated. The requested cancellation and writer ranges contain eight and nine source lines respectively; they are preserved intact rather than shortened dishonestly.

| Group | Card seconds | IDs | Source lines |
| --- | --- | --- | --- |
| 0-6 | 0-6, paired | `cli`, `read-workflow` | `cli.py:276-277`; `workflow.py:23-29` |
| 6-16 | 6-9 | `scan` | `sync.py:127-133` |
| 6-16 | 9-12 | `aggregation` | `analytics.py:159-165` |
| 6-16 | 12-16 | `render` | `render.py:174-177` |
| 16-26 | 16-19 | `selection` | `sender/selection.py:23-26` |
| 16-26 | 19-22 | `decision` | `sender/commands.py:61-68` |
| 16-26 | 22-26 | `writer` | `sender/commands.py:69-77` |
| 26-32 | 26-29, paired | `pause`, `checks` | `sender/workflow.py:90-94`; `sender/executor.py:101-106` |
| 26-32 | 29-32, paired | `intent`, `effect` | `sender/executor.py:125-129`; `sender/executor.py:135-140` |
| 32-39 | 32-36, paired | `journal-intent`, `outcome` | `sender/journal.py:846-852`; `sender/journal.py:898-902` |
| 32-39 | 36-39 | `transport` | `sender/gmail.py:234-239` |

The 39-second schedule is a code-tour timing plan, not a claim viewers can read every character. Emphasize the designated highlights; assess readability in the later composition. The generator reports longest-line character counts without silently wrapping or truncating source. The render excerpt intentionally ends before the long CSP expression.

## Verification Result

Generation and the subsequent read-only `--verify` both passed: 15 excerpts, 11 whole-file pins, contiguous 39-second schedule, and byte-identical logo. Maximum line lengths (including indentation) are: `cli` 56, `read-workflow` 46, `scan` 51, `aggregation` 48, `render` 92, `selection` 95, `decision` 94, `writer` 85, `pause` 107, `checks` 57, `intent` 89, `effect` 88, `journal-intent` 46, `outcome` 76, `transport` 83. The `pause` line is the widest and needs explicit layout review later; these counts are not a visual-readability sign-off.

Source and copied logo SHA-256: `488275a1707d040919d4f568c9fe2df289123b945981177f46e7bea0cde94746`.

## Accuracy Boundaries

- Root `workflow.py` is the read-only graph. The `analyze` CLI obtains inventory through it, then calculates and renders the report outside that graph (`cli.py:276-300`). Root `render_html` is the real symbol; there is no `renderreport` function.
- `sender/workflow.py` implements the approval interrupt. Native approval is captured outside the graph; the graph resumes using a validated journal approval reference, not user consent invented by LangGraph. Root and sender workflows must not be labeled interchangeably.
- Preview-only `sender-cleanup` saves a nonempty immutable plan and returns (`sender/commands.py:129-139`). It does not itself establish a paused graph. `_perform` prepares that graph before opening native confirmation (`52-61`). `sender-resume` opens an existing plan without re-enumeration. The timeline is a responsibility tour, not a literal call-order diagram.
- Cancellation (`61-68`) returns without writer construction. Approval persistence (`69`) precedes live writer construction (`75`) and executor construction (`76`). The omitted executor lines `130-134` handle guard rejection; the `intent` and `effect` panels are deliberately disjoint, not adjacent source.
- Sender selection is an independent Gmail sender search, not a subset of the earlier bounded analysis. The 1,000 cap counts inspected candidates, including exclusions/missing messages; safety thread reads are additional. No newest-first guarantee or per-message deselection UI is implemented. A smaller new preview is not guaranteed to be a subset of an old plan.
- Executor freshness includes read latency and is bounded to ten seconds (`sender/executor.py:78-81`). The later dispatch guard rechecks approval/protections/freshness. The short `checks` excerpt does not show the entire safety algorithm.
- `transport` shows Gmail `batchModify` adding `TRASH`, not permanent deletion. The executor currently sends one message at a time. A response alone is insufficient: `_effect` reads back metadata and confirms or records unknown (`sender/executor.py:140-155`). The selected `outcome` excerpt is the journal event, not the read-back verification code.
- `SenderJournal` uses the existing `journal.db` connection (`sender/journal.py:323-329`); it does not create another sender database. Graph checkpoints are in separate `checkpoints.db` (`profile.py:70-76`). Checkpoint state is not approval authority, and SQLite plus Gmail is not one atomic transaction.
- No runtime LLM integration was found in the audited source. The framework invokes graph nodes; deterministic Python aggregates metadata and existing Gmail labels. Do not depict a language model deciding what is unwanted.

## Source Copy Discrepancies

- `sender/render.py:99-100` still says live Trash/Restore is release-disabled, while `sender/models.py:27-32` reports `live_mutation_released=True` / `B_passed`, consistent with README's released sender path. Do not reproduce stale HTML prose as the current release decision or rewrite captured product pixels to hide it.
- `cli.py:25-27` global help still says no Gmail writes; `sender/commands.py:149-152` restore help says Gate B is not released. Root Gate A commands remain closed, while separate sender commands are released. These labels do not justify collapsing the two paths.
- A redacted sender preview does not guarantee a redacted resumed native window: `_perform` re-fetches metadata at `sender/commands.py:59-61`, and the confirmation table shows a present subject. Treat native-window subjects as sensitive in later recordings.

No live Gmail, OAuth, application tests, composition renders, or approval automation are part of this foundation task. Historical runtime evidence in README or other video notes is not newly verified by the extraction command.
