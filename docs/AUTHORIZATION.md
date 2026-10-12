# First-time read-only authorization — implementation and verification

## Assumptions
- User elects first-time Gmail authorization and supplies a Google Desktop OAuth client in the selected profile.
- The helper only supports a profile without `google_token.json`. Replacement, grant escalation and revocation require a separate reviewed workflow.
- Adoption uses a same-filesystem hard link for exclusive, atomic publication. Unsupported filesystems fail closed; no overwrite fallback exists.

## Architecture and contracts
`reclaim-auth` is a separate interactive entry point in `authorization.py`; it does not change the `reclaim` application's hard Gate A boundary.

Installed profile helper → local Desktop client validation → profile setup lock → Google installed-app flow (PKCE, loopback, timeout) → private staged authorized-user token → existing Google adapter's actual-grant/account checks → existing-journal account check → operator types exact email → account lock and recheck → exclusive token publication.

Only `gmail.readonly` is requested and only that exact verified scope set is accepted. Authentication reads token metadata and Gmail getProfile; it does not enumerate messages. Client/refresh-token information never enters normal output. Known OAuth debug loggers are suppressed. Local confirmation is not batch authorization.

No old token is read or replaced. Failed validation, denied consent, local cancellation, unexpected scopes, client/account mismatch and competing token creation prevent adoption. Private staging is cleaned on normal exits; forced termination can leave a private `.oauth-*` directory under app state. Cancelling locally does not revoke an already-issued Google grant.

The optional `auth` extra pins `google-auth-oauthlib==1.2.2`; the lock includes `requests-oauthlib==2.0.0` and `oauthlib==3.3.1`. The base application does not require browser consent dependencies. Run tests with the auth extra installed to exercise the SDK-call contract test rather than skip it.

## Actual verification
- `uv sync --frozen --extra auth`: installed the optional SDK and the `reclaim-auth.exe` entry point.
- `ruff check src tests scripts`: All checks passed.
- `pytest -q --tb=short`: **173 passed in 34.02s**.
- The helper's real `--check` command used the installed home helper and selected coder profile. Output: **Desktop client configuration valid; token absent. No Google request was made.** No credential values were emitted.
- New tests cover exclusive adoption, current-token preservation, a competing token creation, journal account mismatch, wrong OAuth client, missing refresh token, failed consent/validation/confirmation, local rejection, normal staging cleanup, non-Google endpoints, exact actual scope checks, noninteractive refusal, and the PKCE/loopback/timeout/no-URL-output SDK contract.

## Remaining live gate
The browser consent and real Google grant/profile exchange have **not** been executed by the agent. The operator must run the README's local sign-in command, review consent, confirm the actual account and then run the read-only scan. Do not infer successful Google authorization from the offline tests or `--check`.

## Spec mapping
- §9: selected installed-helper profile; private local state and OS-held locks.
- §11.1: first-time analyze/propose scope only, actual grant/account validation, staged credentials, no existing-token replacement. This does not implement Gate B/C scope escalation.
- §11.2: local-only interaction, secret-safe output and private token storage.
- §14: offline fault/contract tests; live authorization explicitly unverified until the operator completes consent.

See README.md, section “First-time read-only sign-in,” for exact PowerShell commands.
