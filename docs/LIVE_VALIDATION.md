# Disposable-account live validation (pre-release)

## Purpose and authorization boundary
The operator requested real sender-to-Trash capability and approved completing code fixes, stating that a disposable Gmail account with test messages is available. This authorizes implementation, not this agent's access to credentials or mailbox mutations. The operator must run sign-in and each test action locally.

The original Gate B release requires isolated live tests before production enablement. A separate validation entry point is required to perform those tests; removing the unconditional production gate without evidence is not acceptable.

## Assumptions
- One fixed dedicated test home: `~/inbox-reclaimer-validation`. No use of the normal Hermes profile or token. The installed profile helper resolves this explicit home.
- Initial live tests are capped at five candidates, not 1,000, to minimize the affected set. Every native confirmation freezes exact IDs. Missing/protected candidates consume a slot.
- Operator supplies the disposable account email and exact test sender. The provider-verified account must match before message reads, and the writer is additionally bound to the OAuth client/account ID and approved IDs.
- Validation permission lasts at most 15 minutes in the current process and cannot enable the ordinary CLI. A new invocation still requires fresh approval for each trash/restore plan.

## Design
`validation_scope.py` defines an immutable, expiring disposable-account scope. The existing closed gate accepts this scope only for dedicated validation calls. The actual Google adapter enforces the dedicated credential directory, verified identity, and maximum five frozen IDs at the write boundary. It continues to require a fresh executor dispatch guard, actual grants, and quota reservation.

`python -m inbox_reclaimer.sender.validation` supports local client check, first-time readonly sign-in, modify consent, preview, trash, and restore. It uses the existing journal, executor, native confirmation and graph implementation. Restore accepts only a source sender-trash plan from the same account and sender. Unknown operations block new effects; they are never automatically retried or marked successful.

Production `sender-cleanup --execute`, ordinary modify authorization and permanent deletion remain closed. There is no environment flag to open them. Native mutation approval is never replaced by account setup/consent.

## Required verification
Offline: default gates unchanged; arbitrary scope/expired scope/wrong home/wrong account/client/IDs rejected; five-message cap; account mismatch before message reads; cancel means no writer; account-bound source restore; no-network check; noninteractive execution rejected; failure output does not claim zero effects after dispatch; journal/lock/privacy behavior retained.
Live, operator-controlled: sign in only to the disposable account, preview test sender, separately confirm trash and restore, verify provider label transitions against journal observations and report counts. Cancellation, unavailable messages, conflicts, and interrupted outcomes must not become blind retries. A successful round-trip alone does not certify full Gate B fault/recovery behavior or authorize production release.

## Operator runbook (PowerShell on this machine)

Prerequisite: Gmail API enabled for your Google Desktop OAuth client, and the disposable Gmail address added as a test user if the Google project is in External/Testing mode. Use your downloaded **Desktop client JSON**, not an existing token, service account key, Gmail password or app password. Keep its contents local.

From a local PowerShell terminal:

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
.\run-disposable-validation.ps1 -Stage Prepare
```

The launcher prompts locally for the disposable account email, exact test sender, and (if absent) Desktop-client file path. It privately copies only the client configuration into the dedicated folder without overwriting an existing file. It runs a no-network configuration check, first-time readonly sign-in if needed, separately disclosed Gmail modify consent, and sender preview. **Prepare does not move mail.** If no browser opens, repeat the setup command with `-ManualBrowser` and open the initial sign-in link locally; never paste it or a callback into chat. Do not run the same setup simultaneously in two terminals.

After reviewing the preview and confirming the sender contains only disposable messages, run:

```powershell
.\run-disposable-validation.ps1 -Stage Trash -MaxMessages 1
```

The native window shows the verified account, exact IDs and action. Review it yourself, acknowledge the consequences, type the exact account email and explicitly confirm. Cancel makes no changes. This invokes the **real Gmail API**, not a demo. Start with one message; the hard maximum is five candidates per invocation. Protected messages are skipped. Gmail automatically deletes messages left in Trash after its retention period, so perform restoration promptly.

Keep the opaque trash `plan_id` from the local output. To separately approve restoration:

```powershell
.\run-disposable-validation.ps1 -Stage Restore -SourcePlan '<trash-plan-id>'
.\run-disposable-validation.ps1 -Stage Status
```

The launcher prompts for the same disposable account and sender each time; optional `-Account` and `-Sender` parameters avoid repeating these. A `confirmed` journal outcome means the application observed the expected labels after the call; still inspect the disposable mailbox yourself. Unknown outcomes block further effects and require review rather than replay. Do not replace journal files or delete state to clear a block. No automatic production enablement follows a successful test.

Record only safe evidence for review: command exit status, opaque plan reference, confirmed/unknown/failed counts, whether the expected Trash/restore label transitions were visible, and whether cancellation behaved correctly. Do not share credentials, authorization URLs, message subjects or contents.

If a PowerShell execution policy blocks the script, use the module directly from the same local terminal after placing the client JSON in the dedicated private folder. The supported arguments are shown by `.\.venv\Scripts\python.exe -m inbox_reclaimer.sender.validation --help`; no security-policy change is needed for that route.

## Audited acknowledgement after manual recovery

**Assumption / narrow recovery policy:** the specification requires reconciliation but does not prescribe an external-recovery disposition. This implementation supports exactly one unknown Trash attempt, after the operator has manually restored the complete original metadata/label state. It does not support unresolved untrash/repair or multiple unknown operations. These cases remain blocked for review.

1. Restore the affected test message in Gmail yourself. Preserve all original labels, including Inbox/unread/custom labels. Do not delete or edit journal files.
2. Run this locally; it performs reads and a locally approved audit write, **not Gmail mutations**:

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
$account = Read-Host "Disposable Gmail account email"
$sender = Read-Host "Exact sender of the affected test message"
.\run-disposable-validation.ps1 -Stage Reconcile -Account $account -Sender $sender
```

3. Review the native window, acknowledge external recovery and enter the exact account email. The message is checked against the original preimage both before and after confirmation. Cancellation, changed account/state, a stale observation or an expired approval records no resolution.
4. Check status:

```powershell
.\run-disposable-validation.ps1 -Stage Status -Account $account -Sender $sender
```

`outcomes.unknown` retains the original historical count. `externally_reconciled` separately counts acknowledged external recoveries; `blocked` describes whether unresolved operations still prevent effects. An immutable `sender_resolutions` record and the audit event are committed together. The original operation is not rewritten as confirmed, and its plan still cannot supply restore provenance or be replayed. A new test requires a new plan and separate native approval. Reconciliation never enables production.

The controller has implemented and tested this command with synthetic profiles. It has not approved or run it against the operator's real journal. A prior, explicitly authorized labels-only live read found the message in Trash; that snapshot is not confirmation of subsequent manual recovery.

## Release status
Implementation and offline verification do not constitute live evidence. Production enablement remains a separate reviewed release decision after actual disposable-account test evidence and remaining Gate B review.
