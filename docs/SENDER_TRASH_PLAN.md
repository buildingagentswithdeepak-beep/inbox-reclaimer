# Bounded sender cleanup — implementation contract

## User amendment
The user selected: move up to 1,000 matching messages to Trash after preview and confirmation. This is permission to implement, not permission for the agent to access or modify a live mailbox.

## Assumptions and release boundary
- Match a single exact parsed sender address, not a domain/display name/search expression. Query `from:` is candidate retrieval only; verify metadata sender exactly. A candidate cap of 1..1000 includes disappeared/excluded/mismatched search hits, so execution may contain fewer items.
- No age/size minimum: the explicit sender selection replaces the automatic cleanup rules for this workflow only. All existing protected-label/sender and SENT-thread checks remain mandatory. Mailbox-wide scan is not necessary; this is a new sealed bounded selection, never an approval of the partial analysis cache.
- One sender plan has at most 1,000 immutable IDs and one approval challenge. Dispatch uses one-message batchModify chunks, below the spec's conservative maximum, to bound safety-read age.
- Confirmation occurs only in a separately launched native local window, not stdin, CLI flags, JSON or a graph resume. Preview is the default. `--execute` requests the window, not approval.
- Sender plans, approvals, intents and outcomes extend the existing journal.db with namespaced tables; existing Gate A tables/triggers stay closed. Raw subjects and message headers remain transient and are not persisted in the sender journal. Plans and events are immutable; unknown outcomes block new effects.
- Restore is separately confirmed and uses confirmed trash pre/post label observations. Preserve external changes by refusing a conflicting label precondition; never replace entire label sets. Each untrash/repair step has a durable intent and no blind retry.
- Original Gate B live-test requirement remains binding. Build includes operational mock transport, real SQLite engine, GUI and read-only sender preview. Live write adapter remains release-disabled until explicitly approved disposable-account trash/restore and crash/label-transition evidence is obtained. No CLI/env option bypasses this release gate. Do not present the feature as live-enabled before that test gate.
- Gmail modify consent is a separate explicit local action, requested only for this elected capability. Preserve existing valid credentials on denial/mismatch; request no separate gmail.send, Drive or full-mail scope. The required gmail.modify grant is nevertheless broad enough to permit sending (Google's discovery description: “Read, compose, and send emails from your Gmail account”); this application exposes no send operation. OAuth permission is never deletion approval.

## Pre-release validation amendment
The operator subsequently approved code fixes and identified availability of a disposable Gmail account. `LIVE_VALIDATION.md` defines a separate fixed-home, expected-account, maximum-five-candidate local test entry point. Only this scoped validation route can construct the live writer before production release; it requires the normal native approval, account/client checks, immutable membership, journal and dispatch guards. Neither an environment variable nor ordinary `sender-cleanup --execute` enables production writes. This exception exists to gather mandatory live test evidence; it is not a Gate B release or permission for the hosted agent to mutate mail.

## Components and ownership
1. Shared models (`sender/models.py`): SenderPlan, Approval; canonical digest binds account/client-derived identity, sender, IDs, action, source plan, policy and plan ID. Shared validation and closed live-release gate.
2. Candidate selection + CLI + native confirmation (controller): targeted paginated reads, unique cap, metadata/exact-sender/protection checks, transient full-list preview, explicit rejection, confirmation-to-executor integration. Existing analyze behavior unchanged.
3. Sender journal + execution service (worker): additional tables in same journal; transactional immutable plans/approvals; expiry/one-shot challenges; intent-before-write; per-ID outcomes; crash recovery; restore label repair; executor injected writer (offline tests). Every effect repeats identity/approval/protection checks and requires caller-held account lock.
4. Google sender read/write transport + modify OAuth (worker): exact candidate query, one-attempt write calls, actual grant/client validation, quota reservation; no permanent delete methods. Real writer constructor enforces closed Gate B; mock-tested internal transport verifies request contracts without changing release readiness.

## Shared interfaces
`SenderPlan(account_id, plan_id, sender, ids, action='trash', source_plan_id=None, created_at=<UTC epoch>, policy_version='sender-v1')`; `.digest` calculated from immutable scope fields. `Approval(account_id, plan_id, digest, action, principal, event_id, challenge_id, issued_at, expires_at)`.

Journal initialized from a bound `JournalStore`: `SenderJournal(journal)`; `save_plan(plan)`, `get_plan(account_id, plan_id)`, `approve(plan, approval)`, `validate_approval(plan, approval_id, now)`, `begin(plan, approval_id, message_id, step, preimage) -> operation_id`, `finish(operation_id, state, postimage=None, reason=None)`, `operations(account_id, plan_id=None)`, `recover(account_id)` marking pending unknown. Exact returned shapes documented in implementation.

Executor: `SenderExecutor(adapter, sender_journal, clock=time.time)`; `execute(plan, approval_id, dry_run=True) -> dict`, `restore(plan, approval_id, dry_run=True) -> dict`. Adapter exposes `resolve_identity()`, `validate_capability(action)`, `get_metadata(id)`, `get_thread(id)`, `trash_ids(ids)`, `untrash_message(id)`, `modify_message(id, add_labels, remove_labels)`; actual transport reserves quota before final protection reads via `prepare_write(action)` where available. No automatic write retry.

Read selection uses `GoogleSenderReader(base_read_adapter).list_sender_ids(sender, page_token=None, max_results=500) -> {'ids': [...], 'next_page_token': ...}`. Writer `GoogleSenderWriter(base_read_adapter)` wraps same validated session and refuses construction until release gate passes.

OAuth function `authorize_modify(paths, *, consent=None, verify=None, confirm=None)` and standalone `python -m inbox_reclaimer.sender.authorization --workspace-scripts PATH [--manual-browser | --check]`. Read-only auth remains unchanged.

## Execution plan and verification
- Write shared contracts and requirement tests before implementations.
- Run isolated worker tests, inspect actual artifacts, spec review then quality review.
- Verify sender selection query injection defense, cap, exact sender, protections, fail-closed thread reads, account switches, redaction, cache isolation.
- Verify approval expiry/scope, malicious flags/no UI decision, duplicate/replayed dispatch, intent rollback/crash, ambiguous write outcomes, pending-to-unknown restart, and restore label round-trip/conflicts using fake transport and real journal.
- Existing `pytest -q` and ruff must pass. Execute the actual CLI and packaged wheel against synthetic fixtures; inspect the native preview window without clicking a real-mail permission/approval control.
- Report offline results separately from the remaining live Gate B blocker. Permanent deletion stays disabled.
