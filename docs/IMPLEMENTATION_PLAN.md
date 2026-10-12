# Inbox Reclaimer — implementation plan / architecture / contracts

## Release decision
Implement specification v2 Gate A (sections 2, 14): actual read-only inventory + immutable proposals. Gates B/C are unconditionally closed, not flags a model or environment can enable. No Gmail mutation implementation is shipped/exposed. No mailbox access or OAuth changes during development. This scope follows the spec's explicit first-deliverable sequencing, not an assertion that B/C are complete.

## Necessary assumptions
- New repository `C:\Users\v-deegarg\inbox-reclaimer`; Python 3.11 and local CLI, not a web service.
- Gate A cannot mint trusted human mutation approvals. confirm/execute/restore explain the closed gates; protect removal is also blocked until an independent trusted surface exists.
- Conservative configurable proposal defaults (not stated in spec): size >10 MB and older than 1 year; newsletter older than 1 year; Promotions older than 6 months. Default minimum batch 100 decimal MB, batch cap 100 messages. No attachment-derived rule. Proposal configuration and cutoff are recorded.
- Timezone defaults UTC (explicit config override); annual/monthly arithmetic clamps end of month.
- Installed google-workspace helper is imported from an explicit script-directory option in app config; no copied fallback or token search. Missing helper fails closed. Offline fixture uses same helper with temporary HERMES_HOME, not real credentials.
- Existing scopes in an authorized-user token are requested scopes, not evidence of granted scopes. Live reads validate access-token grant metadata from Google tokeninfo and same-account Gmail profile. No automatic token-file replacement, setup, or escalation in Gate A.
- Optional attachment comparison consumes bounded local observations/bytes and is advisory. A live opt-in MIME pass may be provided separately; nothing opens attachments or uses them as proposal reasons.

## Layers / file ownership
1. Shared contracts: `src/inbox_reclaimer/models.py` (controller).
2. Storage/domain: `storage.py`, `proposals.py`, their tests (worker A).
3. Google/fake read adapters, quota, synchronization: `gmail.py`, `sync.py`, `quota.py`, their tests (worker B).
4. Analytics, HTML/terminal safety, attachments: `analytics.py`, `render.py`, `attachments.py`, their tests (worker C).
5. Profile config/security, CLI composition, LangGraph read-only workflow, fixtures, integration and benchmark (controller).

## Shared contracts (no hidden cross-worker changes)
Frozen dataclasses in models.py:
- Identity(email, oauth_client_id, subject=None), account_id property = SHA256 canonical JSON binding email/client/subject. No dot/plus normalization.
- Message(id, thread_id, internal_date: int|None [epoch ms], size_estimate: int|None, labels: frozenset[str], raw_from: str, subject: str|None=None, headers: dict[str,str]=..., valid: bool=True). Headers normalized lowercase. Sender is parsed by analytics.parse_sender(raw_from) -> str|None.
- Inventory(account_id, generation, cursor, started_at, completed_at, complete, unresolved: tuple[str,...], messages: tuple[Message,...]). Dates ISO timestamps, cursor opaque str.
- Rule(rule_id, kind, min_bytes=0, older_months=0, category=None, sender=None); kinds SIZE_AGE, SENDER_NEWSLETTER, CATEGORY_AGE.
- Batch(batch_id, kind, ids: tuple[str,...], estimated_bytes, digest, reasons: dict[str,list[str]]).
- Plan(account_id, plan_id, revision, action, policy_version, inventory_generation, created_at, batches: tuple[Batch,...], status='sealed').
- Errors ReclaimError, GateClosed, IdentityMismatch, IncompleteInventory, MissingMessage, HistoryExpired, ReadFailure.

Storage signatures:
CacheStore(path): publish(inventory), load(account_id)->Inventory|None, rebuild(account_id), invalidate_thread(account_id,thread_id=None), close(). Atomic generation + cursor publish; account-scoped indexes; prior inventory remains on failure.
JournalStore(path): bind_account(identity), protect_sender(account_id,address,reason=''), protections(account_id)->set[str], save_plan(plan), get_plan(account_id,plan_id,revision=1)->Plan, plans(account_id)->list[Plan], list_batch(account_id,plan_id,revision,batch_id,page=1,page_size=50)->dict, reject_batch(account_id,plan_id,revision,batch_id), export_audit(output)->dict, status(account_id)->dict, backup(output), close(). Keep schema from spec with sealed membership enforcement. list_batch returns {'ids':[...], 'total':..., 'page':...}. No approval minting.
ProposalService(cache,journal,adapter): build_revision(identity,rules,cutoff:datetime,min_batch_bytes=100000000,max_batch_messages=100,plan_id=None)->Plan. Fetch threads; failed/malformed/SENT threads excluded. bind identity before/after. Every proposal remains non-executable in Gate A.

Read adapter signatures:
resolve_identity()->Identity; validate_capability(action)->None; history_boundary()->str;
list_message_ids(page_token=None)->dict {'ids':list[str], 'next_page_token':str|None};
get_metadata(message_id)->Message (MissingMessage on verified 404);
get_thread(thread_id)->list[Message];
read_history(start_history_id,page_token=None)->dict {'affected_ids':list[str], 'deleted_ids':list[str], 'thread_ids':list[str], 'unknown_threads':bool, 'next_page_token':str|None, 'history_id':str}.
FakeGmailAdapter(messages:Iterable[Message],identity:Identity|None=None) implements contract and deterministic opaque cursor, never network. GoogleReadAdapter(profile_root:Path,quota=None) only read methods, credentials loaded once, validated grant metadata and identity. No Gmail writes.
SyncService(adapter,cache,redact_subjects=False): full_sync()->Inventory; incremental_sync()->Inventory. Identity checks through each protocol; thread invalidation. Full sync H0 before list; replay all structured history events, dedupe/refresh. No publish if failure; bounded restart on expired H0. Missing scan records separately reported, not tool deletion evidence. Progress callbacks and staging/resume desirable; explicitly document if deferred.

Analytics signatures:
parse_sender(raw)->str|None; subtract_months(datetime,months)->datetime (clamped).
build_report(inventory,cutoff:datetime,timezone='UTC')->dict with account_id,generation,coverage,totals,top_senders_count,top_senders_bytes,categories,newsletters,size_cohorts,age_cohorts,size_bands,age_bands,warnings. No subjects in aggregate report. All message counts distinct IDs.
render_html(report)->str; render_terminal(report)->str; safe_terminal(text)->str; csv_safe(text)->str. HTML self-contained, CSP and escapes all user-controlled values; visually professional accessible dashboard. No remote assets/cloud transports.
Attachments: independent typed observations; possible filename/size matches vs confirmed equal bytes; downloads bounded, hash streaming local chunks; zero contribution to proposal totals.

## Task and verification sequence
- Pre-flight: read entire spec, inspect installed helper, resolve/pin dependencies, exercise two-process LangGraph saver/interrupt for approve/reject/list/invalid/expired. **Passed before application implementation** with langgraph 1.2.8, checkpoint-sqlite 3.0.3, checkpoint 4.2.0. Probe is non-destructive, not evidence of production trusted approvals.
- Parallel tasks A/B/C: write focused failing tests before implementations, run subset with `.venv/Scripts/python -m pytest`; never access live Gmail or edit other workers' files.
- Controller: profile-scoped paths/private ACLs+OS locks; Typer CLI; fake fixture integration; reference-only LangGraph workflow; startup profile/account notice; enforce closed gates before adapter creation.
- Integration: canonical `pytest`, actual CLI analyze -> propose -> list -> protection -> status -> audit -> cache rebuild; all in temporary profile roots, read-only fake mailbox clearly labeled.
- Load: synthetic 100k-message fixture, summary target <2s and paginated view <500ms p95; capture actual reference machine and timings, not invented estimates.
- Spec review followed by quality review; fix critical/important findings and rerun tests.
- Deliver README, architecture/LLD/assumptions, requirement traceability and release evidence including honest deferred B/C and live-test gaps.

## Operational constraints
All state under helper-returned H/inbox_reclaimer. Private ACL/mode before sensitive state. SQLite FK/WAL, journal FULL. Journal/checkpoint never deleted by cache rebuild. OS account lock serializes sync/proposal/protection. No telemetry/LLM calls or remote HTML assets. LangGraph tracing disabled. Reject unknown grants, identity switches, incomplete inventories, unsafe metadata. Credentials neither printed nor written. Changes to already-protected sender eligibility take effect immediately. Reports estimates ≠ Google quota; SENT heuristic and overlap limitations disclosed.
