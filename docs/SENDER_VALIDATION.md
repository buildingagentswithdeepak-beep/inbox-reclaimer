# Sender cleanup — validation and release status

## Current production review checkpoint

See `PRODUCTION_RELEASE_REVIEW.md` for the current operator live round-trip evidence and Gate B traceability. A read-only journal check verified confirmed Trash, untrash and label repair with exact original/restored metadata equality and zero unresolved effects. Approval revocation and expiry recording are now implemented and tested. The corresponding full suite passed **456 tests, 1 skipped**, and **65 installed-package tests** passed. Production remains closed pending completion of the broader release review; earlier sections below are historical snapshots, not current statements that the live round-trip is missing.

## Reconciliation digest evidence follow-up

The narrow independent review found no concrete unsafe-clear/UNKNOWN-rewrite defect in the inspected route, but identified an evidence-verifiability gap: the digest includes the original reconciliation plan timestamp while only the later observation timestamp was persisted. New resolutions now retain the canonical `ReconciliationPlan` fields under `approval_json.reconciliation_plan`, alongside the existing approval. No schema migration, original-outcome update, or guessed backfill is performed. Earlier resolutions lacking that field retain their historical evidence limitation.

A regression simulates a delayed human review, reopens the journal, reconstructs the original plan from persisted fields, and verifies its digest against both the resolution and approval. It also verifies that substituting the later observation timestamp changes the digest and that no subject is stored. The regression failed before the change; the affected reconciliation/validation suite returned **40 passed**, and global Ruff passed. Current full-suite output is reported separately in the verification session. This was not a full Gate B review; live reconciliation, restore and production release remain pending.

## Earlier validation snapshot (before audit-digest follow-up)

The operator has now approved the pending import cleanup and confirmed availability of a disposable Gmail account. The import is fixed and **global Ruff passes**. A separate, account-bound, five-candidate validation path is implemented; see `LIVE_VALIDATION.md` and `../run-disposable-validation.ps1`.

Latest full source verification: **446 passed, 1 failed, 1 skipped in 72.59 seconds**; global Ruff passed. The sole failure is `test_empty_and_100k_performance[True]`, **2.167 seconds against the unchanged two-second limit**. Reconciliation, transport, process-safety and other correctness tests passed. An earlier full run passed 447 tests; a later refresh timed out, and an intervening diagnostic used the wrong interpreter after the shell reset. The result above is the completed run in the verified project venv and supersedes earlier all-green claims. Full-suite performance compliance remains unresolved. Missing restore-source plans now produce an actionable, sanitized error explaining that restore requires a confirmed Trash plan from the same isolated account/profile, not a Gmail message ID. The regression reproduces the prior generic error and proves no confirmation or effect occurs. An earlier run satisfied the 100k analytics benchmark at its unchanged two-second threshold; the latest run did not. Size/age cumulative cohorts are now derived from disjoint bands rather than updated repeatedly per message, with binary-search boundary classification. A direct-threshold regression covers unknown metadata and exact boundaries, and a separate complete-report comparison against the prior wheel matched for 100,000 distinct senders. Timing remains host-sensitive: an individual old/new comparison did not demonstrate a speedup, so this is evidence of semantic equivalence and a passing acceptance run, not a guaranteed latency claim. The one skip requires unavailable Windows symlink-creation privileges; hard-link rejection is exercised. Earlier failed refreshes remain documented in session output.

Validation credentials are confined to `~/inbox-reclaimer-validation`; account/client and frozen IDs are checked by the writer. Ordinary production CLI writes and authorization remain closed. The dedicated local entry point permits only explicitly confirmed disposable-account test effects, not general production cleanup. **Live restore, recovery and full release review remain unverified.**

### Live read-only checkpoint and SDK response correction

With explicit operator permission, a read-only check of the one message associated with an unknown test operation verified the account against the journal and fetched only ID/thread/labels (`format=minimal`). The message was present in Trash with `CATEGORY_UPDATES, TRASH`; the original journal preimage contained `CATEGORY_UPDATES, INBOX`. No subject/body was fetched or disclosed. No mutation request was sent, and no operation outcome or credential was rewritten. Current-state observation does not establish receipt of the original mutation acknowledgement or exclude intervening external edits.

Offline reproduction with the installed Google SDK showed `batchModify` decoding an empty HTTP 200 response as `b''` and HTTP 204 as `''`. The adapter previously required a dictionary and could therefore misclassify a successful mutation response as ambiguous. It now normalizes only these empty trash acknowledgements; post-write metadata verification is still mandatory. Regression coverage uses the real SDK decoder without network, rejects unexpected raw/empty response types and empty untrash responses, and exercises actual journal confirmation/unknown behavior with synthetic transport effects. The exact historical failure phase was not retained, so this is a reproduced compatible defect, not proof of the prior response status.

The existing operation remains unknown and blocks further effects until the operator completes the new `Reconcile` stage after manual recovery. This stage has been implemented and tested with synthetic profiles; it has not been run on the operator's real journal. It preserves the original unknown record and adds an immutable `externally_restored` observation/approval record only when preimage equality, account, freshness and native confirmation checks pass. It cannot create successful-trash provenance. See `LIVE_VALIDATION.md` for the assumptions and local command. A withdrawn native window verified reconciliation wording, disabled default, exact-account acknowledgement controls and cancellation. Full Gate B review and successful live reconciliation/restore remain outstanding.

The sections below describe the preceding offline implementation baseline; their older counts/artifact smoke results are historical, superseded by this update and the latest `dist/sender-verification.json`.

## Narrow review follow-up

An independent read-only review of `sender/executor.py`, `sender/journal.py` and `sender/confirmation.py` returned no clear executor/journal blocker for an explicitly confirmed five-message disposable-account test, conditional on caller-enforced limits, native approval, account locking and transport guards. It did not review the complete adapter/caller or certify Gate B.

The reviewer identified a confirmation-preview gap: account and IDs were checked but sender identity was not. `validate_preview` now rejects mismatched, malformed or missing parsed senders before the native view is presented, for both trash and restore. Regression tests failed before this change and now pass; matching display names/domain case normalization remain accepted. Execution's existing fresh sender checks remain in place.

The current validation caller enforces one to five candidates, a frozen bounded writer scope, separate native confirmation for each action, a full-lifetime account lock, and the existing journal/dispatch-guard path. These are controller verification findings, not an expansion of the independent review's scope. Production release and actual live account results remain outstanding.

## Historical baseline status

Offline implementation and packaged smoke verification completed. **Live Gmail trash/restore remains release-disabled. This is not a completed Gate B release or independent review approval.** Permanent deletion is not implemented.

The latest full source test run returned **384 passed in 77.05 seconds**. A verification refresh exposed a timing-sensitive 100,000-message benchmark failure. Two small analytics optimizations removed redundant unknown-size counter writes and per-label domain-validation allocations; a domain-boundary equivalence regression was added. The original two-second performance threshold remains unchanged. Global Ruff returned exactly one error: `src/inbox_reclaimer/cli.py:568 E402` (the sender-command registration import is below other definitions). A tool-approval request for moving that import expired; the operator has not subsequently approved those edits. The error has neither been suppressed nor bypassed.

All delegated implementers/reviewers timed out without a final verdict. Their files were inspected rather than assumed complete. In particular, the final transport worker left regression tests but not the corresponding implementation; the controller completed the missing transport changes and reran the tests. Passing tests are not a substitute for the missing independent spec/quality review.

## Requirement-to-solution mapping

| Requirement | Implementation and evidence | Boundary |
|---|---|---|
| Target one exact sender without a whole-mailbox scan | `sender/selection.py`; quoted `from:` query in `sender/gmail.py`; exact metadata comparison; `test_sender_selection.py`, `test_sender_google.py` | Gmail search is candidate retrieval, not eligibility authority. |
| Inspect at most 1,000 distinct candidates | Cap includes excluded/missing records; deduplicated pagination; fixture larger than the cap | Additional thread-safety reads are required; no guarantee of globally newest-first order. |
| Preserve authoritative inventory and protections | Separate immutable sender selection; no cache publication; existing label, sender and SENT-thread checks | SENT-thread evidence is a conservative heuristic. |
| Preview and explicit confirmation | Native local account/membership view, account entry and acknowledgement; preview is CLI default; `test_sender_ui.py`, `test_sender_commands.py` | No CLI/JSON auto-approval flag. Native Windows widgets were exercised using synthetic data; no real-mail confirmation was operated. |
| Durable intent before effects | Namespaced tables in the existing journal; immutable scope, event/challenge uniqueness, expiry validation and per-step intents; `test_sender_execution.py` | The existing Gate A journal tables/triggers remain closed. |
| No intentional INBOX/UNREAD removal on trash | `batchModify` body contains only selected IDs and `addLabelIds: [TRASH]`; transport regression verifies no `removeLabelIds` | Provider-side label behavior remains a live-test requirement. |
| Fresh checks at actual dispatch | Executor installs a one-shot local guard; transport invokes it after final identity checks/request construction and immediately before the non-retrying SDK call | Missing/stale guards prevent the call; preparation is spent even on invalid attempts. |
| Shared configurable quota accounting | Named trash/untrash/modify costs in `QuotaConfig`; one shared reservation; restore reserves the larger configured step cost | Local accounting is not a provider billing measurement. Quota configuration cannot enable writes. |
| Restore from confirmed tool-owned evidence | Source-operation binding, original-label comparison, separately journaled untrash/repair, external-change conflict handling | Unsupported changes and uncertain results stop the workflow; labels are never wholesale replaced. |
| Crash recovery without blind replay | Real child process exits after committing intent; a new process/connection acquires the released lock, classifies the operation unknown and refuses further effects; `test_sender_process.py` | Unknown outcomes remain blocked for operator review; this increment does not automatically resolve them. |
| Narrow, explicit OAuth escalation | Separate locally operated helper; actual grant/client/account validation; existing-token preservation tests; `test_sender_authorization.py` | Live consent remains gated. `gmail.modify` also permits sending, although this application exposes no send operation. |
| Minimal graph/checkpoint disclosure | Opaque account/plan/approval references and counters only; completed graph replay does not repeat effects; `test_sender_workflow.py` | A graph resume is not authorization. |
| Closed live release and no permanent deletion | Constructor/CLI gates reject before live access; architecture and command tests | No live Gmail read, consent, trash, restore or delete was performed during this verification. |

## Actual verification

- Full suite: `pytest -q --junitxml=docs/evidence/sender-junit.xml` — **384 passed**.
- Focused transport/executor/quota run after recovering the incomplete worker output — **120 passed**.
- Global lint: `ruff check src tests scripts` — **one E402 error**, described above.
- Build: `uv build --offline` — wheel and source archive produced successfully.
- Installed-package smoke: the wheel was installed with `uv pip install --offline --target ... --no-deps` into a temporary directory outside the checkout. Dependencies were reused from the project virtual environment; this was not a clean dependency-resolution test.
- The child process asserted application-module provenance under that installed directory, loaded the wheel's declared `reclaim` console entry point, and exercised the synthetic sender preview.
- Packaged result: **30 candidates, 28 eligible, zero approvals, no mail changes, exit 0**. The live `--execute` command returned **exit 2**, as required by the closed release gate. No credential file was created.
- Latest packaged regressions checked: exhaustive short domain-label boundary equivalence, packaged analytics matching the verified source, dispatch-guard presence, and constructor-level live gate. Earlier package verification also covered integer/float timestamp digest stability and named trash quota costs.
- Both archives were checked for required package resources and absence of credential/profile database files.
- The synthetic report was browser-inspected earlier: 28 table rows, no script tags, no remote assets, no horizontal page overflow, and explicit synthetic/no-approval labels.

## Evidence and artifacts

- `docs/evidence/sender-junit.xml`: full-suite result.
- `docs/evidence/report-sender-synthetic.html`: private synthetic browser preview.
- `docs/evidence/sender-cli.json`: source-entry-point synthetic smoke evidence.
- `dist/inbox_reclaimer-0.1.0-py3-none-any.whl`
- `dist/inbox_reclaimer-0.1.0.tar.gz`
- `dist/sender-verification.json`: installed-wheel results and SHA-256 hashes, kept outside the archives they describe.

## Historical blocker list (import cleanup is now resolved)

1. Obtain explicit operator approval for the pending CLI import-placement cleanup; rerun lint and the full suite after that edit, then rebuild/reverify the changed artifact.
2. Complete independent spec and quality review. The timed-out reviewers supplied no approval.
3. Complete the full Gate B compliance/release review, including approval revocation/expiry audit semantics and handling of unresolved operations. This increment has no standalone approval-revocation command and no automatic resolution of unknown outcomes.
4. Only after explicit operator authorization, conduct the specification's disposable-account live trash/restore, label-transition and failure/recovery tests. No existing account or credentials have been selected for that work.
5. Keep the live release gate closed until those prerequisites are satisfied. No environment variable or command-line option bypasses it.

Compliance summary: the bounded sender-preview feature and conservative offline execution components are implemented and tested. The package is verifiably installable and its preview works with synthetic data. **Full Gate B compliance, clean global lint and live mutation readiness are not claimed.**
