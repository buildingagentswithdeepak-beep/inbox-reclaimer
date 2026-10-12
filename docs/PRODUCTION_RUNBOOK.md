# Production sender cleanup — local PowerShell runbook

This runbook is for the released **sender Trash/Restore workflow only**. Check the build's release status before use. Analysis/proposal commands remain read-only; permanent deletion, autonomous/chat approval and standing consent are not enabled. Preview, authorization and execution are separate stages. No command below must be run by the assistant on your mailbox.

## Assumptions and limits

- Use the existing Hermes profile that holds the intended production account's Google credentials. The isolated `inbox-reclaimer-validation` home is not your normal production profile; do not copy its credentials or journal into another profile.
- A run inspects up to **1,000 distinct sender-query candidates**, not1,000 guaranteed changes. Protected, missing or mismatched candidates consume slots. Provider listing order is not guaranteed newest-first. Thread safety reads can inspect additional messages.
- Resume retains the exact stored membership. Running a new `sender-cleanup --execute` would create a new selection: it is not execution of an earlier preview. The preview-to-execution path below uses `sender-resume --plan` instead.
- An approval lasts15 minutes. A long run may pause for fresh consent; completed/attempted messages are not replayed. Revocation waits for the account lock and cannot recall a request already sent.
- Windows native confirmation displays the account, action, exact list, digest and warnings. Cancel is the default. Do not automate the window or paste secrets/login URLs into chat.
- `gmail.modify` also permits composing/sending according to Google's permission definition; this app exposes no send operation. Scope escalation is optional and explicitly user-operated, same account/client only.
- Gmail has a small unavoidable read/write race with other clients. Detected changes cause skips, conflicts or blocked uncertainty, not speculative success/retries.

##1. Preview only — no mailbox writes

Paste this into a separately opened local PowerShell terminal. Enter the absolute existing profile folder, not a hostname-derived path. The account is printed locally before analysis. Stop if it is not the intended account.

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
$python = Join-Path $PWD '.venv\Scripts\python.exe'
$helper = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\skills\productivity\google-workspace\scripts'
$env:HERMES_HOME = Read-Host 'Absolute existing Hermes profile folder for your production Gmail account'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
if (-not (Test-Path $python) -or -not (Test-Path (Join-Path $helper '_hermes_home.py')) -or -not (Test-Path $env:HERMES_HOME)) { throw 'Check the Python, helper and profile paths before continuing.' }
& $python -c "from inbox_reclaimer.sender.models import release_status; s=release_status(); print(s); raise SystemExit(0 if s['live_mutation_released'] else 2)"
if ($LASTEXITCODE -ne 0) { throw 'This build has not passed production release.' }
$sender = Read-Host 'One exact sender email address'
$report = Join-Path $PWD 'sender-preview.html'
$previewOutput = & $python -m inbox_reclaimer --workspace-scripts $helper sender-cleanup --sender $sender --max-messages 1000 --html $report
if ($LASTEXITCODE -ne 0) { throw 'Preview failed; no execution requested.' }
$preview = ($previewOutput -join [Environment]::NewLine) | ConvertFrom-Json
$preview | Format-List
if ($preview.plan_id) {
    Write-Host "Save this immutable plan ID: $($preview.plan_id)"
    Start-Process $report
} else { Write-Host 'No eligible selection. Nothing to execute.' }
```

Keep the report local. Preview proves selection/read access, not modify permission or future eligibility. Actual execution repeats protection checks and can shrink the selected set.

##2. Optional Gmail-modify authorization — changes permission, not mail

Use only if the intended profile does not already have the required verified grant. This requires its existing read-only credentials and Desktop OAuth client JSON; it does not bypass missing onboarding. A failed/cancelled/wrong-account authorization retains old credentials. Keep browser sign-in information local.

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
$python = Join-Path $PWD '.venv\Scripts\python.exe'
$helper = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\skills\productivity\google-workspace\scripts'
$env:HERMES_HOME = Read-Host 'Same absolute production profile folder used for preview'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
& $python -m inbox_reclaimer.sender.authorization --workspace-scripts $helper --check
if ($LASTEXITCODE -ne 0) { throw 'Local OAuth-client check failed; do not continue.' }
& $python -m inbox_reclaimer.sender.authorization --workspace-scripts $helper
if ($LASTEXITCODE -ne 0) { throw 'Modify authorization was not completed. Existing credentials were retained unless separately reported otherwise.' }
```

The `--check` command does not contact Google or verify granted scopes. The following authorization step does. Never use general workspace setup to broaden unrelated Drive/send scopes as a shortcut.

##3. Execute exactly the saved selection — real mailbox changes after native approval

This is not a preview. Re-enter the same profile and saved plan ID. Read the native confirmation and approve only if its account and exact message selection are correct. The assistant does not click it for you.

```powershell
Set-Location C:\Users\v-deegarg\inbox-reclaimer
$python = Join-Path $PWD '.venv\Scripts\python.exe'
$helper = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\skills\productivity\google-workspace\scripts'
$env:HERMES_HOME = Read-Host 'Same absolute production profile folder used for preview'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$plan = Read-Host 'Exact saved plan ID from the successful preview'
& $python -m inbox_reclaimer --workspace-scripts $helper sender-resume --plan $plan --execute
if ($LASTEXITCODE -ne 0) { Write-Warning 'Inspect status before any retry. Some outcomes may be uncertain.' }
& $python -m inbox_reclaimer --workspace-scripts $helper sender-status --plan $plan
```

A failed or interrupted run is not proof that nothing changed. Do not start another cleanup blindly. If the result awaits approval, resume this same plan with a fresh native approval. If blocked, follow `RECOVERY_RESUME.md`: externally recover the exact original state and separately acknowledge it locally; reconciliation itself never writes Gmail. Historical UNKNOWN outcomes remain in the journal after an independently recorded resolution.

Restore is another explicitly approved action using the confirmed Trash plan as source: `sender-restore --source-plan <trash-plan-id>` previews a new restore plan. Execute that returned immutable restore plan through `sender-resume --plan <restore-plan-id> --execute`, with the same profile/helper setup above. Subsequent Trash cycles or external recovery invalidate older restore provenance.

## Quotas and readiness

Public Gmail documentation was reviewed during release: https://developers.google.com/workspace/gmail/api/reference/quota . It lists new-project limits6,000 user/project units per minute and1,200,000 project units per minute,80,000,000 daily threshold, and billing-change notice caveats. Existing project quotas may differ. The app's planning default4,800 units/minute is conservative but not a measurement of your cloud project's effective quota or billing. Configured effective limits and durable local daily budgets are enforced; provider failures still stop or reconcile safely. This release does not certify other applications' quota usage, your current account's grant, or end-to-end production operation before your local checks/consent.
