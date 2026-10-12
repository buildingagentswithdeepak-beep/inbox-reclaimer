# Inbox Reclaimer

**Local Gmail inventory and proposals, plus released sender Trash/Restore with native confirmation and a1,000-candidate cap.**

Built from `inbox-reclaimer-tech-spec.md` v2 and its bounded sender extension. **Sender Trash/Restore is production-enabled after release review, process/fault verification and the operator's verified live round-trip.** Every effect still requires a separately operated native confirmation, verified same-account modify grant and fresh safety checks. Permanent deletion and protection removal remain unavailable. Neither `--execute`, a CLI response nor a graph resume is consent. Follow [the production PowerShell runbook](docs/PRODUCTION_RUNBOOK.md); [the release decision](docs/SENDER_RELEASE_DECISION.md) records scope, review evidence and limitations. Enabling this build does not itself access or change your mailbox.

## Quick start — no mailbox access

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required.

```powershell
cd C:\Users\v-deegarg\inbox-reclaimer
uv sync --frozen
.\run-demo.cmd
```

`run-demo.cmd` uses the installed google-workspace `_hermes_home.py`, sets an isolated `.demo-profile` for its child process, and runs against **synthetic fixtures**, not your Gmail account. It does not change the parent shell's profile or any token. Pass the installed skill's scripts directory as its first argument if the helper lives elsewhere.

Open `.demo-profile\inbox_reclaimer\reports\report-demo.html` locally. The self-contained report has no scripts, tracking requests, external fonts or CDN dependencies. The attachment examples in demo mode are explicitly synthetic too.

If the PyPI file CDN is TLS-blocked on your network, the lock was generated and exercised using:

```powershell
uv sync --frozen --default-index https://pypi.tuna.tsinghua.edu.cn/simple
```

## Real read-only use (explicit operator action)

**Development verification does not access Gmail.** The following is an operator-run integration path, not a claim that your credentials or live Gmail have been tested.

Use an independent local terminal for raw reports and sender/subject lists. Running raw-output commands through a hosted agent conversation discloses their output to that provider. `--hermes` produces minimized aggregates/opaque references and suppresses raw lists and HTML exports.

```powershell
# Set this explicitly to the intended profile. The app delegates resolution to the installed helper.
$env:HERMES_HOME = 'C:\Users\v-deegarg\AppData\Local\hermes\profiles\coder'
$helper = 'C:\Users\v-deegarg\AppData\Local\hermes\hermes-agent\skills\productivity\google-workspace\scripts'
.\.venv\Scripts\reclaim.exe --workspace-scripts $helper analyze --redact-subjects --json
.\.venv\Scripts\reclaim.exe --workspace-scripts $helper propose --action trash
```

The adapter reads only `H/google_token.json` once. It does not search other profiles, change scope grants, replace token files, or launch OAuth. It validates actual access-token grant metadata with Google, binds the exact Gmail profile address plus OAuth client, and checks identity before reads/retries and after refresh. Missing or ambiguous grant metadata fails closed. A stronger existing grant does **not** enable writes. The journal remembers the single bound account and rejects unexplained switches; use a separate profile for another account.

An existing usable authorized-user token is required for analysis. For first-time read-only authorization, use the separate interactive helper below; it never replaces an existing token and cannot enable Gmail writes. Optional same-account Gmail-modify authorization is a separate local workflow described in the production runbook. There is no Drive quota reader or LLM transport.

### First-time read-only sign-in

Create a Google **Desktop app** OAuth client with Gmail API enabled and save its downloaded client JSON as `H/google_client_secret.json`. For an External app in Testing, add your Gmail address as a test user. Request only `https://www.googleapis.com/auth/gmail.readonly`.

Run directly in a local PowerShell window (not through a hosted agent):

```powershell
cd C:\Users\v-deegarg\inbox-reclaimer
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$env:HERMES_HOME = 'C:\Users\v-deegarg\AppData\Local\hermes\profiles\coder'
$helper = 'C:\Users\v-deegarg\AppData\Local\hermes\hermes-agent\skills\productivity\google-workspace\scripts'
uv sync --frozen --extra auth
.\.venv\Scripts\reclaim-auth.exe --workspace-scripts $helper --check
.\.venv\Scripts\reclaim-auth.exe --workspace-scripts $helper
```

The helper opens Google consent using a loopback callback, PKCE and a five-minute timeout. It requests only Gmail readonly, verifies actual grants and the Gmail profile, then asks you to type the exact verified email address locally. Only then does it atomically publish a private `H/google_token.json`. An existing file, unexpected scopes, client/account mismatch or failed validation blocks adoption. Google OAuth client/token contents and callback URLs must never be pasted into chat. Normal failures clean the private staging directory; a forced process kill can leave private `.oauth-*` staging under the app root. Cancelling locally does not automatically revoke a consent grant already made at Google.

`--check` validates local configuration without Google requests. Sign-in only reads grant/profile information; it does not enumerate mail. Successful sign-in does not authorize any mutation.

If no browser opens, use the explicit manual mode in the same local terminal:

```powershell
.\.venv\Scripts\reclaim-auth.exe --workspace-scripts $helper --manual-browser
```

Copy the complete sign-in URL shown there into a browser on the same computer. Keep the terminal running until the browser returns to the loopback callback, then type the verified email address at the terminal prompt. The URL is displayed only in this explicitly selected interactive mode; do not paste it into chat or logs. Each attempt has a new link and a five-minute timeout.

After success:

```powershell
$report = "$env:HERMES_HOME\inbox_reclaimer\reports\report-gmail.html"
.\.venv\Scripts\reclaim.exe --workspace-scripts $helper --timezone Asia/Kolkata analyze --redact-subjects --html $report
if ($LASTEXITCODE -eq 0) { Start-Process $report }
```

The helper deliberately has no token-replacement/reauthorization flag. If a token already exists but has expired or is invalid, stop and review that credential state rather than deleting it automatically.

### Quick bounded preview (up to 1,000 messages)

To avoid a full metadata scan, run this in the same local PowerShell window after successful sign-in:

```powershell
$report = "$env:HERMES_HOME\inbox_reclaimer\reports\report-gmail-preview.html"
.\.venv\Scripts\reclaim.exe --workspace-scripts $helper --timezone Asia/Kolkata analyze --max-messages 1000 --redact-subjects --html $report
if ($LASTEXITCODE -eq 0) { Start-Process $report }
```

If a full scan is already running, press **Ctrl+C once in that scan's terminal** before starting the preview. Its committed inventory and pending full-scan stage are preserved.

- Reads metadata for at most 1,000 distinct message IDs, including Spam/Trash; no bodies or attachment contents. Missing messages consume a slot. Retries can repeat requests for the same ID.
- Selects the first IDs returned by Gmail. **The API exposes no newest-first sorting guarantee**, so this is a listing-order preview, not a guaranteed global newest-1,000 selection. Sorting the selected metadata locally does not change that limitation.
- Terminal, JSON and HTML explicitly identify **partial coverage**. Totals describe only the preview, not your entire mailbox.
- Preview metadata stays in memory, apart from the requested report. It does **not** replace the full cache, advance its history cursor, or become input to proposals. Reference-only workflow checkpoints and quota accounting still operate normally.
- Each preview starts afresh; no history replay or full-scan resume. Omit `--max-messages` to return to normal full/incremental analysis. `--cached`, `status`, and `propose` still refer to the prior full inventory, if any.
- Cannot be combined with `--cached`, `--full-resync`, or `--attachments`.

See [bounded-preview design, assumptions and validation](docs/LIMITED_SCAN.md).

## Cleanup preview for one sender

After successful read-only sign-in, use the same PowerShell profile/helper setup above:

```powershell
$sender = 'newsletter@example.com' # Replace with the exact sender email address.
$report = "$env:HERMES_HOME\inbox_reclaimer\reports\report-sender-preview.html"
.\.venv\Scripts\reclaim.exe --workspace-scripts $helper sender-cleanup --sender $sender --max-messages 1000 --html $report
if ($LASTEXITCODE -eq 0) { Start-Process $report }
```

This is **preview-only**, not a deletion command. It searches for that sender directly; it neither requires nor overwrites a full-mailbox inventory. The cap applies to the first 1,000 distinct search candidates, including excluded/missing messages. Gmail search may match more broadly than exact sender equality, so each metadata record is revalidated. Safety thread reads are additional reads and can include other messages in those conversations. No email bodies or attachment contents are downloaded.

Starred, important, sent, drafts, existing Trash/Spam, protected senders, malformed metadata, failed safety reads, and threads with sent-message evidence are excluded. Subjects are redacted by default; use `--no-redact-subjects` only in an independent local workflow if you want transient subject samples in the private preview. Reports, exact sender addresses and message IDs remain sensitive.

`sender-cleanup --execute` requests an independently operated native confirmation window, **not automatic consent**. Live sender execution and optional Gmail-modify authorization are released. To execute the exact IDs from a prior preview, use `sender-resume --plan <saved-plan-id> --execute` rather than starting a new cleanup selection. The synthetic demo exercises fake effects only. There is no `--yes` or environment bypass of consent or protections.

`sender-restore --source-plan ID` previews restoration candidates from confirmed tool-trash evidence; its `--execute` path has the same release gate and needs its own native confirmation. `sender-status [--plan ID]` shows journal-backed outcome counts. Pending/unknown operations block further effects and require conservative review rather than blind retries.

See [sender-cleanup design and release requirements](docs/SENDER_TRASH_PLAN.md). Moving to Trash is not permanent deletion now; Gmail normally deletes Trash after 30 days. No permanent-delete capability is added.

## Commands

Global options precede the command: `--workspace-scripts PATH`, `--demo`, `--timezone Asia/Kolkata`, `--config PATH`, `--hermes`.

| Command | Behavior |
|---|---|
| `analyze [--full-resync] [--cached] [--json] [--html PATH] [--redact-subjects]` | Publish a reconciled metadata inventory and render local analytics |
| `analyze --attachments [--max-attachment-messages 1000]` | Separate opt-in MIME-name/decoded-size pass; no bodies or attachment content downloads |
| `propose --action trash [--promo-age 6m] [--min-batch-mb 100]` | Freeze uniquely assigned IDs into bounded, non-executable candidate batches |
| `propose --plan ID ...` | Explicitly request a new revision; previous membership remains immutable |
| `list --plan ID --revision N --batch ID [--page N]` | Local paginated membership, estimated sizes, cached subjects/dates |
| `confirm ... --action trash --reject` | Reject assigned IDs without moving them to other batches; no approval is created |
| `protect --sender ADDRESS [--reason TEXT]` | Add an account-scoped exclusion immediately |
| `protections list` | List protected senders locally, or a count with `--hermes` |
| `status [--plan ID]` / `reconcile` | Journal-backed status and recovery backlog; no mutation recovery in Gate A |
| `audit export --output PATH` | Replay journal events into an idempotent append-only JSONL export |
| `cache rebuild` | Atomically replace only metadata after successful full synchronization |
| `confirm` without `--reject`, `execute`, `restore`, permanent-delete proposals, `protections remove` | Refuse: later release gates / independent trusted human surface required |

Batch defaults not specified by the source are documented as assumptions: >10 decimal MB and older than one year; newsletter candidates older than one year; Promotions older than six months. Assignment priority is size/age → newsletter/sender → category/age. Batches default to at most 100 messages and at least 100 decimal MB. Small chunks below the minimum are omitted, never reassigned to a different owning rule. Other matching reasons remain explanatory tags.

`STARRED`, `IMPORTANT`, `SENT`, `DRAFT`, Trash, Spam, protected senders, malformed metadata and threads containing sent messages are excluded. Failed thread reads exclude candidates. The sent-thread check is a conservative heuristic, not proof that an owner has never replied. Proposals are not consent, predicted storage recovery or authorization.

## Privacy and persistence

All application state derives from the installed helper's `get_hermes_home()`:

```text
H/inbox_reclaimer/
  cache.db          rebuildable metadata, inventory cursor and scan staging
  journal.db        durable account, plans, protections and audit authority
  checkpoints.db   LangGraph opaque workflow references, never approval authority
  reports/ audit/ locks/ logs/
```

- Windows DACLs restrict application directories/files to the current account and SYSTEM; POSIX uses 0700/0600. SQLite is **not encrypted**. Use encrypted disks and protected backups.
- OS-held account locks serialize local sync/proposals/protection work. State on a network share is unsupported. Multiple machines sharing one mailbox are unsupported.
- Journal writes use foreign keys, WAL and `synchronous=FULL`; sealed membership is enforced in SQLite. Cache rebuild never deletes journal/checkpoints.
- `--redact-subjects` strips new subjects and Subject headers before persistence. It does not anonymize senders, IDs or old exports. Put `[privacy] redact_subjects = true` in the optional TOML to apply it by default.
- HTML escapes hostile headers/filenames and has a hash-bound content-security policy. Terminal strings strip escape/control sequences. CSV helper neutralizes formula prefixes; no CSV export command is exposed.
- No model calls, embeddings, telemetry or automatic unsubscribe. Graph tracing is explicitly disabled. Attachment filenames/size or SHA-256 equality never create deletion proposals.
- Interrupted full scans resume their persisted H0, pages and metadata on the next analysis. History and subsequent safety reads are always fresh. Ctrl+C leaves the committed generation intact; `cache rebuild` explicitly discards pending enumeration and starts fresh.
- Default retention removes app-named `reports/report-*.html`/`.json` after seven days and `logs/reclaim-*.jsonl` after fourteen days. Completed read-only checkpoints expire after thirty days, only with an intact journal and no pending/unknown operations. Custom-named or external exports need explicit cleanup. Journal evidence is never automatically deleted.
- Journal backup uses `JournalStore.backup(path)`, SQLite's consistent backup API. Never copy a live WAL database as a backup or treat the whole state directory as disposable.

## Quotas and time estimates

`reclaimer.example.toml` exposes versioned method costs, smooth/rolling pacing, effective project/user limits and an optional budget stop. The spec's defaults are inputs, **not a claim to have verified your project's current quotas**. Use the lower configured/effective limit. Large first scans can take hours. History replay and fresh thread checks add quota costs. No live completion-time SLA is promised.

Daily reservations are durable in the profile journal, so restarting the CLI cannot reset a selected daily budget. Initial identity reads use a conservative provisional profile bucket, adopted by the verified account. Reservation-before-dispatch can overcount interrupted reads; the ledger is not Google's billing meter. Minute pacing is process-local and cannot meter other applications sharing the Cloud project.

MB/GB mean decimal bytes. Cumulative size/age cohorts overlap; only disjoint bands can be added. Category overlap, unclassified mail, Trash/Spam and unique union totals are explicit. `sizeEstimate`, MIME size, decoded attachment bytes and Google account quota are different quantities.

## Engineering evidence

```powershell
uv run --frozen pytest -q
uv run --frozen python scripts/benchmark.py --output docs/evidence/benchmark.json
uv run --frozen ruff check src tests scripts
```

- [Implementation plan, assumptions and contracts](docs/IMPLEMENTATION_PLAN.md)
- [Architecture and low-level design](docs/DESIGN.md)
- [Spec traceability and validation evidence](docs/VALIDATION.md)

Automated tests use fake mailboxes and temporary profile roots. Runtime tests terminate a process at real journal/checkpoint boundaries and reopen the LangGraph workflow in another; they are not import-only checks. The operator's isolated-account live Trash/untrash/label-repair round-trip was separately verified through read-only journal evidence. No Gate C purge test or permanent-delete release is claimed. See the production release decision for current evidence rather than historical pre-release notes.
