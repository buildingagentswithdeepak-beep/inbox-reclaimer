# 📘 Inbox Reclaimer — Technical Specification

**Version:** 2.0 — consolidated safety review revision
**Status:** Design revised; analysis/proposals first. Mutation capabilities remain disabled until their release gates pass.
**Target:** Local Gmail reclamation tool integrated with the installed Hermes google-workspace skill; LangGraph orchestration.
**Scope of this document:** Specification only. No OAuth setup, Gmail access, deletion, or application implementation is implied by its creation.

---

# 📘 1. Problem Statement

A Gmail account owner needs to identify storage-heavy mail, review bounded cleanup proposals, and reclaim space without accidentally deleting important correspondence. The workflow must distinguish reversible trashing from irreversible permanent deletion.

Required analysis:
- Top 20 senders by message count and separately by summed message size estimates.
- Storage estimates for Promotions, Social, Updates, and Forums, with other mail and Trash/Spam separately visible.
- Newsletter candidates identified by List-Unsubscribe headers.
- Messages larger than 5 MB, 10 MB, and 25 MB.
- Messages older than one, two, and five calendar years.
- Possible duplicate large attachments, clearly separated from deletion recommendations.

Users: one account owner per Hermes profile in v1. Detecting an account switch is mandatory even though multi-account orchestration is out of scope.

The report explains estimated message storage, not exact Google quota accounting. Gmail sizeEstimate is an estimate; message MIME size, decoded attachment size, and account storage usage are distinct quantities. No recovery percentage is promised.

IMAP is not rejected for lacking size operations: IMAP supports size-related operations. Gmail API is selected for its message IDs, labels, history feed, and explicit mutation methods. Gmail has no application-level emptyTrash method in the proposed adapter: permanent deletion uses message-delete APIs after a separately approved purge stage. Endpoint behavior must pass the verification gates in Appendix A.

---

# 💡 2. Proposed Solution

A local Python application with a deterministic four-phase workflow:

| Phase | Behavior | Gmail writes |
|---|---|---|
| Analyze | Synchronize metadata and produce terminal/JSON/HTML reports | None |
| Propose | Build immutable, non-overlapping candidate batches and advisory attachment findings | None |
| Confirm | Show action, account, exact membership, sample subjects/dates, full-list option, and consequences; capture trusted human decision | None |
| Execute | Execute only the approved action, with fresh safety reads, durable intent, reconciliation, and outcome reporting | Gated |

**Release scope:**
- **Gate A: analysis/proposals.** First deliverable; no Gmail mutation tool exposed.
- **Gate B: trash/restore.** Enabled only after approval, journal, locking, restoration, and crash-recovery tests pass, including isolated-account live tests.
- **Gate C: permanent delete.** Disabled until action-specific OAuth, fresh purge approval, provenance, and uncertain-outcome tests pass separately.
- **Attachment-based deletion is excluded from v1.** Filename/size and content-hash matches are advisory only.
- **No global trash purge in v1.** There is no command to sweep pre-existing Trash.

Dry-run is the default for every mutation command, including restore. A dry-run record can never authorize or establish eligibility for a later real mutation. Feature flags select capabilities; they do not substitute for user approval or test gates.

---

# 🧱 3. System Architecture

**Style:** Local modular monolith. A single account does not justify Kubernetes, Kafka, or separate microservices. LangGraph supplies workflow persistence; deterministic domain services enforce authorization and execution invariants.

```text
Local CLI / trusted confirmation UI       Optional Hermes advisory interface
                 |                             | read-only, minimized output
                 +-------------+---------------+
                               |
                   LangGraph orchestration
          analyze → propose → request decision → validate approval
                               |
                   serialized execution service
             safety reads → durable intent → Gmail → reconcile
                               |
        +----------------------+-------------------------+
        |                      |                         |
   cache.db                journal.db              checkpoints.db
   rebuildable          execution authority          workflow only
                               |
                         audit JSONL export
```

- **API layer:** Gmail REST adapter and local CLI. Optional Drive quota reader requires separately consented scope; it is not needed for Gmail-only operation.
- **Services:** sync, analytics, proposal builder, protection policy, trusted approval capture, executor, restore, recovery, and audit export.
- **Data layer:** SQLite databases with distinct responsibilities. Only metadata cache is rebuildable. Journal loss is loss of execution evidence, not a normal cache reset.
- **Agent layer:** LangGraph, with no LLM required. Optional LangChain model integration is limited to advisory output and never decides authorization.
- **Single mutation implementation:** all enabled mutation commands dispatch through the same executor and account lock. No parallel hand-written orchestration fallback.

---

# 🧩 4. Component Design

## 4.1 Gmail and identity adapter

**Purpose:** OAuth capability validation, account binding, paginated reads, bounded mutations, and quota enforcement.
**Stack:** Python, google-api-python-client/google-auth, installed OAuth/path integration.
**Interfaces:** resolve_identity(), validate_capability(action), list_message_ids(), get_metadata(), get_thread(), read_history(), trash_ids(), untrash_message(), modify_message(), delete_ids(). These are application interfaces, not claims about existing skill verbs.
**Dependencies:** credentials resolved under the active Hermes home; quota configuration; account lock; journal.

Each connection is bound to the account returned by users.getProfile. Use a validated OIDC subject if the integration explicitly obtains one; otherwise bind to the Gmail profile email and OAuth client/project context. Never normalize Gmail dots or plus-addresses into identity. An unexplained email change is an account mismatch, not an automatic migration.

Validate identity at command start, before each mutation chunk, and after credential refresh/reload. A token from another account stops execution. Missing/ambiguous identity fails closed. Load credentials once per execution session; do not silently switch to a replaced token file. Current documented quota values and configurable limits are in §10.

## 4.2 Metadata synchronization

**Purpose:** Build a consistent-enough, timestamped analysis inventory without skipping changes during long scans.
**Interfaces:** full_sync(), incremental_sync(), invalidate_thread(thread_id).
**Dependencies:** Gmail adapter, cache.db, per-account synchronization lock.

Full sync protocol:
1. Resolve account, capture a starting history boundary H0 **before enumeration**, and create a staging generation. Do not advance the committed cache cursor yet.
2. Enumerate messages with maxResults=500 and pagination. Omit the q parameter, rather than supplying an empty string. Use includeSpamTrash=true for storage reporting; proposals later exclude pre-existing Trash and Spam.
3. Retrieve metadata including IDs, threadId, internalDate, sizeEstimate, labels, From, Subject, Message-ID, In-Reply-To, References, List-Unsubscribe and List-Unsubscribe-Post. Handle a message disappearing during scan as missing, not scan failure or deleted-by-us evidence.
4. Replay users.history.list from H0 through all pages. Handle messagesAdded, messagesDeleted, labelsAdded, and labelsRemoved. Deduplicate IDs and refresh affected messages from current state; tombstone deleted IDs. Do not rely solely on the generic history.messages array.
5. Invalidate cached sent-thread/protection observations for every affected thread, including deletions and SENT-label changes. If the thread cannot be resolved, invalidate the account's thread cache conservatively.
6. Atomically publish the staging generation and resulting history cursor H1 in cache.db after the replay completes. Changes after H1 are consumed next time. History IDs are opaque strings, not consecutive integers.
7. If history has expired (404), discard the incomplete generation and begin a new full sync. Do not publish an advanced cursor over unapplied events.

Incremental sync uses the committed cursor; apply additions, removals, label updates and thread invalidations with the new cursor in one transaction, or idempotent staged pages followed by atomic publication. A crash leaves the previous committed cursor intact.

Enumeration is not a point-in-time Gmail snapshot. Report scan start/end, cursor, unresolved records and coverage; refuse new executable plans from incomplete scans. Mutations always use fresh safety reads, not cache freshness alone.

Attachment analysis is a separate opt-in read pass: inspect MIME parts for large candidate messages. Filename plus decoded size identifies possible matches only. Optional SHA-256 of downloaded decoded bytes confirms equal attachment content, not redundant messages. Stream downloads, enforce size limits, and delete temporary files promptly. Never treat attachment IDs as globally stable content hashes.

## 4.3 Analytics and report renderer

**Purpose:** Offline aggregation over a published inventory generation.
**Stack:** SQLite SQL, Rich terminal output, escaped local HTML with packaged assets; no remote script/CDN requirement.
**Interfaces:** top_senders(), categories(), newsletters(), size_cohorts(), age_cohorts(), attachment_findings(), render_report().

Rules:
- Preserve raw From separately from parsed address; malformed senders form an unknown bucket. Do not merge unrelated mailbox addresses.
- Newsletter classification is a header-derived candidate signal; it does not mean disposable.
- Thresholds use decimal bytes: MB means 1,000,000 bytes and GB means 1,000,000,000 bytes. Display GiB separately only when labeled.
- Use internalDate and a frozen report cutoff in the configured timezone. Calendar-year/month subtraction has explicit end-of-month clamping, including leap days.
- Size/age threshold cohorts are cumulative and overlap. Also provide disjoint bands for additive charts. Never add cumulative cohorts into a grand total.
- Category label totals are label-derived; if categories overlap, show overlap explicitly. Report unclassified mail, Trash, Spam and union totals separately rather than calling all unclassified mail Primary.
- Sender/category reports count each message once within a cohort. Distinct union IDs determine mailbox and reclaimable totals.
- Attachment findings never contribute to deletable-byte totals. Deleting an email deletes its body and all attachments, not just the matched part.

## 4.4 Proposal and protection service

**Purpose:** Immutable bounded batches with one owning batch per message per proposed action.
**Interfaces:** build_revision(), list_batch(), check_protection(), protect_sender().
**Batch kinds:** SENDER_NEWSLETTER, SIZE_AGE, CATEGORY_AGE. No attachment-deletion kind.

Non-overridable eligibility exclusions for trash/permanent delete:
- STARRED, IMPORTANT, SENT, DRAFT and unsupported message types.
- A current thread containing any SENT message, as a conservative replied/conversation heuristic.
- Sender listed in account-scoped sender_protections, including protections added after planning.
- Missing or malformed information needed for the checks, or a failed required safety read.
- Pre-existing Trash/Spam for ordinary trash proposals. Purge uses its own provenance-bound proposals.

The SENT-thread heuristic has false positives and can miss replies whose sent evidence was deleted, moved to another account, or threaded differently. Describe it as a heuristic, not proof that a user never replied.

Overlap policy: assign each eligible message to a single batch using deterministic priority SIZE_AGE → SENDER_NEWSLETTER → CATEGORY_AGE, then a stable rule-ID tie-breaker. Preserve other matching reasons as explanatory tags. Freeze assignment before confirmation. Counts and estimated bytes are computed over the assigned unique IDs.

A rejected batch rejects its assigned IDs for that plan/action. Do not silently move those IDs to another batch. Reconsideration requires an explicitly requested new revision and fresh confirmation. Membership cannot grow after approval; safety checks may shrink actual execution to a subset and must report the skipped IDs.

## 4.5 Executor: authorization, protections, and durable writes

**Purpose:** One account-serialized mutation path, backed by journal.db rather than LangGraph state or JSONL.

### Authorization envelope

Each approval binds all of:
- Authenticated account identity and OAuth client/project context.
- Plan ID, immutable revision, batch ID, and digest of the canonical message-ID set.
- Exact action: trash, permanent_delete, or restore. Restore additionally binds original operation IDs and intended label repair.
- Policy version, issued_at, expires_at, approving principal, trusted source event, one-time challenge ID, and decision.

Hash canonical JSON containing account, revision, action, sorted unique IDs, and relevant policy/source-operation IDs. A hash detects changes; it is not evidence of human consent.

Default approval lifetime: 15 minutes, a product policy rather than Gmail behavior. Validate at every dispatch/retry; stop and request fresh approval if it expires. Record expired/revoked approvals; never extend them automatically. Changing action, account, revision, or membership requires fresh approval. Approving trash does not approve permanent deletion. Neither --execute nor a graph resume value is approval evidence.

Trusted confirmation displays the account, action and consequences, batch revision, count, digest, sample subjects/dates, and full paginated list. Trash confirmation warns that Gmail may automatically delete trashed messages after its retention period. Permanent-delete confirmation explicitly states irreversibility and requests a separate action-specific user response. Persist the original trusted UI event, not a model's interpretation alone.

For v1 mutations, approval capture must happen outside model-controlled tool input: a user-operated local confirmation surface or a host-authenticated approval callback. The model can request a prompt and relay an opaque approval reference, but cannot mint approved records. Plain CLI text/stdin executed by an autonomous agent is not a trusted human event. If a host cannot establish this separation, its conversational mutation capability stays disabled; use the independently launched local workflow.

### Required checks before both trash and purge

Before **each** small mutation chunk:
1. Acquire/hold the per-account executor lock; validate account, feature gate, granted scopes, journal integrity and action-bound approval.
2. Re-fetch current message labels and sender data; fetch each distinct candidate thread again for SENT evidence. Consult the latest sender_protections. These checks are mandatory, not an opt-in flag.
3. Skip a message if any required check fails, is ambiguous, or cannot complete. No successful read means no write for that message.
4. For purge, additionally require current TRASH membership and a linked **confirmed non-dry-run trash operation**, with no later restore operation or observed external untrash. Reconcile uncertain preceding operations first. A dry-run or unknown trash operation never establishes provenance. Pre-existing Trash is not eligible.
5. Reserve quota before the final reads; if dispatch is delayed beyond the configured short safety-read age, repeat checks. Use small dispatch chunks; do not safety-scan a whole mailbox and mutate hours later.

There remains a small read/write race: Gmail does not provide an atomic compare-and-delete operation for these checks. A concurrent external star, reply or restore after the final read may race the write. This is explicitly disclosed; the application promises fail-closed checks, not absolute protection against concurrent Gmail clients.

### Write protocol

1. In a journal.db transaction, persist operation intent and pre-image **before calling Gmail**. Include account, approval ID, action, exact IDs, original labels, source trash operation, expected transition and dry-run=false. Initial state is pending. Commit durably.
2. Make the Gmail call outside the database transaction. A database transaction cannot include Gmail atomically.
3. In a second journal transaction, append the response/observation event and update per-message outcomes: pending, confirmed, unknown, failed or skipped. Persist available post-images and evidence attribution.
4. Export append-only JSONL from committed journal events using stable event IDs. Export/checkpoint failures must not erase the journal; replay exports idempotently on restart.
5. Advance workflow state only after journal reconciliation. Graph checkpoints may lag; they never override the journal.

If the process dies with pending operations, classify them unknown on restart and reconcile before further mutation. A timeout/disconnect may mean Gmail already changed. Never blindly replay a write simply because a graph node restarted.

Trash implementation: use bounded messages.batchModify(addLabelIds=["TRASH"]) with no intentional removal of INBOX/UNREAD. Treat server-side label behavior as a live-test gate, not proof that untrash automatically restores all labels. Verify resulting labels and retain the pre-image.

Purge implementation (Gate C only): bounded messages.batchDelete for approved IDs with valid current provenance. This is a single JSON request, not a multipart batch with per-ID statuses. No atomicity assumption. On request failure or uncertain response, inspect each member; only still-present, still-eligible IDs can enter a new, journaled per-ID messages.delete attempt under a valid approval. See §13 for absent-message handling.

## 4.6 Restore and audit

**Purpose:** Restore tool-trashed mail without overwriting unrelated user changes, and provide durable action evidence.
**Interfaces:** request_restore(), execute_restore(), reconcile_unknown(), export_audit().

Restore takes the same per-account lock as purge and uses its own explicit approval and write intents. Skip permanently missing messages and report them as unavailable. For eligible messages:
1. Record pre-restore state; call untrash if still needed.
2. Re-read labels and reconcile supported mutable labels using the original trash pre-image and confirmed tool-owned changes. Re-add labels lost by the trash transition, including INBOX/UNREAD when appropriate; remove only labels demonstrably introduced by the tool.
3. Never replace the entire current label set with the old set. If history or current observations show conflicting external edits, preserve them and report a restore conflict for review. Unsupported/deleted custom labels are reported, not recreated silently.
4. Journal each untrash and repair step so crashes are recoverable independently.

Acceptance: in an unchanged mailbox, restored labels equal the original pre-image. With concurrent user edits, preserve those edits or stop for review rather than claiming an exact round-trip. Pure untrash is an optimization only if no repair is needed; it is not the restoration contract.

The execution journal is authoritative for what was attempted, acknowledged and observed. JSONL is a regenerable local audit export, not an authorization database. Neither export presence nor an absent Gmail message alone proves the tool permanently deleted it.

---

# 🤖 5. Agent Design

## 5.1 LangGraph orchestration

Use StateGraph for resumable transitions and interrupt()/Command(resume=...) for pauses. LangChain is optional for read-only advisory model calls; no general-purpose model agent receives Gmail mutation credentials/tools.

```text
analyze → propose → select_batch
                    ├─ no batches → summarize
                    └─ request_action_confirmation [interrupt]
                         → verify_trusted_approval
                         ├─ rejected/invalid/expired → record outcome / request fresh decision
                         └─ approved → execute_or_dry_run → reconcile → next batch
```

Purge is a distinct action workflow after confirmed trash, not a boolean appended to a previous approval. Restore also uses the same approval verifier/executor. In the analysis-only release, graph mutation edges are unavailable.

Persist only account ID, plan/revision/batch IDs, approval references, cursors and operation IDs in graph state. Render samples through the local UI from cache/report records; do not serialize raw subjects or full message lists into checkpoints by default. A list request is read-only and leaves the approval challenge pending.

Interrupt nodes are side-effect-free before interrupt. On resume, interrupted nodes can run again from their beginning. Approval capture occurs outside the replayed node; verification consumes an existing trusted approval reference. Execution nodes contain no interrupt and consult the journal before any external write.

Graph replay/time travel is inspection-only for completed mutation workflows. A replay cannot create a second authorization or resurrect consumed operations. The executor remains the guard even if graph state is manually resumed.

## 5.2 Checkpointer lifetime and paths

The following is an integration function, not a complete application or a claimed executed LangGraph demo. The host supplies a built StateGraph, validated invocation input, and a workflow ID; no undefined globals are used. It belongs beside the installed skill's _hermes_home helper. Pin and exercise the library version before adopting this interface.

```python
from pathlib import Path
from _hermes_home import get_hermes_home
from langgraph.checkpoint.sqlite import SqliteSaver


def invoke_workflow(builder, invocation_input, workflow_id: str):
    root = Path(get_hermes_home()).expanduser().resolve() / "inbox_reclaimer"
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / "checkpoints.db"
    config = {"configurable": {"thread_id": workflow_id}}
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        app = builder.compile(checkpointer=saver)
        return app.invoke(invocation_input, config=config)
```

All graph operations using that saver occur within its context. Reopening a workflow uses the same database and workflow ID, with account/revision validation in the domain layer. Directory creation is subject to private permissions in §11.

**Hard pre-implementation library gate:** pin versions, compile a tiny non-destructive graph, create a checkpoint, pause with interrupt, close the saver and process, restart a second process, inspect the persisted state and resume with Command. Assert that the resumed decision is correct and no fake side effect executes twice. Repeat for reject, list navigation and invalid/expired approval. An import-only test is insufficient. This runtime gate is not claimed passed by this document.

## 5.3 Memory and trust

- Short-term workflow memory: checkpoints.db with opaque references, not approval authority.
- Long-term product state: journal.db approvals, operations, protected senders and policy versions.
- Mailbox metadata: cache.db; raw subjects need not appear in graph state or journal.
- Hermes conversation memory: opt-in advisory summaries only, under the disclosure rules in §11.
- No standing deletion consent; remembered sender protection can narrow eligibility, never authorize deletion.

---

# 🔄 6. Data Flow

1. Resolve active Hermes home and authenticate identity/capabilities without changing existing tokens.
2. Capture pre-scan history boundary, harvest and replay changes, publish inventory plus cursor atomically.
3. Generate report with coverage, overlapping-cohort warnings, estimated sizes and advisory attachment findings.
4. Create immutable plan revision and disjoint owning batches. Export/list operations do not change membership.
5. Request a human action-specific decision through a trusted surface; record approval or rejection with exact scope and expiry.
6. Dry-run: evaluate eligibility and record simulation results only. Do not create real trash provenance.
7. Real execution after gate: lock account → validate approval/account → fresh protections → durable intent → Gmail call → record/reconcile result → JSONL export → checkpoint reference update.
8. Purge: create a fresh permanent_delete revision from confirmed eligible trash operations, obtain new explicit approval, and repeat all checks. Never reuse trash approval.
9. Restore: separately approved operations, same lock, durable untrash and label-repair steps, then invalidate purge eligibility for restored messages.
10. Summarize counts, estimates and uncertainty; optional quota readings include observation times and lag warning.

---

# 🧮 7. Data Model

Three profile-local stores:
- **cache.db:** account-keyed inventory generations, message metadata/labels, MIME attachment observations, thread observations, sync cursor. Rebuildable, but sensitive.
- **journal.db:** sole transactional authority for plans, approvals, sender protections, mutation intents/outcomes, audit events and export cursor. Not disposable.
- **checkpoints.db:** LangGraph-managed schema; reference-only workflow checkpoints, not a replacement for journal.db.

All stores use account-scoped keys. SQLite foreign_keys=ON, WAL, synchronous=FULL for journal writes; private local filesystem only. Do not place journal/locks on an unsupported network share.

Core journal schema (additional indexes/migrations may extend it):

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE accounts (
  account_id TEXT PRIMARY KEY,
  gmail_identity TEXT NOT NULL,
  oauth_client_id TEXT NOT NULL,
  identity_subject TEXT,
  UNIQUE(gmail_identity, oauth_client_id)
);
CREATE TABLE plans (
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  plan_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('trash','permanent_delete','restore')),
  policy_version TEXT NOT NULL,
  inventory_generation TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('draft','sealed','superseded','closed')),
  PRIMARY KEY(account_id, plan_id, revision)
);
CREATE TABLE batches (
  account_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  batch_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN
    ('SENDER_NEWSLETTER','SIZE_AGE','CATEGORY_AGE','PURGE_CONFIRMED_TRASH','RESTORE')),
  membership_digest TEXT NOT NULL,
  message_count INTEGER NOT NULL,
  estimated_bytes INTEGER NOT NULL,
  PRIMARY KEY(account_id, plan_id, revision, batch_id),
  FOREIGN KEY(account_id, plan_id, revision) REFERENCES plans(account_id, plan_id, revision)
);
CREATE TABLE batch_members (
  account_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  batch_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  source_operation_id TEXT,
  PRIMARY KEY(account_id, plan_id, revision, message_id),
  FOREIGN KEY(account_id, plan_id, revision, batch_id)
    REFERENCES batches(account_id, plan_id, revision, batch_id)
);
CREATE TABLE approvals (
  account_id TEXT NOT NULL,
  approval_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  batch_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('trash','permanent_delete','restore')),
  membership_digest TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  challenge_id TEXT NOT NULL UNIQUE,
  decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
  issued_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  evidence_json TEXT NOT NULL,
  PRIMARY KEY(account_id, approval_id),
  UNIQUE(account_id, source_event_id),
  FOREIGN KEY(account_id, plan_id, revision, batch_id)
    REFERENCES batches(account_id, plan_id, revision, batch_id)
);
CREATE TABLE operations (
  account_id TEXT NOT NULL,
  operation_id TEXT NOT NULL,
  approval_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('trash','permanent_delete','restore')),
  step TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  source_operation_id TEXT,
  dry_run INTEGER NOT NULL CHECK(dry_run IN (0,1)),
  state TEXT NOT NULL CHECK(state IN ('pending','confirmed','unknown','failed','skipped')),
  reason TEXT,
  attribution TEXT,
  preimage_json TEXT NOT NULL,
  postimage_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(account_id, operation_id),
  UNIQUE(account_id, approval_id, message_id, step, attempt, dry_run),
  FOREIGN KEY(account_id, approval_id) REFERENCES approvals(account_id, approval_id),
  FOREIGN KEY(account_id, source_operation_id) REFERENCES operations(account_id, operation_id)
);
CREATE TABLE journal_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  operation_id TEXT,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(account_id, operation_id) REFERENCES operations(account_id, operation_id)
);
CREATE TABLE export_cursors (
  export_name TEXT PRIMARY KEY,
  last_event_id INTEGER NOT NULL
);
CREATE TABLE sender_protections (
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  sender_address TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY(account_id, sender_address)
);
CREATE INDEX operations_recovery ON operations(account_id, state);
CREATE INDEX operations_provenance ON operations(account_id, message_id, action, dry_run);
CREATE INDEX approval_scope ON approvals(account_id, plan_id, revision, action);
```

Additional required invariants enforced by domain transactions and tested migrations:
- Seal plans and memberships before approval. Reject mutation of a sealed revision with database triggers or equivalent immutable repository enforcement plus digest validation at dispatch.
- Approval account/action/digest/policy must equal the referenced plan and batch; SQL foreign keys alone do not establish that equality or human provenance.
- Application computes digests from stored canonical membership, not supplied CLI hashes.
- Per-message operation ledger prevents duplicate dispatch for a completed approval/action. Across plans, present state and source trash provenance determine eligibility; a completed deletion cannot be counted twice. Retrashing a restored message needs a new explicit plan and approval.
- Journal events and outcome updates commit together. Retry attempts append new evidence; they do not erase unknown outcomes.
- Cache primary key is (account_id, generation, message_id); index sender, size, date, thread and label membership. Sync cursor and active generation publish together.
- No vector embeddings or vector database are needed.

---

# ⚙️ 8. APIs Definition

The v1 public interface is a CLI, not a network service. Commands below are proposed application interfaces and must not be represented as already installed skill commands.

```text
reclaim analyze [--full-resync] [--html PATH] [--json] [--redact-subjects]
reclaim propose --action trash [--promo-age 6m] [--min-batch-mb 100]
reclaim list --plan ID --revision N --batch ID [--page N]
reclaim confirm --plan ID --revision N --batch ID --action trash
reclaim execute --approval ID [--execute]
reclaim restore --source-operation ID [--execute]
reclaim protect --sender ADDRESS [--reason TEXT]
reclaim protections list
reclaim protections remove --sender ADDRESS
reclaim reconcile
reclaim status [--plan ID]
reclaim audit export --output PATH
reclaim cache rebuild
```

Gate C adds a distinct `reclaim propose --action permanent_delete --source-plan ID` and a corresponding permanent_delete confirmation. No purge flag can upgrade trash approval. Gate A rejects all real mutation commands before loading a write-capable adapter. Restore asks for its own confirmation; --execute merely requests real mode.

Protection removal requires explicit human confirmation. Additions immediately narrow all pending work. Account-wide protections are account-scoped, not shared across identities accidentally.

Example approval-request envelope (illustrative, not an actual approval; digest intentionally omitted until canonical membership is computed):

```json
{
  "type": "approval_required",
  "account_id": "example-account",
  "plan_id": "example-plan",
  "revision": 1,
  "batch_id": "example-batch",
  "action": "trash",
  "membership_digest": null,
  "approval_id": null,
  "permanent_delete_authorized": false,
  "requires_trusted_human_event": true
}
```

Gmail endpoints and roles (behavioral gates apply):

| Method | Purpose | Capability |
|---|---|---|
| users.getProfile | Bind identity, count-only observation, history boundary | Gmail read |
| users.messages.list/get | Metadata enumeration, fresh safety reads | Gmail read |
| users.threads.get | Fresh sent-thread heuristic | Gmail read |
| users.history.list | Incremental sync and reconciliation | Gmail read |
| users.messages.attachments.get | Optional attachment-content comparison | Gmail read |
| users.messages.batchModify | Bounded trash-label updates | Gmail modify |
| users.messages.untrash/modify | Restore plus supported label reconciliation | Gmail modify |
| users.messages.batchDelete/delete | Irreversible purge, Gate C only | Full mail scope |
| Drive about.get(fields=storageQuota) | Optional delayed quota observation | Separately validated Drive read capability |

messages.batchModify has a documented ID cap to validate against the current reference; use conservative configurable dispatch chunks of 20 for v1, below intended provider limits. Do not assume batchDelete has the same maximum simply because its request also contains IDs. HTTP multipart batching is only a transport optimization and does not change per-method quota charges or authorization boundaries.

---

# 🚀 9. Deployment Architecture

Local execution; no service cluster. Candidate dependencies: Python, google-api-python-client, google-auth-oauthlib, LangGraph, langgraph-checkpoint-sqlite, Typer, Rich, and a cross-platform account-lock implementation. Pin and lock versions after the Appendix A runtime probe; no untested latest-version claim.

**Profile-safe installation:** reuse the installed google-workspace scripts/_hermes_home.py and get_hermes_home(). Resolve HERMES_HOME through that helper; do not invent a second fallback in this application. Place integration scripts next to the helper or import it through a tested package adapter. No cross-profile credential discovery or writes.

Define H = Path(get_hermes_home()).expanduser().resolve(). All state paths derive from H:

```text
H/google_token.json                     existing skill credentials
H/google_client_secret.json             existing OAuth client configuration
H/inbox_reclaimer/cache.db               rebuildable sensitive metadata
H/inbox_reclaimer/journal.db             durable execution/approval authority
H/inbox_reclaimer/checkpoints.db         workflow state
H/inbox_reclaimer/audit/*.jsonl          regenerable audit exports
H/inbox_reclaimer/reports/               escaped local reports
H/inbox_reclaimer/locks/                 per-account executor locks
H/inbox_reclaimer/logs/                  redacted operational logs
```

On startup, display the resolved profile root and bound account. Test two temporary HERMES_HOME values for isolation. A missing expected helper/profile configuration blocks mutations rather than scanning another profile for tokens.

A single local executor per account serializes trash, purge, restore, reconciliation writes, and protection changes. Use an OS-held exclusive lock for the process lifetime of an execution session; do not rely only on a TTL lease that can expire during a slow call. Hold the lock across safety reads, intent, API dispatch and outcome recording; do not hold an SQLite transaction open over the network. Multiple machines sharing the same account are unsupported; external Gmail clients remain outside this lock.

**Environments:** development uses fakes and temporary profile roots; staging uses a dedicated receiver account and separate sender; production is the user's local profile only after gates pass. Docker is optional for read-only reproducibility, not required for host OAuth/locking. No Kubernetes deployment in v1.

**Backup/reset:** cache rebuild deletes only cache metadata. Journal and checkpoint reset requires explicit separate action after unresolved operations are reconciled. Back up journal.db using SQLite's consistent backup API, not an unsafe copy of a live WAL database. Encrypt/protect backups; validate recovery on staging. Loss of journal disables purge of previously processed messages until evidence is restored. Do not call the whole directory disposable.

---

# 📈 10. Scalability & Performance

The live Gmail quota reference inspected for this revision lists the following new quota regime:

| Limit/cost | Value |
|---|---:|
| Per minute per user per project | 6,000 units |
| Per minute per project | 1,200,000 units |
| messages.list | 5 units |
| messages.get | 20 units |
| threads.get | 40 units |
| history.list | 2 units |
| getProfile | 1 unit |
| attachments.get | 20 units |
| batchModify / batchDelete | 50 units each |
| messages.delete | 10 units |
| messages.modify / untrash | 5 units each |

The reference says projects with qualifying prior activity may retain older quotas, while projects created on/after May 1, 2026 use the new regime. Effective project limits must be checked; do not infer them solely from account type.

Make method costs, per-user/project rates, concurrency, chunk size, daily budget and safety-read freshness configurable and versioned. Default planning budget: 4,800 units/minute/user/project, with smooth pacing and a rolling-window limiter. Reserve capacity for identity and required safety/reconciliation reads. HTTP batching does not bypass this limiter. Honor the lower of configured and effective project limits.

Calculated metadata-harvest example, excluding getProfile, history replay, attachment/thread reads, retries and network overhead:
- 50,000 messages × 20 units + 100 list pages × 5 units = **1,000,500 units**.
- At 6,000 units/minute: **166.75 minutes theoretical minimum**.
- At the 4,800 planning budget: **208.4375 minutes before additional work**.

These arithmetic results were calculated with Python, not benchmarked throughput. Remove the previous short first-run estimate. Large mailboxes can take hours; support cancellation/resume of analysis, progress reporting and estimated remaining quota costs.

Performance targets, subject to benchmarking: local paginated batch views under 500 ms p95 and cached summary reports under 2 seconds for a 100,000-message fixture on a documented reference machine. No live Gmail completion-time SLA. Safety checks take priority over throughput; never disable sent-thread rechecks to meet a speed target.

---

# 🔐 11. Security Design

## 11.1 OAuth capabilities and escalation

The inspected installed setup.py defines a fixed SCOPES list containing Gmail readonly/send/modify and other Workspace scopes, but not https://mail.google.com/. Its current missing-scope helper also does not establish action-specific grants. Re-running the same consent flow cannot add an unrequested capability.

Required implementation work, not an existing command:
1. Add explicit action-specific scope selection to the setup integration: analyze/propose → gmail.readonly; trash/restore → gmail.modify; permanent_delete → https://mail.google.com/. Avoid requesting send/Drive/Calendar solely for this application.
2. Request additional consent only after the user elects the gated capability. Preserve existing credentials while consent is pending or denied. Revocation is not the default escalation step.
3. Validate actual granted scopes and account identity from the resulting credential/authorization data. Do not treat requested scopes or a missing scope field as proof of a grant. Unknown capability blocks that action.
4. Stage new credentials separately; atomically adopt only a validated same-account grant. Retain a valid prior refresh token where supported; test refresh and denied-consent recovery without logging secrets.
5. Map stronger scopes to supported capabilities explicitly and test the mapping. Enforce application-level read-only mode even if an existing token has broader privileges.
6. Document restricted-scope verification/admin policies if distributing beyond personal/local use. Grant possession is not approval to delete a batch.

Optional quota observation must not silently broaden a Gmail-only consent request. getProfile contains counts, not storage bytes; without Drive consent, omit the live quota reading.

## 11.2 Privacy modes and untrusted mail

**Local-only mode (default):** Gmail/Google auth services receive necessary API requests; no mailbox metadata is sent to an LLM provider. Reports and confirmation lists are rendered directly by the local application. Running a raw-output command through hosted Hermes conversation would break this mode; the Hermes-facing read tool therefore returns minimized counts/opaque references by default.

**Cloud-assisted mode (explicit opt-in):** show the exact fields and provider before sending anything. Default external payload is aggregate counts, size bands and pseudonymous batch IDs. Subject/sender samples require a separate disclosure choice; full bodies/attachment bytes are not sent in v1. Provider and Hermes conversation logs may retain disclosed content under their own policies; local deletion cannot retract it. Disable automatic model traces or redact them before capture.

Sensitive artifacts include cache.db, journal.db, checkpoints.db, reports, audit exports, backups, temporary downloads and possible conversation/log histories. --redact-subjects applies to newly persisted/exported subject fields across all application stores, not only JSONL. Fetch subject samples transiently for a local view if requested; do not persist them under this option. It does not anonymize sender addresses, IDs or past exports. A separate explicit cleanup is needed for old sensitive artifacts.

Retention policy defaults: operational logs rotate and expire after 14 days; transient downloads are removed after hashing; generated reports expire after 7 days; completed workflow checkpoints after 30 days once reconciled. Journal evidence is retained until explicit archival/deletion and never automatically discarded while unknown operations or restore obligations remain. Cache rebuild/reset is explicit. These are product policies, not provider guarantees.

Use OS-private file permissions/Windows ACLs, encrypted local disks where available, and protected backups. Do not claim SQLite is encrypted by default. Never log access/refresh tokens or OAuth codes.

Treat email headers, attachment names and bodies as untrusted data: HTML-escape all rendered fields, encode embedded JSON safely, strip terminal control sequences, neutralize spreadsheet formula prefixes in CSV exports, and never execute URLs or instructions found in mail. Local HTML uses no remote tracking assets and a restrictive content policy. No auto-unsubscribe or attachment opening in v1.

---

# 📊 12. Observability

Journal-backed counters: approved/rejected, attempted/confirmed/unknown/failed/skipped per action; safety skip reasons; dry-run outcomes; retries; API quota cost; approval expiry; account mismatch; recovery backlog; export lag.

Every operation/event includes account_id, plan/revision, approval_id, operation_id and timestamps. Logs contain opaque references and error classifications, not raw email content.

Completion output separates:
- Confirmed trash operations and estimated message bytes affected.
- Confirmed permanent-delete acknowledgments and their estimated message bytes.
- Observed-absent messages after uncertain calls, counted separately without claiming deletion attribution.
- Unknown/failed/skipped records with next steps.
- Optional live storage usage and timestamp: **may lag minutes to hours; other Drive/Photos/mail activity can affect the value**.

Summed sizeEstimate is an estimate, not authoritative quota freed. Do not require or promise an immediate positive quota delta. Audit export is for inspection; the transactional journal is the authoritative operation record. Prometheus/OpenTelemetry are optional later; local structured logs and status views suffice for v1.

---

# ⚠️ 13. Failure Handling & Resilience

| Condition | Required behavior |
|---|---|
| Required safety read fails | Skip affected message; thread-read failure skips all affected thread members |
| Approval expired/changed scope/account mismatch | Stop dispatch; require corrected identity or fresh trusted approval |
| Rate limit / transient read failure | Bounded exponential backoff with jitter and Retry-After; keep within quota budget |
| Gmail write timeout/disconnect/process death | Mark unknown; reconcile before deciding whether a new attempt is safe |
| Storage full/journal commit failure | No new Gmail write without committed intent; stop after any response that cannot be recorded |
| JSONL export/checkpoint failure | Preserve committed journal; resume/export from event IDs; do not repeat a mutation |
| Missing message during trash/restore | skipped/missing, not a successful mutation |
| Missing message during uncertain purge | Record observed_absent with uncertain attribution; no duplicate quota credit |
| History expired or incomplete | Full resync; no executable plan from incomplete cache |
| Concurrent local restore/purge | Exclusive account lock serializes operations; later action sees updated provenance |
| Lost journal | Disable affected mutation recovery/purge; recover backup or require manual resolution |

Batch failure handling:
- Multipart read batches have per-subrequest results. Inspect and retry individual safe reads.
- batchModify and batchDelete return a single method response; do not invent per-ID response statuses or claim atomicity. Treat invalid-ID behavior as provider-specific until live probes pass.
- On a failed/uncertain mutation chunk, reconcile each ID. A safe per-ID fallback creates a new journaled attempt and repeats identity, approval, protection, and provenance checks. Never fallback on authentication/permission failures by blindly spraying requests.
- An individual messages.delete 404 may mean absent, but is not proof the tool deleted it. Validate error context and classify as observed_absent/missing; do not count it as a newly confirmed deletion.

Unknown outcome recovery:
1. Under account lock, convert unfinished pending work to unknown and load committed intent/pre-images.
2. Read current state and history where available. A state consistent with a requested transition can be recorded as observed, but does not automatically establish tool causality.
3. Unknown trash that merely appears in TRASH is not promoted to purge-authorizing provenance without sufficient confirmation evidence. Conservative unresolved cases remain blocked for purge and require manual review.
4. A still-present purge candidate may be retried only under valid current approval and all fresh checks. An absent candidate is not retried. A restored/newly protected candidate is skipped.
5. Reconciliation may finish after approval expiration because it is observational; new writes require valid approval.

Do not claim exactly-once remote writes. The contract is durable intent, at-most-one active local executor, conservative reconciliation and no blind replay. Gmail side effects and SQLite commits are not one transaction.

---

# 🧪 14. Testing Strategy and Release Gates

**No application test suite is claimed to have run merely because these tests are specified.** Gate evidence must include pinned versions, commands, fixture descriptions, actual outputs and pass/fail records.

## Gate A — analysis and proposal release
- Unit: sender parsing, newsletter headers, decimal thresholds, calendar cutoffs/leap years, malformed dates, labels, overlapping cumulative cohorts and disjoint totals.
- Sync: H0 captured before scan; arrivals/deletions/label changes during pagination; multi-page history; committed-cursor crash boundaries; expired history; SENT-thread cache invalidation; account isolation.
- Batching: unique owning batch per message/action; union totals; deterministic priority; rejection never reassigns IDs; sealed revisions cannot change membership.
- Attachments: identical filename/size with different content; equal SHA-256 with distinct message bodies/additional attachments. Neither produces a deletion batch.
- Privacy: hostile subjects/filenames cannot execute HTML, scripts, terminal controls or CSV formulas; redaction covers every output/store; cloud transport is disabled in local-only mode.
- Load: reference 100,000-message fixture, report/query targets in §10; quota pacing tests use the configured cost table rather than old hardcoded rates.

## Gate B — trash/restore release
- Approval: wrong account, switched token, expired/revoked approval, changed revision, changed IDs/action, fabricated resume payload, replayed UI event and absent trusted human evidence all block writes.
- Protections: user stars, marks important, replies, or adds sender protection between planning and execution. Repeat between trash and a later action. Failed required reads result in skips.
- Restore: unchanged mailbox label equality; inbox/unread/archive combinations; custom labels; external label changes; deleted custom labels; untrash and repair partial failures.
- Fault injection before/after every intent commit, API dispatch, API response, outcome commit, JSONL export and graph checkpoint. No intent means no call; unknown results trigger reconciliation, not blind retries.
- Concurrent restore/trash/purge requests: account lock, recovery after process death, correct provenance invalidation. Test Windows locking semantics as well as POSIX.
- Dry-run records and JSONL edits cannot authorize real mutations. Duplicate graph resume cannot duplicate a completed operation.
- LangGraph probe: real checkpoint creation, interrupt, process termination, second-process reopen and resume; rejection and list navigation; no unsafe pre-interrupt side effect. Remove import-only acceptance.
- OAuth: action-specific requested/granted scopes, denied additional consent preserves old access, account mismatch refuses token replacement, missing grant metadata fails closed.
- Live staging fixture uses a **separate sender account** for eligible newsletter mail. Receiver self-sent/replied threads are protected fixtures, not deletion candidates.

## Gate C — purge release (disabled until independently passed)
- Trash approval cannot authorize permanent_delete; a CLI flag or model-authored Command cannot upgrade it.
- Only confirmed non-dry-run trash provenance plus current TRASH membership qualifies. Restored, newly starred, important, replied-to, sender-protected, or unknown-provenance messages are skipped.
- Account switch, expired approval, changed membership and overlapping plans cannot widen the purge set.
- Probe batchDelete with valid staged IDs, malformed IDs, previously deleted IDs and mixed chunks in a disposable test account with explicit approval. Record whole-request behavior and per-ID reconciliation results rather than prescribing fabricated 404 semantics.
- Crash/timeout tests cover unknown purge outcomes and missing messages; uncertain absence never becomes counted confirmed deletion.
- Live smoke asserts the exact expected IDs absent, protected/control IDs still present, journal evidence correct, and no unrelated Trash touched. Quota observations may be delayed; immediate quota reduction is not the pass criterion.
- Restore and purge cannot run concurrently for the same account; restored items invalidate later purge eligibility.

Attachment-based deletion has no v1 release gate because it is not a v1 capability. A future design must require separate message-level review.

---

# 💰 15. Cost Optimization

Use local SQLite and a local CLI to avoid required hosted infrastructure and model costs. Metadata reads and incremental history reduce transfer and repeat work; they do not change per-request quota cost. Cache advisory results but never substitute cached safety checks for dispatch-time reads.

The inspected quota page lists an **80,000,000-unit daily per-project billing threshold**, states standard API use is currently at no additional cost, and describes planned charges later in 2026 with notice. This is not the old 1B-units/day assumption and is not a promise of permanently free usage. Recheck effective project quotas, billing notices and pricing before release and large runs. Expose configurable budget stops; stop before exceeding a user-selected daily budget.

Avoid unsupported claims of bandwidth reduction factors or guaranteed recovery percentages. The largest performance trade-off is deliberate: fresh protection reads and conservative recovery cost quota but reduce deletion risk.

---

# 🗺️ 16. Future Enhancements

1. Complete Gate A, then Gate B; evaluate Gate C independently rather than enabling all actions together.
2. Optional local web UI with accessible batch review, independent trusted approval controls and privacy-safe previews.
3. Multi-account support after account-bound schema/lock invariants pass; account-switch detection remains mandatory in v1.
4. Scheduled read-only reports and proposal notifications; scheduled jobs cannot create standing deletion consent.
5. Optional local-model advisor, then explicitly consented hosted advisor with field-level disclosure.
6. Attachment review improvements that compare message context and additional attachments; content hashes alone remain insufficient deletion rationale.
7. Other storage providers as separate scoped integrations. Do not imply Drive and Photos expose identical deletion/quota APIs.

---

# Appendix A — Grounding and Verification Register

## Evidence obtained for this revision

- Read installed google-workspace scripts/_hermes_home.py: exposes get_hermes_home(), delegates to hermes_constants when available, otherwise resolves HERMES_HOME. Application paths will use this helper.
- Read installed scripts/setup.py, including SCOPES and scope validation: full mail scope absent; action-specific escalation is implementation work, not a working existing command.
- Inspected public Gmail usage-limits page through the browser: https://developers.google.com/workspace/gmail/api/reference/quota . Values, grandfathering note and billing-threshold caveats in §§10/15 reflect that page.
- Calculated the §10 example with Python: 1,000,500 units; 166.75 minutes at 6,000 units/minute; 208.4375 minutes at 4,800 units/minute.

## Not verified by this revision

No Gmail account was accessed, OAuth grant changed, or mailbox operation run. Earlier LangGraph installation failed; no installed-version runtime behavior is claimed. An additional reference-fetch command was blocked by the tool approval gate. The batchDelete reference navigation did not yield a usable body for behavioral verification.

Public reference targets for implementation gates:
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchDelete
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchModify
- https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/untrash
- https://developers.google.com/workspace/gmail/api/guides/sync
- https://developers.google.com/workspace/gmail/api/auth/scopes
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://hermes-agent.nousresearch.com/docs/user-guide/profiles

Hard verification gates: current endpoint request limits and granted scopes; actual trash/untrash label transitions; mixed-ID batchDelete outcomes; identity and scope escalation without revocation; durable LangGraph interrupt/restart/resume. Documentation and mocks cannot replace approved disposable-account tests for destructive semantics.

# Appendix B — Review Resolution Map

| Finding | Resolution location |
|---|---|
| Approval not bound to purge/account/membership | §§4.5, 5, 7, 8, Gate C |
| Weak TOCTOU and restored/protected purge candidates | §§4.4–4.5, 13, Gates B/C |
| Unsafe attachment-deletion rationale | §§2, 4.2–4.4, 7, Gate A |
| Missing write-ahead journal, recovery and serialization | §§3, 4.5–4.6, 6–7, 9, 13 |
| Account binding and profile paths | §§4.1, 7, 9, 11 |
| Fixed OAuth scope list cannot escalate | §11.1, Gate B, Appendix A |
| Outdated quota, throughput and free-usage assumptions | §§10, 15, Appendix A |
| Sync cursor boundary and overlapping batches | §§4.2–4.4, 7, Gate A |
| Local-only versus cloud privacy contradiction | §§5.3, 9, 11.2 |
| Missing acceptance/fault-injection tests | §14 |
| Broken saver/interrupt examples and import-only probe | §5.2, Gate B |
| Restore label round-trip | §4.6, Gate B |
| Lagging quota and unproven deletion attribution | §§12–14 |
| Multiple destructive orchestration paths | §§3, 5, 9 |
| Missing sender-protection command/enforcement | §§4.4–4.5, 8 |
| Unbounded Trash sweep and premature readiness | §§2, 8, 14; version/status header |
