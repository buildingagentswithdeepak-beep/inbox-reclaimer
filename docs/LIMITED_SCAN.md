# Bounded mailbox preview — user-requested specification amendment

## Requirements

- Provide `reclaim analyze --max-messages 1000` to avoid a full metadata harvest.
- Read metadata for at most N distinct message IDs; stop enumeration when the cap is reached. Missing or invalid messages consume a slot; retries may repeat a request for the same ID.
- Retain mailbox-wide scope, including Spam/Trash. No email bodies or attachment contents.
- Keep read-only capability, quota reservation, account binding, subject redaction, private exports, and minimized Hermes output.
- Clearly label all preview outputs as partial. Never publish the preview as a reconciled full inventory or advance its history cursor.
- Preserve existing cache generations, in-progress full scans, journal plans, and protections.
- Default analysis remains the original full/incremental synchronization.

## Assumptions and limitations

1. “Latest” means the first distinct IDs in Gmail's returned listing order, not a guaranteed global timestamp top-N. Gmail discovery exposes no orderBy parameter or ordering guarantee. Sort the selected records by internalDate descending for deterministic presentation; this does not prove global recency. Disclose the ordering limitation in CLI help and reports.
2. Limit applies to individual messages, not conversation threads. A disappearing message consumes a slot, so fewer than N records may be reported.
3. Bounded previews are transient report inputs, not resumable inventory generations. No history replay, full-scan staging, or proposal input; rerunning begins at the first page. This prevents history from pulling older/unbounded metadata into the preview and preserves full-scan state.
4. Reject --cached, --full-resync, and --attachments with --max-messages before profile/credential access. These modes have incompatible coverage/read-budget contracts.
5. Use an opt-in positive integer rather than changing the default. Existing callers and proposals continue to require the original full inventory.

## Architecture / low-level design

- `SyncService.limited_scan(max_messages)`: reuse identity checks, cancellation, redaction and metadata validation; enumerate unique IDs up to the cap, with loop-token validation. No cache access/publication, thread reads, or history calls.
- `LimitedInventory`: explicit immutable subtype carrying message_limit, selected_count and enumeration_exhausted; complete=false and empty cursor. Full CacheStore publication rejects this type, even if a caller changes complete.
- CLI branches before constructing the resumable adapter. Existing reference-only LangGraph read workflow still runs; it stores opaque references only. Preview generations are ephemeral and not proposal inputs.
- Analytics emits scope, cap, selected count, enumeration exhaustion, persistence and ordering caveats. HTML shows a prominent preview badge and limit/count; terminal and JSON carry the same coverage contract. Hermes retains coverage but not raw identifiers/senders.
- Failures/cancellation produce no new report and cannot replace the committed full inventory. Missing messages remain unresolved. No OAuth or Gmail mutation changes.

## Spec traceability

| Requirement | Original spec / amendment | Verification |
|---|---|---|
| Bounded metadata read | User amendment above | Multi-page >1000 fixture, exact boundary, dedupe, missing records |
| Coverage accuracy | §4.2, §4.3 | Partial terminal/JSON/HTML/minimized outputs; no global-recency claim |
| Cache/cursor isolation | §4.2, §7, §9 | Prior full cache unchanged; staging unchanged; preview cannot be published |
| Identity/privacy | §4.1, §11.2 | Switched-account failure, subject redaction, minimized output |
| Closed write gates | §2, §14 Gate A | Existing full suite and proposal isolation |
| Existing full sync | §4.2 | Existing sync/staging/CLI regression suite |

## Actual validation results

| Check | Observed result |
|---|---|
| Test-first regression run | 33 expected failures before implementation (missing method/CLI option) |
| `pytest -q --junitxml=docs/evidence/limited-scan-junit.xml` | **208 passed in 36.34s**; [JUnit](evidence/limited-scan-junit.xml) |
| `ruff check src tests scripts` | All checks passed |
| Actual installed `reclaim.exe`, outside repo cwd, installed home helper, isolated temporary profile | 10 selected synthetic messages at limit 10; exit 0; full cache absent; no token created; [CLI evidence](evidence/limited-scan-cli.json) |
| Browser inspection of synthetic HTML | Prominent limited-preview and synthetic badges; 0 scripts, 0 remote assets, no horizontal overflow |
| Wheel/source build | Both built successfully; archive checks found no credential/profile database artifacts |
| Wheel installed in isolated target, imported outside source checkout | 3 synthetic messages at limit 3; exit 0; packaged CSS rendered; [package evidence and hashes](evidence/limited-scan-package.json) |

The 1,500-message unit fixture verifies exactly 1,000 metadata selections and two list pages, with no third page, history, thread or cache access. CLI/browser fixtures are separately labeled synthetic; their report counts are not mailbox observations.

## Evidence boundary

Automated verification uses synthetic mailboxes, temporary profiles and mocked Google transport only. No live Gmail preview or chronological ordering guarantee is claimed. Current discovery contract checked at https://gmail.googleapis.com/$discovery/rest?version=v1; listing parameters are maxResults, q, includeSpamTrash, userId, labelIds and pageToken.
