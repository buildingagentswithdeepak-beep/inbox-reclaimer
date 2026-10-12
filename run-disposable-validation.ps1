# Run locally in PowerShell. Never paste tokens or sign-in URLs into chat.
[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Preview', 'Trash', 'Restore', 'Status', 'Reconcile', 'Resume')]
    [string]$Stage = 'Prepare',
    [string]$Account,
    [string]$Sender,
    [string]$ClientFile,
    [string]$SourcePlan,
    [string]$Plan,
    [string]$Operation,
    [ValidateRange(1, 5)]
    [int]$MaxMessages = 5,
    [switch]$ManualBrowser
)

$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$helper = Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\skills\productivity\google-workspace\scripts'
$homePath = Join-Path $env:USERPROFILE 'inbox-reclaimer-validation'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual environment is missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $helper '_hermes_home.py'))) { throw 'Installed workspace helper is missing.' }
if (-not $Account) { $Account = Read-Host 'Disposable Gmail account email (not your normal mailbox)' }
if (-not $Sender) { $Sender = Read-Host 'Exact sender address of disposable test messages' }
if ($Stage -eq 'Restore' -and -not $SourcePlan) { $SourcePlan = Read-Host 'Confirmed trash plan ID from the local result' }
if ($Stage -eq 'Resume' -and -not $Plan) { $Plan = Read-Host 'Existing immutable plan ID to resume with fresh native approval' }
if ($SourcePlan -and $Stage -ne 'Restore') { throw '-SourcePlan is only valid for Restore.' }
if ($Plan -and $Stage -ne 'Resume') { throw '-Plan is only valid for Resume.' }
if ($Operation -and $Stage -ne 'Reconcile') { throw '-Operation is only valid for Reconcile.' }

Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$common = @('--workspace-scripts', $helper, '--account', $Account, '--sender', $Sender, '--max-messages', "$MaxMessages")
if ($ManualBrowser) { $common += '--manual-browser' }

function Invoke-Validation([string]$Action, [string[]]$Extra = @()) {
    & $python -m inbox_reclaimer.sender.validation $Action @common @Extra
    if ($LASTEXITCODE -ne 0) {
        throw 'Validation stopped. Do not blindly retry a mutation; inspect the local status and account.'
    }
}

Write-Host 'DISPOSABLE-ACCOUNT VALIDATION ONLY. Normal production cleanup stays disabled.'
Write-Host "Dedicated credentials: $homePath"
if ($Stage -eq 'Prepare') {
    # Validate and restrict the dedicated folder before writing a client configuration.
    & $python -c 'from inbox_reclaimer.sender.validation_scope import DisposableValidation,validation_home; from inbox_reclaimer.profile import ProfilePaths,make_private; import sys; s=DisposableValidation(sys.argv[1],sys.argv[2]); h=validation_home(); s.check_home(h); h.mkdir(parents=True,exist_ok=True); make_private(h,directory=True); ProfilePaths(h).initialize()' $Account $Sender
    if ($LASTEXITCODE -ne 0) { throw 'Cannot initialize the isolated private profile.' }
    $target = Join-Path $homePath 'google_client_secret.json'
    if (-not (Test-Path -LiteralPath $target)) {
        if (-not $ClientFile) { $ClientFile = Read-Host 'Path to your downloaded Google Desktop OAuth client JSON (not a token file)' }
        # File.Copy overwrite=false preserves a configuration created by another process.
        [System.IO.File]::Copy((Resolve-Path -LiteralPath $ClientFile).Path, $target, $false)
    }
    Invoke-Validation 'check'
    if (-not (Test-Path -LiteralPath (Join-Path $homePath 'google_token.json'))) {
        Invoke-Validation 'sign-in'
    }
    Write-Host 'Next is Gmail modify consent. The grant also permits sending, but this app has no send operation.'
    Write-Host 'Authorization is not approval to change messages. No messages are moved in Prepare.'
    Invoke-Validation 'authorize-modify'
    Invoke-Validation 'preview'
    Write-Host 'Preparation/preview finished. Nothing moved. Use -Stage Trash separately only after reviewing the preview.'
} elseif ($Stage -eq 'Restore') {
    Invoke-Validation 'restore' @('--source-plan', $SourcePlan)
} elseif ($Stage -eq 'Resume') {
    Invoke-Validation 'resume' @('--plan', $Plan)
} elseif ($Stage -eq 'Reconcile' -and $Operation) {
    Invoke-Validation 'reconcile' @('--operation', $Operation)
} else {
    Invoke-Validation $Stage.ToLowerInvariant()
}
