# Inbox Reclaimer — validation and spec traceability

## Release scope and compliance summary

**Bounded-preview update:** `analyze --max-messages N` now provides an explicitly partial, non-published listing-order preview. **208 tests passed**, including 33 new preview cases; lint, real offline CLI, browser rendering, and separately installed wheel checks passed. See [LIMITED_SCAN.md](LIMITED_SCAN.md) and its linked evidence. Exact global newest-N ordering and live Gmail execution are not certified.

**Authorization update:** first-time read-only sign-in is now available through `reclaim-auth`; see [AUTHORIZATION.md](AUTHORIZATION.md) for the newer **173-test** run and safeguards. Only the supplied client configuration was checked locally without displaying credential values; Google consent and live Gmail remain operator-run and unverified. The evidence below records the original Gate A baseline.

**Implemented: Gate A read-only inventory, local reports and immutable proposals.** The application is runnable and verified with synthetic mailboxes, mock Google transports, actual SQLite files, Windows ACLs/locks, separate Python processes and a separately installed wheel.

**Not a claim of complete implementation of the whole specification or live production certification.** Gates B/C have no Gmail mutation implementation, no trusted approval minting and no enabled bypass. Live Gmail, OAuth consent and account-specific effective quotas were not exercised. Additional interpretations/limitations are explicit below.

Source: [verbatim specification snapshot](SPEC.md), originally `C:\Users\v-deegarg\specs\inbox-reclaimer-tech-spec.md`.
Source SHA-256: `93e7a050ae198974343c821452732f92e14801b2e922b1966c6b7b27ac036d59`.

## Actual execution evidence

Reference environment: Windows reported `Windows-10-10.0.26200-SP0`; Intel64 Family 6 Model 170 Stepping 4; Python 3.11.9. Dependency versions and distribution checksums are in [package.json](evidence/package.json).

| Check | Actual result / evidence |
|---|---|
| `pytest -q --tb=short --junitxml=docs/evidence/junit.xml` | **159 passed in 42.44s**, no warnings; [JUnit output](evidence/junit.xml) |
| `.venv/Scripts/ruff check src tests scripts` | **All checks passed** |
| `run-demo.cmd` | Actual local inventory/report/proposal run; **37 synthetic messages**, **20 uniquely proposed IDs**, **410,000,000 estimated message bytes**; no Gmail access; [demo.json](evidence/demo.json), [transcript](evidence/demo.txt) |
| Installed-helper A → B → A | Separate CLI processes with two temporary `HERMES_HOME` values, distinct generations, A unchanged when reopened, no credentials created; [profile-isolation.json](evidence/profile-isolation.json) |
| Durable LangGraph probe | Tests start a process, persist an interrupt, terminate it, then reopen/resume from another process. Approval/rejection/list/invalid/expired-shaped decisions are exercised **as runtime fixtures, not application authorization**. A separate fake-effect log proves completion does not run twice. |
| OS lock | A second process cannot acquire the held account lock; termination releases it. |
| Windows DACL | Generated state/report ACLs inspected through Windows security APIs; grants restricted to current principal and SYSTEM. |
| Browser | Actual local HTML opened and visually inspected. Styled dashboard and readable tables; no document overflow. DOM check: **0 scripts**, **0 remote assets**; restrictive hash-bound style CSP and `connect-src 'none'`. |
| Distribution | Wheel and source archive built. Wheel installed into a separate uv-managed environment, outside the source checkout; actual sync/SQLite schema/packaged CSS/report smoke passed with **37 synthetic messages**. Archives checked to exclude profile state, databases and credential files. |
| Public quota reference | Live article inspected; read-method costs agree with the configuration defaults. This does not establish the user's effective project quota; [reference checks](REFERENCE_CHECKS.md). |

### 100,000-message benchmark

Command: `.venv/Scripts/python scripts/benchmark.py --output docs/evidence/benchmark.json`.

Fixture: synthetic, 1,000 sender addresses, unique messages/threads, no API calls. Actual results:

| Measurement | Seconds |
|---|---:|
| SQLite inventory hydration | 2.278542 |
| In-memory cached summary aggregation p95 | **1.017467** |
| Hydration plus summary p95 component sum | **3.296009** |
| Indexed paginated batch view p95 | **0.000271** |

The cached-aggregation and indexed-view targets pass. **Cold database hydration plus summary does not meet two seconds**; cold CLI startup/authentication are not included. This distinction is exposed in the benchmark rather than hidden behind a warm-cache claim. The unit suite also exercises 100,000 unique simple display-name headers. These are local synthetic measurements, not a live Gmail completion-time SLA.

## Requirement → implementation → tests

| Spec | Implemented solution | Primary evidence |
|---|---|---|
| §§2–3, Gate A | Local modular read/proposal application; no Gmail mutation adapter or mutation graph edges | `cli.py`, `workflow.py`; `test_cli.py`, `test_architecture.py` |
| §4.1, §§9/11 | Installed home-helper adapter; single token-file source; exact account/client binding; actual grant metadata; refresh revalidation even when token text is unchanged | `profile.py`, `gmail.py`; `test_profile.py`, `test_gmail.py`, actual helper-isolation script |
| §4.2, §13 | H0 before enumeration; paginated history; arrivals/deletions/label changes; current refresh; conservative SENT-thread invalidation; atomic generation/cursor | `sync.py`, `storage.py`; `test_sync.py`, `test_storage.py` |
| §§4.2/10 | Durable full-scan H0/pages/metadata; cancellation and failed publication preserve the committed generation; history/safety reads bypass staged metadata | `staging.py`; `test_staging.py` |
| §4.3, Gate A | Sender parsing, unknown metadata, decimal thresholds, calendar clamping, unique unions, overlapping cohorts and additive bands | `analytics.py`; `test_analytics.py` |
| §4.4 | Protected labels/senders and fresh SENT-thread heuristic; deterministic one-owner priority; bounded chunks; union counts/bytes; immutable sealed revisions; rejection never reassigns | `proposals.py`, `storage.py`, `schema.sql`; `test_proposals.py`, `test_storage.py`, CLI round trip |
| §§4.2–4.4, Gate A attachment cases | Opt-in bounded MIME-name/size pass; local decoded-stream SHA-256 utility; possible/equal-content findings remain advisory and cannot create deletion batches | `attachments.py`, `mime.py`; `test_attachments.py`, `test_mime.py` |
| §§5.1–5.3 | Pinned StateGraph; saver lifetime encloses compile/invoke; reference-only checkpoints; traces disabled; no LLM transport | `workflow.py`, runtime probe; `test_workflow.py`, `test_architecture.py` |
| §7 | Account-keyed cache/journal schema, foreign keys, WAL/FULL, membership digests, database-level sealing and closed approval/operation insertion | `models.py`, `storage.py`, `schema.sql`; storage/proposal tests |
| §8 | Read, propose, local paginated list, reject, add protection, status, audit, metadata rebuild commands; later actions fail before token access | `cli.py`; `test_cli.py`, `test_safety_regressions.py` |
| §9 | Profile-local stores, process-held locks, consistent journal backup, export protection for all application stores/credentials | `profile.py`, `storage.py`; architecture/storage/safety tests |
| §§10/15 | Versioned costs and lower effective limits; smooth/rolling pacing; retry/backoff; durable selected daily budget; progress and remaining-metadata-cost estimate on interactive terminals | `quota.py`, `budget.py`, `gmail.py`, CLI; quota/budget/Gmail tests and benchmark |
| §11.2 | Subject redaction before newly persisted metadata/staging; minimized Hermes output; escaped CSP HTML; terminal-control removal; CSV formula-neutralization utility; no remote report assets | `sync.py`, `staging.py`, `render.py`, `profile.py`, CLI; privacy/render/attachment/CLI tests and browser |
| §11.2 retention | Expiry of recognized app-named reports/logs and completed read-only checkpoints; no automatic journal deletion | `retention.py`; `test_retention.py` |
| §12 | Journal status, rejection/protection counts, opaque plan/workflow references, proposal skips, conservative reserved-quota counters; idempotent audit export | CLI/storage/budget tests and demo |
| §13 | Fail-closed grant/account checks; bounded read retries; expired-history rescan; ambiguous thread skip; transactional rollback; crash-safe stage/cursor behavior | Gmail/sync/staging/storage/budget tests |
| §14 Gates B/C | **Disabled, not implemented or claimed passed.** Schema placeholders are closed by triggers, not working execution capabilities. | Architecture/CLI tests; explicit errors for execute/restore/purge/approval/protection removal |

## Assumptions and interpretations

The full design and reasons are in [DESIGN.md](DESIGN.md). Additional operational interpretations:

- A first-ever identity read cannot yet have a verified account key. Its **quota reservation only** uses a provisional profile bucket, later adopted by the bound account. No mail metadata is stored under this provisional key.
- Reservation-before-dispatch may conservatively overcount failed/undelivered calls. It is a local budget, not Google's billing meter.
- Retention recognizes `report-*.html`/`report-*.json` and `reclaim-*.jsonl` in app-owned directories. It does not delete arbitrary user-named or external exports. Those need explicit cleanup; a future ownership manifest could extend automatic expiry safely.
- The independent attachment hash utility consumes already-decoded bounded streams. Live attachment-content downloads/hash orchestration are not exposed by the CLI; live MIME metadata inspection is implemented but only mock-tested.

## Remaining gaps and risks

1. **No live Gmail integration test.** Real token grants, refresh, metadata/MIME responses, administrator restrictions and effective quotas require an operator-run read-only staging check. No user credentials were read or changed during development.
2. **Gate B/C features intentionally absent:** trusted human approvals, action-specific consent escalation/adoption, write-ahead mutation execution, uncertain-write reconciliation, restore label repair, purge provenance and destructive live smoke tests. CLI flags cannot enable them.
3. **Cold-path performance:** measured hydration + summary is about 3.30 seconds for the reference fixture. The two-second result applies to cached aggregation, not the complete cold CLI path.
4. **Concurrency/freshness policy:** implementation uses one serial reader and always-fresh thread safety observations; arbitrary concurrency and safety-freshness tuning are not exposed. Minute pacing is process-local; other apps/profiles sharing a Cloud project are not globally metered by this app.
5. **Retention limits:** custom-named/external exports are manual cleanup; no operational request-log emitter/rotation pipeline is introduced beyond journal/status and conservative expiry of recognized log files.
6. **Local metadata remains sensitive.** SQLite is not encrypted. Disk encryption, protected backups and avoiding raw commands inside hosted conversations remain operator responsibilities.
7. **External Gmail changes are not locked.** This does not matter for irreversible effects in Gate A because it has none. Future write gates must separately address the specified TOCTOU and unknown-outcome rules.

Final assessment: a working, tested **Gate A implementation with the explicit limitations above**, not an implementation of every future-gated feature and not a claim that synthetic tests certify live destructive behavior.
