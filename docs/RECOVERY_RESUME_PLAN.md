# Recovery and reapproval implementation plan

## Scope / assumptions

Implement outstanding review fixes against `C:\Users\v-deegarg\specs\inbox-reclaimer-tech-spec.md` §§4.5–4.6 and Gate B. No credential or Gmail access; no production release-gate bypass; existing one-message live round-trip remains accepted evidence. Cap stays1000 candidates in production plans,5 in disposable validation. No permanent deletion.

Recovery policy assumption: external recovery is acknowledged only when fresh full allowlisted metadata equals the original pre-Trash image; no inference that an ambiguous SDK call succeeded. Unknown untrash/repair plus confirmed-but-incomplete untrash are grouped by the same source Trash operation. Acknowledgement resolves only that explicitly displayed group, atomically, without rewriting original operation outcomes. Other uncertain groups stay blocked. Operator performs any manual Gmail recovery; this implementation only reads state and appends audit records.

Reapproval policy assumption: immutable plan membership is reviewed anew; attempted IDs remain in journal and are never replayed. Approval expiry/revocation pauses for new native approval, not automatic extension. Explicit rejection is terminal for that workflow. Group recovery acknowledgement is not a new mutation approval.

## Ownership and shared contracts

- Worker R owns `sender/reconciliation.py`, `sender/journal.py`, reconciliation tests and new restore-recovery tests only. Preserve existing approval-lifecycle and stale-source protections.
- Worker W owns `sender/workflow.py`, sender workflow tests and new second-process/fault tests/helpers only. No journal changes.
- Controller owns `sender/commands.py`, `sender/validation.py`, native dialog integration if required, launcher, CLI, documentation and composition tests. Never edit worker-owned files until their completion signal.

### Recovery contract

Preserve `reconcile_external(journal, adapter, identity, sender, *, confirm=None, clock=time.time, guard=None)`; add optional `operation_id=None` for explicit target selection when multiple groups exist and optional `validation=True` for disclosure. No new writer methods. Existing callers remain valid. Return `reconciled` count, `mail_changed=False`, blocked/current disposition. Exact messages shown and local approval checked. Target lookup MUST bind account, sender, source, IDs and all related unknown/partial records; plans/digests must retain all reconstruction inputs.

### Workflow contract

Preserve `run_sender_workflow(paths, identity, journal, executor, plan, approval_id=None, *, decision=None)` (existing positional approval callers supported). `decision` may be `list`/`reject` only; approval is a journal reference, never a Boolean/resume approval payload. With no approval ID, persist a real graph interrupt and return `status='awaiting_approval'`. `executor=None` is valid while awaiting/listing/rejecting; never invoke it there. Supplying approval reference must validate the persisted journal approval against exact immutable plan/account before any dispatch. Existing completed workflows remain inspection-only. Invalid/mismatched replacement references must not mutate checkpoint authority. On approval expiry/revocation, return to a durable awaiting-approval boundary; native reapproval is performed outside the graph by the local composition root. Keep checkpoint free of message content and identity strings, only opaque refs/counts/status. Unknown account operations halt rather than resume writes.

## Tasks and verification

1. R: Add failing tests for untrash/repair timeouts, confirmed partial untrash at crash, multiple groups, changed/source/current evidence, cancellation, expired/wrong approval, immutable/audited atomic records. Implement targeted recovery checks/schema migration preserving old resolutions and all original records. Run affected tests.
2. W: Add failing graph tests for actual interrupt/list/reject, expiration/new approval, fabricated refs, duplicates, second-process reopen. Use real journal/checkpointer + fake external adapter. Add crash boundaries with durable external call marker; prove no replay after uncertain dispatch/outcome/checkpoint failures. Preserve existing API and state privacy. Run affected tests.
3. Controller: wire `sender-reconcile` read-only remote/local audit action (native approval, interactive local only, account lock). Wire `sender-resume --plan` with preview default; execute requires native reapproval and real release gate. Integrate graph preparation before confirmation, separate rejected/list interactions; keep writer deferred until successful native consent. Add disposable resume with maximum5 frozen IDs and expected sender/account. Update status to expose waiting/blocked/resolved state without claiming production enabled.
4. Controller: verify real composition against temporary synthetic profiles; native cancel, malformed references and noninteractive paths; one ownership per file.
5. Independent spec review then quality review of completed changes. Address concrete findings, do not claim gate approval from tests alone.
6. Full Ruff/pytest, isolated installed-wheel tests, exact evidence update and final compliance summary. No commit or real mailbox effects implied.

## Traceability

| Spec | Solution | Tests |
|---|---|---|
|4.5 expiry and separate human event|durable graph interruption and new journal approval|expiry/revoke/new approval/fabricated ref|
|4.5 crash no replay|journal intent authoritative across process restart|subprocess call marker and checkpoint failures|
|4.6 reconcile unknown / partial restore|atomic external-recovery group with original source target|untrash/repair/partial, exact images, other groups blocked|
|GateB process graph probe|real interrupts and second-process resume|approve/reject/list/stale ref across restart|
|GateB privacy and1000 bound|unchanged scope/protections and minimized checkpoint|composition/cap tests|
