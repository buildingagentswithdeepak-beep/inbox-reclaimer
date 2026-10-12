# Sender Trash/Restore production release decision

##1. Assumptions and release scope

**Decision: enable the bounded sender Trash/Restore workflow (`B_passed`), not general execution or permanent deletion.** The operator explicitly requested enablement only after a passing review. Review refers to the sender extension of `C:\Users\v-deegarg\specs\inbox-reclaimer-tech-spec.md` §§4.5–4.6 and Gate B, not blanket certification of every future feature.

Limits and trust assumptions are unchanged: one exact sender; at most1,000 distinct candidates inspected per plan/run; protections may shrink effects; separately launched user-operated native confirmation; one account/client per profile; OS account lock held throughout commands; local journal/host trusted against arbitrary code or SQL tampering. Native Tk consent is an independent local workflow, not hardware-backed identity proof or protection against a compromised desktop. The independent reviewers explicitly used this caller-lock/native-approval boundary.

No target sender, production account or messages were chosen by the assistant. Enabling the application does not grant OAuth scope, approve any plan, or perform a Gmail effect.

##2. Architecture and review results

Two independent read-only reviews completed under delegation `deleg_023ced63`; each returned **scoped PASS, no concrete blocker**:

- Workflow/commands: local interactive restriction, release check before profile access, no executor before native consent, immutable stored membership, valid opaque approval references, durable reapproval boundary, journal-first recovery, terminal inspection without redispatch, supported local recovery/resume commands.
- Journal/reconciliation: complete unchanged recovery membership, original source/account binding, consumed acknowledgement events, externally recovered source invalidation, append-only uncertainty history, atomic group/audit persistence, fresh full-image observations before/after confirmation, and unrelated uncertainty remaining blocked.

These are actual returned verdicts, unlike earlier timeouts. Reviewers did not rerun tests or inspect other modules. The controller separately reviewed `executor.py`, `gmail.py`, `selection.py`, `confirmation.py`, quota configuration and gate-sensitive integration tests. No unresolved concrete blocker was found in this bounded scope.

##3. Low-level mapping to Gate B

| Requirement | Source and executable evidence |
|---|---|
| Account/action/membership/approval binding; expiry/revocation | sender models/journal/workflow; approval-lifecycle, execution, workflow and authorization suites |
| Protections and fresh required reads | selection/executor; sender selection/execution and provider-boundary tests |
| Correct label restoration and conflicts | executor/Google writer; supported delta, deleted custom label, unknown untrash/repair and external-recovery tests |
| Durable intent, no blind replay, audit independence | journal, recovery and actual second-process graph fault suite around intent/send/ack/outcome/export/checkpoint |
| Serialized account effects and process-death recovery | OS lock tests and sender process tests; purge remains unreachable |
| Dry-run/exports never authorize real effects | journal scope triggers, execution/architecture tests and replay tests |
| Real graph interrupt/list/reject/reopen/resume | SqliteSaver plus subprocess crash tests and persisted synthetic call log, not import-only checks |
| Verified actual grants; narrow consent and safe replacement | Google transport/authorization tests; one-shot final guard after identity/credential checks; SDK retries zero |
| Live fixture | Operator's approved separate-account round-trip and read-only local journal verification below |

The small concurrent Gmail-client read/write race remains disclosed. A1,000-candidate ceiling is not a promise of1,000 successful changes, unlimited sender cleanup or newest-first order. A restore conflict is not silently overwritten. If exact manual recovery cannot be verified, the account remains blocked rather than guessing.

##4. Code / configuration change

`sender.models.release_status()` now declares `live_mutation_released=True`, `release_gate=B_passed`, `candidate_cap=1000`. `require_live_release()` still enforces the decision and explicitly rejects invalid disposable-validation objects instead of falling back to production. No CLI flag or environment variable creates consent. A valid disposable scope remains independently limited to five candidates and its original home/account/IDs/lifetime.

Closed-gate regression cases remain in tests with an explicitly closed test decision. Enabled-gate tests assert live availability while preserving noninteractive/model-controlled denial, account-switch refusal, invalid-scope refusal and permanent-delete rejection. Reporting and help now describe the actual release state. The normal SDK composition test exercises unmodified release checks with SDK/network doubles, not a patched writer or bypassed approval/executor chain.

##5. Verification evidence

Before activation, the final candidate source suite returned **563 passed,1 skipped** and Ruff passed. The skip is the existing Windows symlink-privilege case, not the Windows OS-account-lock test. Earlier failures, fixes and analytics timing variability are retained in `PRODUCTION_RELEASE_REVIEW.md`; no timing threshold was relaxed.

Active project environment, verified after clearing inherited `PYTHONPATH`: Python3.11.9, langgraph1.2.8, langgraph-checkpoint-sqlite3.0.3, google-api-python-client2.170.0, pytest8.4.0, typer0.16.0. The check without clearing `PYTHONPATH` initially reported unrelated package versions; those were not accepted as project evidence. The runbook clears the variable too.

Commands used for final enabled-build verification:

```bash
unset PYTHONPATH
source .venv/Scripts/activate
ruff check src tests scripts
pytest -q --tb=short
uv build --offline
```

The final enabled-build command outputs are delivered in the release session; `dist/sender-verification.json` records checksums, installed-package provenance and actual installed-test results. Installed application tests run outside the checkout with an independently installed wheel; dependencies are reused from the verified project venv, not claimed as a clean dependency installation. No test result is inferred from this document.

##6. Live evidence, external checks and limitations

The controller refreshed only the explicitly intended disposable journal via SQLite `mode=ro`—no application initialization, migrations, Google calls or credential output. Result: one exact confirmed Trash/untrash/repair round-trip; zero unresolved sender operations; zero unresolved legacy operations; zero incomplete repairs; one external recovery acknowledgement with reconstructible matching digest. This is local journal evidence plus the operator's previous live success report, not a new remote observation. No repeat mutation was performed.

Public quota documentation was reread during release: https://developers.google.com/workspace/gmail/api/reference/quota . The configured new-project rates and method costs match the inspected published defaults; labels listing is conservatively charged as a message-list read rather than undercharged. Old projects may have different limits. The operator's private project quotas/billing and current normal-account grant were not accessed or certified. Configurable effective limits and durable local budget stops remain available, with conservative default pacing and fail-closed provider errors. No permanent-free-use claim is made.

**Operational handoff:** `PRODUCTION_RUNBOOK.md` gives self-contained local PowerShell preview, optional scope authorization, saved-plan execution and status steps. Account/sender selection and each native approval belong to the user. Production capability is enabled; a bulk production run has not been performed by the assistant. Gate C, arbitrary legacy executor paths and model-controlled effects remain disabled.
