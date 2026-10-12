# Sender recovery and resume — local operator runbook

## Boundaries

- Production mutation availability is reported separately from implementation/tests. A recovery command does **not** open the production Trash gate.
- `sender-reconcile` reads current Gmail metadata, asks for native acknowledgement, and writes only the local audit journal. It never sends a Gmail write or replays an unknown request.
- `sender-resume --plan <id>` inspects the frozen plan and persists/inspects its approval boundary. It does not discover additional mail or create an approval.
- `sender-resume --plan <id> --execute` requests fresh native approval and may change real mail **only if the production release gate is open**. Previously attempted messages are never replayed. The selected plan remains capped at1,000 candidates, including any already attempted or skipped entries.
- `sender-resume --plan <id> --reject` is a local, terminal rejection. It changes no mail. Later reconsideration requires a new plan/approval, not reopening rejection as consent.
- Native confirmation is authoritative. An earlier separate `sender-cleanup` preview may enumerate a different selection than a later new `sender-cleanup --execute`; use the returned persisted plan ID with `sender-resume` to retain exact membership.
- Audit acknowledgements are not approvals for new mutations. Original UNKNOWN and confirmed operation records are preserved. An historical unknown count may remain nonzero after its uncertainty has been separately acknowledged.

## Main profile: inspect and recover

Use the same Hermes/workspace profile that created the operation; do not move/copy credentials or journals between the production and disposable profiles. The following command block explicitly uses the installed workspace helper and does not print credentials.

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
$python = Join-Path $PWD '.venv\Scripts\python.exe'
$helper = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\skills\productivity\google-workspace\scripts'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
# Resolve HERMES_HOME to the intended profile before continuing; keep the same
# value used for the original command. Do not point this at another account.
& $python -m inbox_reclaimer --workspace-scripts $helper sender-status
```

Inspect `blocked`, `recovery_references`, and the recorded plan/operation references. Stop on any unexpected profile/account. If an effect is uncertain, **do not rerun Trash/Restore**.

The recovery route verifies external restoration to the original pre-Trash metadata, including original labels. If needed, the operator restores that exact state in Gmail manually. Changed thread/sender/metadata, missing original labels or missing messages are not silently ignored. Then:

```powershell
$sender = Read-Host 'Exact sender of the manually recovered message'
$operation = Read-Host 'Operation reference from sender-status'
& $python -m inbox_reclaimer --workspace-scripts $helper sender-reconcile `
    --sender $sender --operation $operation
```

Read the native recovery window and approve only the exact intended message and source evidence. The application reads the state again after confirmation before recording recovery. One acknowledged source group cannot clear unrelated uncertain messages. Run `sender-status` again; continue only after blockers are understood and resolved.

## Main profile: inspect or resume a saved plan

```powershell
$plan = Read-Host 'Existing immutable plan ID'
& $python -m inbox_reclaimer --workspace-scripts $helper sender-resume --plan $plan
```

Inspect candidate/attempted/remaining counts and status. Only after production release, and only if you intend real mailbox changes:

```powershell
& $python -m inbox_reclaimer --workspace-scripts $helper sender-resume --plan $plan --execute
```

This is a new native approval, not automatic extension of an expired approval. Already-completed workflows are inspection-only. Unknown outcomes require reconciliation, not fresh consent alone. Do not retry after an error without checking the journal state.

## Disposable validation profile

The existing launcher keeps its independent five-candidate ceiling, verified expected account/sender, separate credentials, and fresh validation lifetime. There is no production-limit override in this launcher.

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
$account = Read-Host 'Disposable Gmail account email'
$sender = Read-Host 'Exact disposable test sender'
$plan = Read-Host 'Existing disposable validation plan ID'
.\run-disposable-validation.ps1 -Stage Resume -Account $account -Sender $sender -Plan $plan
```

`Resume` is a mutation request requiring native approval, not a preview. `Status` has no Gmail writes; `Reconcile -Operation <id>` verifies and acknowledges an external recovery only. Do not run these merely to repeat the already-accepted live round-trip.

## Limitations

- Revocation uses the account lock and cannot recall an already-sent Gmail request.
- Gmail has no atomic compare-and-write for these local checks; a small external-edit race remains.
- Manual recovery cannot be acknowledged if the required exact original image cannot be verified. The app fails closed rather than guessing.
- A resumed plan may include completed entries in the native full list; the journal prevents their replay. Missing metadata can prevent review and should be investigated rather than bypassed.
- Graph checkpoints are orchestration records, never authorization. Original journal intent/outcomes remain authoritative.
