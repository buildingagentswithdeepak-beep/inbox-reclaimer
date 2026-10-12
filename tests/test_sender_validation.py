"""All Google responses and approvals here are synthetic; no real account access."""

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import time
from uuid import uuid4

import pytest

import test_sender_google as google_fixtures
from inbox_reclaimer.models import GateClosed, Identity
from inbox_reclaimer.profile import ProfilePaths
from inbox_reclaimer.sender import validation as v
from inbox_reclaimer.sender.models import Approval
from inbox_reclaimer.sender.validation_scope import DisposableValidation, validation_home


google = google_fixtures.google


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    paths = ProfilePaths(validation_home())
    paths.home.mkdir()
    paths.initialize()
    scope = DisposableValidation("owner@example.test", "x@y.test")
    return paths, scope


def test_real_writer_validation_is_bound_to_home_account_and_ids(google, isolated):
    base, service, *_ = google
    paths, scope = isolated
    identity = Identity(scope.email, "fixture-client")
    scope = replace(scope, account_id=identity.account_id, ids=("a",))
    with pytest.raises(GateClosed):
        v.GoogleSenderWriter(base, validation=scope)
    base.profile_root = paths.home
    writer = v.GoogleSenderWriter(base, validation=scope)
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(GateClosed):
        writer.trash_ids(["outside"])
    assert "batchModify" not in service.executions
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    writer.trash_ids(["a"])
    assert service.executions.count("batchModify") == 1
    service.responses["profile"]["emailAddress"] = "other@example.test"
    with pytest.raises((GateClosed, v.ReclaimError)):
        writer.prepare_write("trash")
    # Production is released separately; it still rejects the switched account.
    unscoped = v.GoogleSenderWriter(base)
    with pytest.raises((GateClosed, v.ReclaimError)):
        unscoped.prepare_write("trash")
    assert service.executions.count("batchModify") == 1


def test_validation_scope_expiry_prevents_transport_call(google, isolated, monkeypatch):
    base, service, *_ = google
    paths, scope = isolated
    base.profile_root = paths.home
    scope = replace(scope, account_id=Identity(scope.email, "fixture-client").account_id, ids=("a",))
    writer = v.GoogleSenderWriter(base, validation=scope)
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    monkeypatch.setattr("inbox_reclaimer.sender.validation_scope.time.time", lambda: scope.created_at + 901)
    with pytest.raises(GateClosed):
        writer.trash_ids(["a"])
    assert "batchModify" not in service.executions


def test_validation_scope_expiry_during_local_guard_prevents_send(google, isolated, monkeypatch):
    base, service, *_ = google
    paths, scope = isolated
    base.profile_root = paths.home
    scope = replace(scope, account_id=Identity(scope.email, "fixture-client").account_id, ids=("a",))
    writer = v.GoogleSenderWriter(base, validation=scope)
    writer.prepare_write("trash")

    def delayed_guard():
        monkeypatch.setattr(
            "inbox_reclaimer.sender.validation_scope.time.time", lambda: scope.created_at + 901
        )

    writer.set_dispatch_guard(delayed_guard)
    with pytest.raises(GateClosed):
        writer.trash_ids(["a"])
    assert "batchModify" not in service.executions


def test_check_is_offline_and_preserves_original_home(isolated, monkeypatch, capsys):
    paths, scope = isolated
    monkeypatch.setenv("HERMES_HOME", "original-profile")
    monkeypatch.setattr(v, "resolve_profile", lambda _: paths)
    monkeypatch.setattr(v.modify_auth, "load_client", lambda _: {"installed": {}})
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("network in check"))
    args = ["check", "--workspace-scripts", "unused", "--account", scope.email, "--sender", scope.sender]
    assert v.main(args) == 0
    assert '"network_used": false' in capsys.readouterr().out
    import os

    assert os.environ["HERMES_HOME"] == "original-profile"


@pytest.mark.parametrize("action", ["sign-in", "authorize-modify", "trash", "restore", "preview"])
def test_noninteractive_actions_stop_before_profile(action, monkeypatch):
    monkeypatch.setattr(v.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(v, "resolve_profile", lambda _: pytest.fail("profile accessed"))
    assert (
        v.main([action, "--workspace-scripts", "unused", "--account", "a@b.test", "--sender", "x@y.test"])
        == 2
    )


def test_wrong_account_rejected_before_message_reads(google, isolated, monkeypatch):
    base, service, *_ = google
    paths, scope = isolated
    monkeypatch.setattr("inbox_reclaimer.gmail.GoogleReadAdapter", lambda *a, **kw: base)
    with pytest.raises(GateClosed):
        with v._session(paths, replace(scope, email="wrong@example.test")):
            pytest.fail("wrong account session admitted")
    assert not any(name in {"list", "get", "thread"} for name, _ in service.calls)


@pytest.fixture
def engine(isolated, monkeypatch):
    from test_sender_execution import Mailbox
    from inbox_reclaimer.storage import JournalStore
    from inbox_reclaimer.sender.journal import SenderJournal
    from inbox_reclaimer.sender.demo import DemoSenderAdapter

    paths, _ = isolated
    adapter = Mailbox()
    scope = DisposableValidation(adapter.identity.email, "news@example.invalid")
    with JournalStore(paths.journal) as store:
        store.bind_account(adapter.identity)
        journal = SenderJournal(store)

        @contextmanager
        def session(*_):
            yield adapter, adapter.identity, store, journal

        monkeypatch.setattr(v, "_session", session)
        # Demo query helper only; actual executor still uses the effect-logging fixture.
        monkeypatch.setattr(v, "GoogleSenderReader", DemoSenderAdapter)
        writers = []

        def writer(base, *, validation):
            validation.check_home(paths.home)
            validation.check_account(base.identity)
            writers.append(validation)
            return base

        monkeypatch.setattr(v, "GoogleSenderWriter", writer)
        yield paths, scope, adapter, journal, writers


def approve(plan, identity, messages, **kwargs):
    assert kwargs == {"validation": True}
    assert tuple(sorted(m.id for m in messages)) == plan.ids
    now = time.time()
    return Approval(
        identity.account_id,
        plan.plan_id,
        plan.digest,
        plan.action,
        "synthetic-test",
        uuid4().hex,
        uuid4().hex,
        now,
        now + 900,
    )


def test_preview_and_cancellation_never_construct_writer(engine, monkeypatch):
    paths, scope, adapter, journal, writers = engine
    preview = v.run_action(paths, scope, "preview")
    assert not preview["approval_created"] and not preview["mail_changed"]
    monkeypatch.setattr(v, "confirm_plan", lambda *a, **kw: None)
    cancelled = v.run_action(paths, scope, "trash")
    assert cancelled["decision"] == "rejected"
    assert not writers and not adapter.calls and not journal.operations(adapter.identity.account_id)


def test_restore_missing_source_reports_actionable_error_without_effects(engine, monkeypatch, capsys):
    paths, scope, adapter, journal, writers = engine
    monkeypatch.setattr(v, "_interactive", lambda: None)
    monkeypatch.setattr(v, "resolve_profile", lambda _: paths)
    monkeypatch.setattr(v, "confirm_plan", lambda *a, **kw: pytest.fail("confirmation must not open"))
    assert (
        v.main(
            [
                "restore",
                "--workspace-scripts",
                "unused",
                "--account",
                scope.email,
                "--sender",
                scope.sender,
                "--source-plan",
                "MISSING-SENSITIVE-REFERENCE",
            ]
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "source trash plan was not found" in error
    assert "same disposable-account profile" in error
    assert "MISSING-SENSITIVE-REFERENCE" not in error
    assert not writers and not adapter.calls
    assert not journal.operations(adapter.identity.account_id)


def test_trash_then_separately_confirmed_restore_real_journal(engine, monkeypatch):
    paths, scope, adapter, journal, writers = engine
    before = {i: m.labels for i, m in adapter.messages.items()}
    monkeypatch.setattr(v, "confirm_plan", approve)
    trashed = v.run_action(paths, scope, "trash", limit=2)
    assert trashed["result"]["counts"]["confirmed"] == 2
    restored = v.run_action(paths, scope, "restore", source_plan=trashed["plan_id"])
    assert restored["result"]["counts"]["confirmed"] == 2
    assert {i: m.labels for i, m in adapter.messages.items()} == before
    assert len(writers) == 2 and writers[0].ids == writers[1].ids
    assert restored["production_released"] == v.release_status()["live_mutation_released"]
    assert restored["execution_scope"] == "disposable_validation"
    assert restored["validation_candidate_cap"] == 5
    assert journal.operations(adapter.identity.account_id)


def test_reconcile_stage_uses_reader_and_keeps_original_unknown(engine, monkeypatch):
    from inbox_reclaimer.sender import reconciliation

    paths, scope, adapter, journal, writers = engine
    original = adapter.messages["a"]
    adapter.timeout = "trash"
    monkeypatch.setattr(v, "confirm_plan", approve)
    outcome = v.run_action(paths, scope, "trash", limit=1)
    assert outcome["result"]["counts"]["unknown"] == 1
    unknown = journal.operations(adapter.identity.account_id)[0]
    adapter.messages["a"] = original
    calls, writer_count = list(adapter.calls), len(writers)
    monkeypatch.setattr(reconciliation, "confirm_plan", approve)
    result = v.run_action(paths, scope, "reconcile")
    assert result["reconciled"] == 1 and not result["mail_changed"]
    assert journal.operations(adapter.identity.account_id)[0] == unknown
    assert adapter.calls == calls and len(writers) == writer_count
    status = v.run_action(paths, scope, "status")
    assert status["outcomes"]["unknown"] == 1
    assert status["externally_reconciled"] == 1 and not status["blocked"]


def test_restore_scope_and_uncertainty_block_further_effects(engine, monkeypatch):
    paths, scope, adapter, journal, writers = engine
    monkeypatch.setattr(v, "confirm_plan", approve)
    trashed = v.run_action(paths, scope, "trash", limit=1)
    with pytest.raises(v.ReclaimError):
        v.run_action(
            paths, replace(scope, sender="other@example.test"), "restore", source_plan=trashed["plan_id"]
        )
    operation = journal.operations(adapter.identity.account_id)[0]
    journal.finish(operation["operation_id"], "unknown", reason="test_uncertainty")
    calls = list(adapter.calls)
    with pytest.raises(v.ReclaimError):
        v.run_action(paths, scope, "trash")
    assert adapter.calls == calls
    assert v.run_action(paths, scope, "status")["blocked"]


def test_failed_after_effect_does_not_claim_no_changes(isolated, monkeypatch, capsys):
    paths, scope = isolated
    monkeypatch.setattr(v, "_interactive", lambda: None)
    monkeypatch.setattr(v, "resolve_profile", lambda _: paths)

    def failure(*a, **kw):
        raise OSError("PRIVATE")

    monkeypatch.setattr(v, "run_action", failure)
    assert (
        v.main(["trash", "--workspace-scripts", "unused", "--account", scope.email, "--sender", scope.sender])
        == 2
    )
    err = capsys.readouterr().err
    assert "outcomes may be uncertain" in err and "PRIVATE" not in err


def test_modify_consent_rejects_normal_home_before_credentials(isolated):
    _, scope = isolated
    with pytest.raises(GateClosed):
        v.modify_auth.authorize_modify(ProfilePaths(Path("other")), validation=scope)


def test_modify_scope_checks_both_old_and_new_accounts(isolated, monkeypatch):
    import test_sender_authorization as fixtures
    from inbox_reclaimer.sender.models import require_live_release

    paths, scope = isolated
    _, consent, verify, confirm, _ = fixtures.setup.__wrapped__(paths.home, monkeypatch)
    monkeypatch.setattr(v.modify_auth, "require_live_release", require_live_release)
    token = paths.home / "google_token.json"
    original = token.read_bytes()
    verify.return_value = Identity("wrong@example.test", fixtures.CLIENT)
    with pytest.raises(v.ReclaimError):
        v.modify_auth.authorize_modify(
            paths, validation=scope, consent=consent, verify=verify, confirm=confirm
        )
    consent.assert_not_called()
    assert token.read_bytes() == original
    verify.side_effect = [fixtures.OWNER, Identity("wrong@example.test", fixtures.CLIENT)]
    with pytest.raises(v.ReclaimError):
        v.modify_auth.authorize_modify(
            paths, validation=scope, consent=consent, verify=verify, confirm=confirm
        )
    confirm.assert_not_called()
    assert token.read_bytes() == original
    verify.side_effect = None
    verify.return_value = fixtures.OWNER
    assert (
        v.modify_auth.authorize_modify(
            paths, validation=scope, consent=consent, verify=verify, confirm=confirm
        )
        == fixtures.OWNER
    )
    assert token.read_bytes() != original


def test_readonly_onboarding_rejects_wrong_account(isolated, monkeypatch):
    paths, scope = isolated
    monkeypatch.setattr(v.readonly_auth, "verify_staged", lambda *a: Identity("other@example.test", "client"))

    def authorization(paths, *, verify, consent):
        return verify(paths.home, "client")

    monkeypatch.setattr(v.readonly_auth, "authorize", authorization)
    with pytest.raises(GateClosed):
        v._sign_in(paths, scope, False)
