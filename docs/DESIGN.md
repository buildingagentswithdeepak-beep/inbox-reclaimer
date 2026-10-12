# Architecture and low-level design

## 1. Assumptions

1. **Release order:** ship the read-only analysis/proposal application specified as the first deliverable (§2/§14). Mutation designs are not treated as permission to enable unfinished Gates B/C.
2. **Unspecified proposal rules:** default >10 MB/one-year size cohort, one-year newsletter cohort, six-month Promotions cohort, 100 MB minimum and 100-message cap. Options can narrow/change a newly created revision; old membership remains immutable.
3. **Time:** UTC by default; configurable IANA zone. Calendar arithmetic preserves local wall time with end-of-month clamping, using Python ZoneInfo semantics at DST boundaries.
4. **Integration discovery:** the operator supplies the installed google-workspace scripts directory (or installs its helper on the Python import path). No second home-resolution fallback or cross-profile credential search exists.
5. **Scope provisioning:** analysis requires existing credentials. A separate, explicitly invoked `reclaim-auth` helper supports first-time Gmail-readonly consent with local browser PKCE/loopback, verified grants/account, exact-address confirmation, and exclusive no-overwrite token adoption. Consent never runs during installation/development. Capability escalation and token replacement remain unavailable; unknown actual grants fail closed.
6. **Trust:** an autonomous CLI cannot attest an independent human approval. Gate A records rejections/protection additions only; approval minting and protection removal are unavailable.
7. **Offline verification:** fixtures are explicitly synthetic. They exercise the same repositories, sync, graph, policy and renderers as the live read adapter, but never establish live Gmail semantics.
8. **Analysis implementation:** indexed SQLite storage plus a single-pass in-process aggregator satisfies the local modular design without introducing a server. Cached aggregation and database hydration are measured separately.

## 2. Architecture Design

```text
Local Typer CLI / minimized --hermes read surface
    │
    ├── hard release gate (no write adapter exists)
    ├── installed google-workspace helper → active H
    ├── private state paths → OS-held account lock
    │
    ├── read-only LangGraph: analyze → [propose] → summarize
    │       │                          │
    │       SyncService                ProposalService
    │       │                          │
    │       resumable metadata reads   current thread + protection checks
    │       └──────── Read adapter ─────┘
    │                  │
    │                  ├── deterministic fake (explicit --demo)
    │                  └── Google REST + actual grant/account validation + quota
    │
    ├── Analytics → safe Rich output / JSON / self-contained HTML
    ├── opt-in MIME metadata → advisory attachment findings only
    └── SQLite repositories
            cache.db        journal.db        checkpoints.db
            rebuildable     authority         opaque references
                                └── idempotent JSONL export
```

The local modular monolith has no HTTP server, queue, vector store, hosted model, Drive dependency or microservice. LangGraph orchestrates only read/proposal transitions; deterministic services own eligibility and immutability. Account identity is exact email plus OAuth client (optional subject in the contract), canonically hashed for account-scoped keys. The persistent journal rejects an unexplained identity switch within one profile.

### Reliability and security boundaries

- **Cache:** generation publication and cursor advancement share a transaction. Staged or failed scans cannot advance the active cursor.
- **Journal:** foreign keys, WAL, synchronous FULL; SQLite triggers seal revision membership. Audit files and graph state cannot authorize anything.
- **Checkpointer:** compiled and invoked only inside the `SqliteSaver` lifetime; state contains account/generation/cursor/plan/revision/workflow references, not subjects or message lists.
- **Identity:** credential file loaded once, grant validation from Google's token metadata, profile revalidation before reads/retries. Refresh stays in memory and never rewrites tokens.
- **Concurrency:** OS-held account lock, not a TTL lease. Network-share state is unsupported. External Gmail clients remain outside the lock; future mutations cannot promise atomic compare-and-delete.
- **Privacy:** private file ACLs/modes, no model transport, tracing disabled, redaction before cache/staging persistence, HTML escaping/CSP and terminal control stripping. SQLite is not encrypted.
- **Safety:** no mutation methods, mutation graph edges, automatic unsubscribe or global Trash sweep. Fake/provider flags never imply authorization.

## 3. Low-Level Design

### Contracts and modules

| Module | Contract / responsibility |
|---|---|
| `models.py` | Frozen `Identity`, `Message`, `Inventory`, `Rule`, `Batch`, `Plan`; canonical hashing; classified errors |
| `profile.py` | Import installed helper; derive H paths; apply ACLs; validate export destinations; OS account lock; fail closed release gate |
| `gmail.py` | Paginated metadata/history/thread reads; fake adapter; read-only Google adapter; granted-scope and identity checks; bounded retry |
| `quota.py` | Versioned costs; lower configured/effective rate; smooth plus rolling-minute pacing and priority reserve |
| `budget.py` | Durable reservation-before-read daily cap; conservative provisional preflight bucket bound to verified account |
| `sync.py` | Capture H0 before listing; replay structured history; current refresh; thread invalidation; atomic inventory publication |
| `staging.py` | Cache-local durable enumeration/metadata staging to resume a cancelled full scan at its original H0 |
| `storage.py`, `schema.sql` | Account binding; indexed cache generations; journal schema; sealed plans; rejection/protection state; audit export/backup |
| `proposals.py` | Conservative metadata validation, current-thread protection heuristic, deterministic single-owner rules and bounded batches |
| `analytics.py` | Sender parsing, calendar cutoffs, unique-message totals, cumulative cohorts, disjoint bands and overlap disclosures |
| `attachments.py`, `mime.py` | Bounded streaming SHA-256 for decoded local streams; opt-in MIME metadata inspection; advisory grouping only |
| `render.py`, `assets/report.css` | Escaped, accessible self-contained HTML; plain safe terminal output; safe CSV-cell helper |
| `workflow.py` | Read-only StateGraph and persisted opaque references; completed workflow reopen is inspection-only |
| `retention.py` | Bounded expiry of recognized reports/logs and completed read-only checkpoints; no journal deletion |
| `cli.py` | Single composition root and all public commands; local vs minimized output; gates checked before credentials |
| `demo.py` | Explicit synthetic fixture including stars, importance, sent threads, drafts, prior Trash/Spam and hostile text |

### Data stores

`cache.db` holds account/generation-keyed records and label membership indexes, active cursors, thread observations and resumable scan staging. Raw From is separate from parsed sender; malformed values remain unknown. Only this store is rebuildable.

`journal.db` implements the source schema's accounts/plans/batches/batch_members/approvals/operations/events/export_cursors/sender_protections tables and supporting rejection/immutability enforcement. The approvals/operations tables are reserved schema, not exposed application capability. There is no approval insertion API and no real mutation dispatcher. `Plan` is loaded from normalized stored membership with digest validation.

`checkpoints.db` uses the pinned LangGraph schema. It is not copied into the journal or used as evidence of consent. JSONL exports use stable event IDs, and repeated export does not duplicate events. Consistent journal backups use SQLite's backup API.

### Synchronization algorithm

1. Acquire the account lock; resolve exact account and read capability.
2. Start/resume a staged full inventory and original H0 before list enumeration. Omit Gmail `q`; request 500 IDs/page including Spam/Trash.
3. Fetch required metadata and headers. Record missing/malformed observations without claiming tool deletion.
4. Replay every history page's added/deleted/label-added/label-removed events. Deduplicate affected IDs, refresh current state, tombstone deletions and invalidate all affected thread observations. Unknown thread identity invalidates conservatively.
5. Validate account again; publish generation and final opaque H1 together. On expired history, discard the stage and boundedly restart. On failure/cancellation retain the previously published cursor.
6. Incremental sync starts at the committed cursor, never a guessed numeric history successor. Fresh thread checks remain separate from cache freshness.

### Proposal algorithm

A complete published inventory is mandatory. Validate metadata and protected labels/sender first. For matching candidates, fetch the current thread; exclude failed/ambiguous reads, missing members, current protection changes and any SENT evidence. Check latest sender protections again before sealing. Assign by `SIZE_AGE → SENDER_NEWSLETTER → CATEGORY_AGE`, then stable rule ID. Newsletter batches are sender-bounded. Preserve matching rule IDs as reasons. Split assigned IDs into bounded chunks, discard below-minimum chunks without reassignment, compute unique counts/estimated bytes and canonical membership digest, then seal in one journal transaction.

Rejecting a batch is separate state; it never changes or moves membership. Explicitly requested new revisions are fresh plans, not automatic reconsideration. No attachment matching output enters this algorithm.

### Analytics and rendering

Deduplicate by message ID before counting. Preserve local-part case/dots/plus-tags and normalize only address-domain case. Malformed sender/date/size values are unknown. Decimal thresholds are strict greater-than; calendar age cohorts are strict older-than. Size and age cumulative cohorts overlap; disjoint bands partition inventory including unknowns. Category totals explicitly show overlap, unclassified, Trash/Spam and union counts.

All report text is data, not code. HTML uses bundled styles, no scripts and a restrictive hash-bound CSP. The terminal renderer uses Rich text objects rather than parsing mail as markup. Attachment MIME inspection selects names/part IDs/decoded sizes, omits body data and limits message count/depth/part complexity. It reports partial coverage and creates no deletion batches or recovered-byte totals.

### Errors and deployment

Classified errors fail the CLI with nonzero status and no raw token/mail exception details. Rate-limited/transient reads use bounded backoff with jitter and Retry-After. Required metadata failures prevent cache publication; failed proposal thread reads skip affected candidates. Storage errors cannot result in Gmail mutation because no mutation path exists.

Installation is a standard Python package/CLI with a locked dependency graph. Windows `run-demo.cmd` confines fixture state to the repository's ignored `.demo-profile`. No Docker or server deployment is required by this local-first specification.

## 4. Code

Implementation is in `src/inbox_reclaimer/`. `pyproject.toml` defines the `reclaim` entry point; `uv.lock` locks transitive dependencies; the built wheel includes SQL and CSS assets. This document describes the executable artifact rather than embedding a divergent code copy.

## 5. Unit Tests

`tests/` covers functional contracts, Gate A boundaries, privacy, identity, sync races/failures, ownership/immutability, rendering, attachments, quota pacing and actual process-restart checkpointer behavior. Separate subprocess tests exercise OS-lock exclusion and release after process death. Benchmarks use a documented synthetic 100k-message fixture. See validation for actual commands/results and remaining live gates.

## 6. Validation

See [VALIDATION.md](VALIDATION.md) and [REFERENCE_CHECKS.md](REFERENCE_CHECKS.md). Only verified Gate A behavior is represented as implemented. Mutation approval, durable write execution, uncertain-write reconciliation, label restoration, consent escalation and permanent deletion require separate future implementation and release evidence.
