"""Synthetic external recovery only; never reads or changes a real mailbox."""

from dataclasses import replace
import sqlite3
from uuid import uuid4

import pytest
import test_sender_execution as fixtures

from inbox_reclaimer.models import ReclaimError
from inbox_reclaimer.sender.models import Approval
from inbox_reclaimer.sender.reconciliation import reconcile_external

env = fixtures.env


@pytest.fixture
def recovered(env):
    adapter, store, journal, executor, clock = env
    original = adapter.messages["a"]
    plan, approval = fixtures.plan_for(env)
    adapter.timeout = "trash"
    assert executor.execute(plan, approval, dry_run=False)["unknown"] == 1
    operation = journal.operations(plan.account_id)[0]
    adapter.messages["a"] = original  # Simulated manual recovery in Gmail.
    adapter.timeout = None
    return env, operation


def decision(plan, identity, messages, **kwargs):
    assert kwargs == {"validation": True}
    assert plan.action == "reconcile_external"
    return Approval(
        plan.account_id,
        plan.plan_id,
        plan.digest,
        plan.action,
        "synthetic-human",
        uuid4().hex,
        uuid4().hex,
        plan.created_at,
        plan.created_at + 900,
    )


def reconcile(env, confirm=decision):
    adapter, _, journal, _, clock = env
    return reconcile_external(
        journal, adapter, adapter.identity, "news@example.invalid", confirm=confirm, clock=lambda: clock[0]
    )


def test_manual_recovery_appends_evidence_without_rewriting_unknown_or_replaying(recovered):
    env, original = recovered
    adapter, store, journal, executor, _ = env
    calls = list(adapter.calls)
    result = reconcile(env)
    assert result["reconciled"] == 1 and result["mail_changed"] is False
    assert not journal.blocked(adapter.identity.account_id)
    assert journal.operations(adapter.identity.account_id)[0] == original
    assert adapter.calls == calls
    assert store.conn.execute("SELECT count(*) FROM sender_resolutions").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("DELETE FROM sender_resolutions")
    store.conn.rollback()
    # Reconciliation neither makes old trash confirmed nor grants restore provenance.
    with pytest.raises(ValueError):
        fixtures.plan_for(env, action="restore", source=original["plan_id"])
    # A fresh, separately approved plan can run; old scopes are never replayed.
    fresh, approval = fixtures.plan_for(env)
    assert executor.execute(fresh, approval, dry_run=False)["confirmed"] == 1
    assert len(adapter.calls) == len(calls) + 1


def test_approved_plan_digest_is_reconstructible_after_delayed_review_and_reopen(recovered):
    from dataclasses import asdict
    import json
    from inbox_reclaimer.sender.reconciliation import ReconciliationPlan
    from inbox_reclaimer.storage import JournalStore

    env, original = recovered
    reviewed = []

    def delayed(plan, identity, messages, **kwargs):
        reviewed.append(plan)
        env[4][0] += 60  # Human review separates original plan time from the fresh read.
        return replace(
            decision(plan, identity, messages, **kwargs), issued_at=env[4][0], expires_at=env[4][0] + 900
        )

    reconcile(env, delayed)
    with JournalStore(env[1].path) as store:
        row = store.conn.execute(
            "SELECT * FROM sender_resolutions WHERE operation_id=?", (original["operation_id"],)
        ).fetchone()
        evidence = json.loads(row["approval_json"])
        persisted = ReconciliationPlan(**evidence["reconciliation_plan"])
        assert asdict(persisted) == asdict(reviewed[0])
        assert persisted.created_at < row["observed_at"]
        assert persisted.created_at < evidence["issued_at"]
        assert persisted.digest == row["plan_digest"] == evidence["digest"]
        assert persisted.account_id == row["account_id"]
        assert persisted.operation_id == row["operation_id"]
        assert persisted.observation_json == row["observation_json"]
        assert replace(persisted, created_at=row["observed_at"]).digest != row["plan_digest"]
        assert "PRIVATE SUBJECT" not in row["approval_json"]
    assert env[2].operations(original["account_id"])[0] == original


def test_cancel_preserves_account_block(recovered):
    env, _ = recovered
    result = reconcile(env, lambda *a, **kw: None)
    assert result["decision"] == "rejected"
    assert env[2].blocked(env[0].identity.account_id)
    assert env[1].conn.execute("SELECT count(*) FROM sender_resolutions").fetchone()[0] == 0


@pytest.mark.parametrize(
    "labels", [frozenset({"TRASH"}), frozenset({"INBOX"}), frozenset({"INBOX", "STARRED"})]
)
def test_conflicting_or_incomplete_manual_restore_never_opens_confirmation(recovered, labels):
    env, _ = recovered
    env[0].messages["a"] = replace(env[0].messages["a"], labels=labels)
    with pytest.raises(ReclaimError):
        reconcile(env, lambda *a, **kw: pytest.fail("conflicting preview"))
    assert env[2].blocked(env[0].identity.account_id)


def test_change_after_confirmation_fails_closed(recovered):
    env, _ = recovered

    def changed(plan, identity, messages, **kwargs):
        approval = decision(plan, identity, messages, **kwargs)
        env[0].messages["a"] = replace(env[0].messages["a"], labels=frozenset({"TRASH"}))
        return approval

    with pytest.raises(ReclaimError):
        reconcile(env, changed)
    assert env[2].blocked(env[0].identity.account_id)


def test_expired_or_wrong_action_approval_does_not_resolve(recovered):
    env, _ = recovered

    def wrong(plan, identity, messages, **kwargs):
        return replace(decision(plan, identity, messages, **kwargs), action="trash")

    with pytest.raises(ValueError):
        reconcile(env, wrong)
    assert env[2].blocked(env[0].identity.account_id)


def test_resolution_survives_reopen_and_cannot_repeat(recovered):
    from inbox_reclaimer.sender.journal import SenderJournal
    from inbox_reclaimer.storage import JournalStore

    env, original = recovered
    reconcile(env)
    with JournalStore(env[1].path) as store:
        journal = SenderJournal(store)
        assert not journal.blocked(original["account_id"])
        assert journal.operations(original["account_id"])[0] == original
    with pytest.raises(ReclaimError):
        reconcile(env)


@pytest.mark.parametrize("change", ["expired", "account", "digest", "principal", "event"])
def test_invalid_approval_preserves_unknown(recovered, change):
    env, original = recovered

    def invalid(plan, identity, messages, **kwargs):
        approval = decision(plan, identity, messages, **kwargs)
        if change == "expired":
            return replace(approval, expires_at=plan.created_at)
        if change == "account":
            return replace(approval, account_id="0" * 64)
        if change == "digest":
            return replace(approval, digest="0" * 64)
        if change == "principal":
            return replace(approval, principal="")
        old = env[1].conn.execute("SELECT event_id FROM sender_approvals").fetchone()[0]
        return replace(approval, event_id=old)

    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        reconcile(env, invalid)
    assert env[2].blocked(original["account_id"])
    assert env[2].operations(original["account_id"])[0] == original


def test_stale_final_observation_cannot_be_recorded(recovered):
    env, original = recovered

    def delay():
        env[4][0] += 11

    with pytest.raises(ValueError):
        reconcile_external(
            env[2],
            env[0],
            env[0].identity,
            "news@example.invalid",
            confirm=decision,
            clock=lambda: env[4][0],
            guard=delay,
        )
    assert env[2].blocked(original["account_id"])


def test_new_unknown_operation_still_blocks_after_resolution(recovered):
    env, _ = recovered
    reconcile(env)
    env[0].timeout = "trash"
    plan, approval = fixtures.plan_for(env, ids=("b",))
    assert env[3].execute(plan, approval, dry_run=False)["unknown"] == 1
    assert env[2].blocked(plan.account_id)


def test_sql_null_expiry_cannot_bypass_resolution_approval(recovered):
    from dataclasses import asdict
    from inbox_reclaimer.sender.reconciliation import ReconciliationPlan
    from inbox_reclaimer.sender.journal import _json

    env, original = recovered
    clock = env[4][0]
    plan = ReconciliationPlan(
        original["account_id"], original["operation_id"], _json(original["preimage"]), clock
    )
    approval = asdict(decision(plan, env[0].identity, (), validation=True))
    approval.pop("expires_at")
    with pytest.raises(sqlite3.IntegrityError):
        env[1].conn.execute(
            "INSERT INTO sender_resolutions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                plan.operation_id,
                plan.account_id,
                "externally_restored",
                plan.digest,
                plan.observation_json,
                _json(approval),
                approval["event_id"],
                approval["challenge_id"],
                clock,
                clock,
            ),
        )
    env[1].conn.rollback()
    assert env[2].blocked(plan.account_id)


def test_schema_upgrade_preserves_existing_unknown(recovered):
    from inbox_reclaimer.sender.journal import SenderJournal

    env, original = recovered
    # Represent a pre-reconciliation database: existing evidence, no resolution table.
    env[1].conn.execute("DROP TABLE sender_resolutions")
    env[1].conn.commit()
    upgraded = SenderJournal(env[1], clock=lambda: env[4][0])
    assert upgraded.operations(original["account_id"])[0] == original
    assert upgraded.blocked(original["account_id"])
    assert not upgraded.resolved_operation_ids(original["account_id"])
    reconcile(env)
    assert not upgraded.blocked(original["account_id"])


def test_audit_failure_rolls_back_resolution(recovered, monkeypatch):
    env, original = recovered

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(env[1], "_event", fail)
    with pytest.raises(RuntimeError):
        reconcile(env)
    assert env[2].blocked(original["account_id"])
    assert not env[2].resolved_operation_ids(original["account_id"])
    assert env[2].operations(original["account_id"])[0] == original


def test_account_change_after_confirmation_cannot_resolve(recovered):
    env, original = recovered

    def switched(plan, identity, messages, **kwargs):
        approval = decision(plan, identity, messages, **kwargs)
        env[0].identity = replace(identity, email="other@example.invalid")
        return approval

    with pytest.raises(ReclaimError):
        reconcile(env, switched)
    assert env[2].blocked(original["account_id"])


def test_wrong_sender_is_not_a_resolution_target(recovered):
    env, _ = recovered
    with pytest.raises(ReclaimError):
        reconcile_external(env[2], env[0], env[0].identity, "other@example.invalid", confirm=decision)
    assert env[2].blocked(env[0].identity.account_id)
