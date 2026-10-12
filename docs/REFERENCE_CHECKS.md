# Public reference inspection

Observed during implementation, 2026-09-26 UTC (system clock read with Python).

## Gmail usage limits

Source: https://developers.google.com/workspace/gmail/api/reference/quota

The live public page was loaded in the browser and its article text inspected. It currently states:

- 6,000 units/minute/user/project and 1,200,000 units/minute/project.
- `getProfile=1`, `history.list=2`, `messages.list=5`, `messages.get=20`, `threads.get=40`, `messages.attachments.get=20`.
- 80,000,000-unit daily per-project billing threshold and notice of planned charges later in 2026.
- Qualifying previously active projects retain earlier quotas; projects created on/after May 1, 2026 use the new regime.
- Effective limits can vary by project. This inspection does not verify the operator's Cloud project or current usage.

The application's cost table agrees with this observed read-method table. Its 4,800-unit planning budget and reserve are explicit application policy, not provider promises.

## Hermes integration

Installed source inspected read-only:
`C:\Users\v-deegarg\AppData\Local\hermes\hermes-agent\skills\productivity\google-workspace\scripts\_hermes_home.py`

It delegates to `hermes_constants.get_hermes_home` when available, otherwise resolves `HERMES_HOME` internally. The application imports this helper through an explicit scripts-path adapter and does not duplicate its fallback. Profile documentation was retrieved from https://hermes-agent.nousresearch.com/docs/user-guide/profiles. No Hermes installation, skill, token, configuration or other profile was modified.

## Unverified external behavior

- Actual Google grant metadata for the user's token, credential refresh and live Gmail read/mime responses.
- OAuth consent setup/escalation, trash/untrash server label transitions, destructive batch endpoint limits/behavior, mixed-ID permanent-delete results.
- Live mailbox storage quota and quota change timing.

No Gmail account was accessed during development. Documentation and mocks do not replace isolated-account live tests. Gates B/C remain unavailable.
