"""Approval invalidation tests; temporary journals and synthetic effects only."""

from dataclasses import replace
import sqlite3

import pytest
import test_sender_execution as fixtures

from inbox_reclaimer.sender.journal import SenderJournal
from inbox_reclaimer.storage import JournalStore

env = fixtures.env


def test_revocation_is_durable_idempotent_and_prevents_effects(env):
    adapter, store, journal, executor, clock = env
    plan, approval_id = fixtures.plan_for(env)
    original = dict(store.conn.execute("SELECT * FROM sender_approvals").fetchone())
    assert journal.revoke_approval(plan.account_id, approval_id, "local-human") is True
    assert journal.revoke_approval(plan.account_id, approval_id, "local-human") is False
    with pytest.raises(ValueError, match="revoked"):
        executor.execute(plan, approval_id, dry_run=False)
    assert not adapter.calls
    assert dict(store.conn.execute("SELECT * FROM sender_approvals").fetchone()) == original
    with JournalStore(store.path) as reopened:
        other = SenderJournal(reopened, clock=lambda: clock[0])
        with pytest.raises(ValueError, match="revoked"):
            other.validate_approval(plan, approval_id, clock[0])
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("DELETE FROM sender_approval_invalidations")
    store.conn.rollback()


def test_expiry_is_recorded_once_and_never_extends_approval(env):
    _, store, journal, _, clock = env
    plan, approval_id = fixtures.plan_for(env)
    approval = journal.validate_approval(plan, approval_id, clock[0])
    clock[0] = approval.expires_at
    for _ in range(2):
        with pytest.raises(ValueError, match="expired"):
            journal.validate_approval(plan, approval_id, clock[0])
    rows = store.conn.execute("SELECT * FROM sender_approval_invalidations").fetchall()
    assert len(rows) == 1 and rows[0]["state"] == "expired"
    assert journal.approval_status(plan.account_id)[0]["state"] == "expired"


def test_revocation_before_final_guard_prevents_send(env):
    adapter, store, journal, executor, clock = env
    plan, approval_id = fixtures.plan_for(env)
    guards = []
    adapter.set_dispatch_guard = guards.append
    original_trash = adapter.trash_ids

    def trash(ids):
        with JournalStore(store.path) as other_store:
            other = SenderJournal(other_store, clock=lambda: clock[0])
            other.revoke_approval(plan.account_id, approval_id, "other-local-session")
        guards.pop()()
        return original_trash(ids)

    adapter.trash_ids = trash
    result = executor.execute(plan, approval_id, dry_run=False)
    assert result["unknown"] == 1  # Intent exists, no retrospective certainty inferred.
    assert not adapter.calls and not guards


def test_revoke_wrong_account_or_reference_preserves_valid_approval(env):
    _, _, journal, _, clock = env
    plan, approval_id = fixtures.plan_for(env)
    from inbox_reclaimer.models import IdentityMismatch

    with pytest.raises(IdentityMismatch):
        journal.revoke_approval("0" * 64, approval_id, "local-human")
    with pytest.raises(KeyError):
        journal.revoke_approval(plan.account_id, "missing", "local-human")
    with pytest.raises(ValueError):
        journal.revoke_approval(plan.account_id, approval_id, "")
    assert journal.validate_approval(plan, approval_id, clock[0])


def test_revoking_one_approval_does_not_revoke_another(env):
    _, _, journal, _, clock = env
    plan, first = fixtures.plan_for(env)
    approval = journal.validate_approval(plan, first, clock[0])
    second = journal.approve(plan, replace(approval, event_id="new-event", challenge_id="new-challenge"))
    journal.revoke_approval(plan.account_id, first, "local-human")
    assert journal.validate_approval(plan, second, clock[0])


def test_invalidation_and_audit_commit_together(env, monkeypatch):
    _, store, journal, _, clock = env
    plan, approval_id = fixtures.plan_for(env)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(store, "_event", fail)
    with pytest.raises(RuntimeError):
        journal.revoke_approval(plan.account_id, approval_id, "local-human")
    assert not store.conn.execute("SELECT * FROM sender_approval_invalidations").fetchall()
    assert journal.validate_approval(plan, approval_id, clock[0])
