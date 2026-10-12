# Production sender Trash: release checkpoint

> **Current decision: sender Trash/Restore is released after the final scoped reviews passed.** See [SENDER_RELEASE_DECISION.md](SENDER_RELEASE_DECISION.md) for the authoritative decision and [PRODUCTION_RUNBOOK.md](PRODUCTION_RUNBOOK.md) for local operation. The entries below preserve historical review failures and remediation; their earlier closed/open status is not the current gate state.

## Recovery/resume implementation follow-up

The controller took ownership after both implementation workers timed out without summaries. Their partial source was not accepted as verified. The incomplete recovery-group defect was reproduced and fixed by requiring the entire declared member set to be present, account/source-bound and unchanged before the resolution view clears any member. Recovery and reconciliation tests then passed (64 tests).

The CLI now supports local `sender-reconcile` and immutable-plan `sender-resume` (preview/list by default, native approval for execution, separate rejection). Disposable validation adds Resume without raising its five-candidate ceiling. Main-profile cap remains1,000; neither path re-enumerates an existing plan during resume. The production gate and reporting use the same build-time release decision, currently closed; no flag/environment override exists.

Two additional workflow regressions were reproduced and fixed: interrupted local preparation now revokes the prior active approval and creates a durable native-approval boundary; a blocked run can reopen that boundary only after the journal confirms all account blockers resolved. Both paths retain frozen membership and never replay attempted messages. A later full run exposed an early-crash checkpoint edge: durable approval-node writes can leave `ready` state, a stale interrupt and no scheduled next task. This is not completion. Explicit validated resumption reconstructs dispatch scheduling; journal recovery still precedes any possible effect. Only true completed/rejected states are final. The synthetic subprocess harness also now classifies expected `ReclaimError` refusals correctly.

The first complete post-takeover run returned550 passed,5 failed,1 skipped; all five failing cases subsequently passed after the checkpoint/harness fixes. They are retained here rather than hidden. Final full-suite and rebuilt-artifact results are reported in the verification session. Tests include real second-process approval/list/reject and crash boundaries around intent, dispatch, response, outcome/checkpoint commits and audit export; durable synthetic call logs prove no duplicate effects. Child tests import the actual application-under-test (including isolated wheels), not an unconditional source-checkout override.

A later verification run returned553 passed,2 failed,1 skipped: an unchanged analytics threshold failed at2.843 seconds and one terminal-inspection reference was missing from a lagging checkpoint. The controller fixed the latter by preserving validated references when reconstructing dispatch and permitting terminal inspection only for the checkpoint reference or an approval already attached to this plan's authoritative journal intents. This cannot authorize a write or admit a newly minted/unrelated approval. A deterministic missing-reference regression was added. The49-test follow-up (workflow, exact failed subprocess case, complete analytics suite) passed; the analytics threshold remained unchanged and its prior failure remains disclosed.

See `RECOVERY_RESUME.md` for local command boundaries. Earlier open-item sections below are historical review findings: their recovery/resume implementations now exist, with final validation and release decision separate. The operator's previous live round-trip remains accepted. No new Gmail operation was performed by the controller. No blanket independent review approval is claimed: timed-out reviews supplied no verdict.

## Scope and assumptions

The requested production scope is one exact sender, at most **1,000 distinct candidates inspected per run**, excluding protected/ineligible messages. It is not unlimited "all sender mail", a newest-first guarantee, or permanent deletion. Native review freezes exact selected IDs and each dispatched message receives fresh checks. Implementation authorization is not permission for the assistant to change the mailbox.

Revocation is an additive, denial-only journal record. The specification requires revoked/expired approvals to block dispatch but does not prescribe a CLI. `sender-revoke --approval <id>` and `sender-approvals` provide that local interface. These commands use the existing account-serialized session; revocation is not an emergency cancellation of a running request. Stop execution, inspect/reconcile any interrupted outcome, then revoke before another execution. An API request already sent cannot be recalled.

## Verified live evidence

The operator reported completing manual recovery and a fresh one-message round-trip. The controller verified the dedicated test journal using SQLite `mode=ro`, without Gmail access, schema changes, or credential output:

- One historical unknown Trash operation remains unchanged.
- One external recovery record exists, with reconstructible matching approved digest.
- One new Trash operation is confirmed.
- One linked untrash and one linked label-repair operation are confirmed.
- Original labels: `CATEGORY_UPDATES, INBOX`.
- Trashed labels: `CATEGORY_UPDATES, TRASH`.
- Restored labels: `CATEGORY_UPDATES, INBOX`.
- Full allowlisted original/restored metadata images compare equal.
- Zero unresolved sender operations, zero unresolved legacy operations, zero incomplete label repairs.

This is a verified journal record of the operator's live run plus their report of success, not a fresh independent remote read or evidence for every Gate B fault case. No additional mailbox mutation was requested by the controller.

## Release review and traceability

| Requirement | Implementation / evidence | State |
|---|---|---|
| 1,000 candidate ceiling | sender models, selection, CLI and existing cap tests | Implemented; unchanged |
| Separate exact-message native approval | confirmation + journal scope validation | Implemented; existing synthetic UI tests and operator live approvals |
| Preserve historical uncertainty; no blind replay | immutable original outcome plus separately approved reconciliation | Live recovery record verified |
| Trash → untrash → label repair | executor and Google adapter | One operator live round-trip verified |
| §4.5 / Gate B revoked approvals block writes | append-only sender_approval_invalidations; preflight and final dispatch validation; SQL intent trigger | Added; synthetic second-connection revocation blocks final send |
| §4.5 expired approvals recorded | expiry append on external validation/status; unchanged approval and original lifetime | Added; expiry inside an intent transaction still blocks immediately, audit appended on next preflight/status |
| Audit atomicity | invalidation and event in same journal transaction | Tested rollback and reopening; no rewriting approval evidence |
| General Gate B fault/restore/graph matrix | Independent reviews plus controller source verification | Review complete: open blockers below; not certified |
| Production gate | require_live_release() | Closed: recovery/resume blockers remain |
| Permanent deletion | Gate C | Disabled, outside requested scope |

## Verification

Following the approval lifecycle change: global Ruff passed; 44 affected tests passed; full source suite returned **456 passed, 1 skipped in 107.34 seconds**. The unchanged two-second analytics benchmark passed in this run; earlier host-sensitive failures remain recorded, so this is a passing run rather than a guaranteed latency claim. The skip is the existing Windows symlink-privilege test.

## Analytics verification refresh

A subsequent full-suite refresh failed only the distinct-sender 100k analytics benchmark: 2.209 seconds against the unchanged 2-second threshold (455 passed, 1 failed, 1 skipped). An isolated unprofiled diagnostic measured 1.369 wall / 1.313 CPU seconds; variability alone does not identify a host cause. Profiling identified two full sender sorts for top-20 output and redundant zero-initialize/update work for every new sender group.

The report now uses `heapq.nsmallest(20, ...)` with identical ordering keys and initializes a new sender metric directly from its first record. Six ranking-oracle cases cover empty/small/large groups, ties, unknown senders and sizes. The first sort-only change still failed at 2.003 seconds; that failure is retained. With both changes, all 29 analytics tests and global Ruff passed. Complete-report equality against the preceding wheel held for100000 distinct display-name senders. Bounded alternating timings were previous 0.798/1.490 wall seconds and updated 0.660/0.684; these are measured samples, not a latency guarantee. The acceptance threshold was not changed. Final full-suite results are reported in the verification session.

## Independent review verdict and remaining work

Both bounded read-only reviews completed. Neither is blanket Gate B certification. Controller source inspection corroborated the following findings:

1. **Stale restore source (fixed in this follow-up):** an older confirmed Trash operation remained selectable after external untrash and a later Trash, even if the earlier preimage differed. The journal now rejects any source superseded by a later same-account/message Trash intent, both through `source_operation()` and the SQL intent trigger. Insertion order is used rather than timestamps, which can tie or move backwards. Conservative policy assumption: even a later skipped/failed intent supersedes the old source; ambiguous or unsuccessful later attempts do not revive old provenance. Six new tests failed before the fix and now pass, including equal-postimage/different-preimage cycles, already-approved stale plans, direct SQL intent insertion and pending/unknown/failed/skipped later intents. No historical record is rewritten. This does not prove detection of every unobserved external Gmail edit.
2. **Interrupted restore recovery (open):** external reconciliation currently supports only one unknown Trash operation. Unknown untrash/repair and partial restores block safely but lack a supported recovery exit, even after manual recovery. Required work: separately confirmed, evidence-bound external reconciliation of restore steps, preserving original unknown records and source relationships; no blind retry.
3. **Renewed approval and graph recovery (open):** sender workflow persists its original approval reference and rejects replacement approvals. It cannot resume an interrupted plan under fresh trusted approval after expiry. The sender graph has no approval interrupt/list/reject transitions; its current graph test covers completed same-process replay, and its process-death test does not resume a real sender graph checkpoint. Required work: trusted reapproval/resume preserving immutable membership and operation deduplication, with second-process checkpoint and fault-boundary tests.
4. **Production integration (open):** production recovery has no sender reconciliation route, the shared session still reports Gate A/read-only, and status hardcodes live release as false. Update these surfaces with the actual release decision, not by merely removing the release check.

Confirmed controls from the second review: CLI/selection/plan enforce the1,000-candidate cap; native approval precedes writer construction; execution holds the account lock; verified token grants/account are checked before dispatch; reachable writes exclude permanent deletion. Approval revocation/expiry was independently assigned to the controller and has since been implemented/tested.

**Decision: Gate B remains closed.** The operator's live round-trip remains accepted. Further work is on application recovery/workflow and its tests, not repeated identical operator smoke tests. The latest follow-up targeted suite returned **61 passed**, with global Ruff passing. Final full-suite/package results are recorded in the verification session.

## Operator impact

No new live test is requested until this release review identifies the specific remaining evidence. A successful live round-trip is complete and must not be repeatedly requested as a substitute for review. Production and the separate five-candidate disposable validation scope remain distinct.
