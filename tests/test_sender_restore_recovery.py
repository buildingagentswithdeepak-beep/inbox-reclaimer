"""Offline interrupted-restore recovery: acknowledgement, never a retry."""

from dataclasses import asdict, replace
import json
import sqlite3
from uuid import uuid4

import pytest
import test_sender_execution as fixtures
from test_sender_reconciliation import decision

from inbox_reclaimer.models import ReclaimError
from inbox_reclaimer.sender.journal import SenderJournal
from inbox_reclaimer.sender.reconciliation import ReconciliationPlan, reconcile_external
from inbox_reclaimer.storage import JournalStore

env = fixtures.env


def recover(env, **kwargs):
    return reconcile_external(
        env[2],
        env[0],
        env[0].identity,
        "news@example.invalid",
        confirm=kwargs.pop("confirm", decision),
        clock=lambda: env[4][0],
        **kwargs,
    )


def interrupted(env, step):
    adapter, _, journal, executor, _ = env
    original = adapter.messages["a"]
    plan, approval = fixtures.trash_then_restore_plan(env)
    if step == "process":
        operation = journal.begin(plan, approval, "a", "untrash", adapter.messages["a"])
        adapter.untrash_message("a")
        journal.finish(operation, "confirmed", adapter.messages["a"])
    else:
        adapter.timeout = step
        assert executor.restore(plan, approval, dry_run=False)["unknown"] == 1
    adapter.timeout = None
    assert journal.blocked(plan.account_id)
    adapter.messages["a"] = original  # Operator restores every original label externally.
    return journal.operations(plan.account_id)


@pytest.mark.parametrize("step", ["untrash", "repair", "process"])
def test_group_recovery_preserves_history_and_invalidates_source(env, step):
    before = interrupted(env, step)
    calls = list(env[0].calls)
    reviewed = []

    def approve(plan, identity, messages, **kwargs):
        reviewed.append(plan)
        assert plan.ids == ("a",)
        return decision(plan, identity, messages, **kwargs)

    result = recover(env, confirm=approve)
    assert result["reconciled"] == 1 and not result["mail_changed"]
    from inbox_reclaimer.sender.models import release_status

    assert not result["blocked"]
    assert result["production_released"] == release_status()["live_mutation_released"]
    assert env[0].calls == calls
    assert env[2].operations(before[0]["account_id"]) == before
    assert env[2].resolved_operation_ids(before[0]["account_id"]) == {o["operation_id"] for o in before[1:]}
    assert reviewed[0].operation_id == before[0]["operation_id"]
    evidence = json.loads(reviewed[0].evidence_json)
    assert evidence == {"source": before[0], "operations": before[1:]}
    with pytest.raises(ValueError):
        fixtures.plan_for(env, action="restore", source=before[0]["plan_id"])
    assert env[2].recover(before[0]["account_id"]) == 0
    assert env[2].operations(before[0]["account_id"]) == before
    with pytest.raises(ReclaimError):
        recover(env)


@pytest.mark.parametrize("step", ["untrash", "repair", "process"])
def test_cancel_preserves_entire_restore_group(env, step):
    before = interrupted(env, step)
    result = recover(env, confirm=lambda *a, **kw: None)
    assert result["decision"] == "rejected"
    assert env[2].blocked(before[0]["account_id"])
    assert env[2].operations(before[0]["account_id"]) == before
    assert not env[2].resolved_operation_ids(before[0]["account_id"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("labels", frozenset({"UNREAD", "Label_1"})),
        ("thread_id", "different"),
        ("raw_from", "other@example.invalid"),
        ("internal_date", 2),
        ("size_estimate", 999),
    ],
)
def test_restore_requires_original_full_trash_preimage(env, field, value):
    before = interrupted(env, "repair")
    env[0].messages["a"] = replace(env[0].messages["a"], **{field: value})
    with pytest.raises((ReclaimError, ValueError)):
        recover(env, confirm=lambda *a, **kw: pytest.fail("unsafe confirmation"))
    assert env[2].blocked(before[0]["account_id"])


def test_two_groups_require_explicit_selection_and_other_group_stays_blocked(env):
    adapter, _, journal, executor, _ = env
    originals = dict(adapter.messages)
    trash, approval = fixtures.plan_for(env, ids=("a", "b"))
    executor.execute(trash, approval, dry_run=False)
    restore, approval = fixtures.plan_for(env, ids=("a", "b"), action="restore", source=trash.plan_id)
    children = []
    for message_id in ("a", "b"):
        op = journal.begin(restore, approval, message_id, "untrash", adapter.messages[message_id])
        journal.finish(op, "confirmed", originals[message_id])
        children.append(op)
    for op in children:
        journal.finish(op, "unknown", reason="interrupted")
    adapter.messages = originals
    with pytest.raises(ReclaimError):
        recover(env)
    assert recover(env, operation_id=children[0])["blocked"]
    assert journal.resolved_operation_ids(trash.account_id) == {children[0]}
    assert not recover(env, operation_id=children[1])["blocked"]


@pytest.mark.parametrize("change", ["state", "source", "observation", "account", "stale"])
def test_changes_after_confirmation_fail_closed(env, change):
    before = interrupted(env, "process")

    def approve(plan, identity, messages, **kwargs):
        approval = decision(plan, identity, messages, **kwargs)
        if change == "state":
            env[2].finish(before[1]["operation_id"], "unknown", reason="interrupted")
        elif change == "source":
            env[2].finish(before[0]["operation_id"], "unknown", reason="interrupted")
        elif change == "observation":
            env[0].messages["a"] = replace(env[0].messages["a"], labels=frozenset({"TRASH"}))
        elif change == "account":
            env[0].identity = replace(identity, email="other@example.invalid")
        else:
            env[4][0] += 901
        return approval

    with pytest.raises((ValueError, ReclaimError)):
        recover(env, confirm=approve)
    assert env[2].blocked(before[0]["account_id"])
    assert not env[2].resolved_operation_ids(before[0]["account_id"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("issued_at", None),
        ("expires_at", "later"),
        ("issued_at", True),
        ("expires_at", float("nan")),
        ("principal", ""),
        ("digest", "0" * 64),
        ("account_id", "0" * 64),
        ("event_id", None),
        ("action", "restore"),
    ],
)
def test_malformed_approval_is_rejected_without_evidence(env, field, value):
    before = interrupted(env, "repair")

    def approve(plan, identity, messages, **kwargs):
        return replace(decision(plan, identity, messages, **kwargs), **{field: value})

    with pytest.raises(ValueError):
        recover(env, confirm=approve)
    assert not env[2].resolved_operation_ids(before[0]["account_id"])
    assert env[2].blocked(before[0]["account_id"])


def test_audit_failure_rolls_back_entire_group(env, monkeypatch):
    before = interrupted(env, "repair")

    def fail(*args, **kwargs):
        raise RuntimeError("audit failure")

    monkeypatch.setattr(env[1], "_event", fail)
    with pytest.raises(RuntimeError):
        recover(env)
    assert not env[2].resolved_operation_ids(before[0]["account_id"])
    assert env[2].operations(before[0]["account_id"]) == before
    assert env[1].conn.execute("SELECT count(*) FROM sender_recovery_groups").fetchone()[0] == 0
    assert env[1].conn.execute("SELECT count(*) FROM sender_recovery_members").fetchone()[0] == 0


def test_reopen_reconstructs_canonical_group_and_preserves_legacy_resolution(env):
    # First produce an old four-field resolution, then add restore recovery evidence.
    adapter, store, journal, executor, clock = env
    original = adapter.messages["b"]
    plan, approval = fixtures.plan_for(env, ids=("b",))
    adapter.timeout = "trash"
    executor.execute(plan, approval, dry_run=False)
    adapter.timeout = None
    adapter.messages["b"] = original
    recover(env)
    legacy = dict(store.conn.execute("SELECT * FROM sender_resolutions").fetchone())
    before = interrupted(env, "repair")
    reviewed = []

    def delayed(plan, identity, messages, **kwargs):
        reviewed.append(plan)
        clock[0] += 60
        return replace(
            decision(plan, identity, messages, **kwargs), issued_at=clock[0], expires_at=clock[0] + 900
        )

    recover(env, confirm=delayed)
    with JournalStore(store.path) as reopened:
        upgraded = SenderJournal(reopened, clock=lambda: clock[0])
        row = reopened.conn.execute("SELECT * FROM sender_recovery_groups").fetchone()
        persisted = ReconciliationPlan(**json.loads(row["plan_json"]))
        assert asdict(persisted) == asdict(reviewed[0])
        assert persisted.digest == row["plan_digest"]
        assert persisted.created_at < row["observed_at"]
        assert not upgraded.blocked(plan.account_id)
        assert upgraded.recover(plan.account_id) == 0
        assert dict(reopened.conn.execute("SELECT * FROM sender_resolutions").fetchone()) == legacy
        assert upgraded.operations(plan.account_id) == before
        for table in ("sender_recovery_groups", "sender_recovery_members"):
            with pytest.raises(sqlite3.IntegrityError):
                reopened.conn.execute(f"DELETE FROM {table}")
            reopened.conn.rollback()


def test_validation_disclosure_is_forwarded(env):
    interrupted(env, "process")

    def approve(plan, identity, messages, **kwargs):
        assert kwargs == {"validation": False}
        return decision(plan, identity, messages, validation=True)

    assert recover(env, confirm=approve, validation=False)["reconciled"] == 1


def test_fabricated_selection_is_rejected(env):
    interrupted(env, "process")
    with pytest.raises(ReclaimError):
        recover(env, operation_id=uuid4().hex)


@pytest.mark.parametrize("mode", ["stale_read", "guard_delay", "guard_account"])
def test_final_observation_and_identity_are_fresh(env, mode):
    before = interrupted(env, "repair")
    adapter, _, _, _, clock = env
    get = adapter.get_metadata

    def slow(message_id):
        clock[0] += 11
        return get(message_id)

    def guard():
        if mode == "guard_delay":
            clock[0] += 11
        elif mode == "guard_account":
            adapter.identity = replace(adapter.identity, email="other@example.invalid")

    if mode == "stale_read":
        adapter.get_metadata = slow
    with pytest.raises((ValueError, ReclaimError)):
        recover(env, guard=guard)
    assert env[2].blocked(before[0]["account_id"])
    assert not env[2].resolved_operation_ids(before[0]["account_id"])


@pytest.mark.parametrize("change", ["members", "source", "state"])
def test_forged_canonical_group_cannot_be_persisted(env, change):
    from inbox_reclaimer.sender.journal import _json

    before = interrupted(env, "repair")
    target = env[2].external_recovery_target(before[0]["account_id"], "news@example.invalid")
    evidence = json.loads(target["evidence_json"])
    root = before[0]["operation_id"]
    if change == "members":
        evidence["operations"] = evidence["operations"][1:]
    elif change == "source":
        root = uuid4().hex
        evidence["source"]["operation_id"] = root
        for op in evidence["operations"]:
            op["source_operation_id"] = root
    else:
        evidence["operations"][0]["state"] = "unknown"
    plan = ReconciliationPlan(
        before[0]["account_id"], root, _json(before[0]["preimage"]), env[4][0], _json(evidence)
    )
    approval = decision(plan, env[0].identity, (), validation=True)
    with pytest.raises((ValueError, ReclaimError)):
        env[2].record_external_recovery(plan, approval, env[0].messages["a"], env[4][0])
    assert not env[2].resolved_operation_ids(before[0]["account_id"])


def test_stale_source_with_later_trash_cycle_cannot_be_reconciled(env):
    adapter, _, journal, executor, _ = env
    original = adapter.messages["a"]
    trash, approval = fixtures.plan_for(env)
    executor.execute(trash, approval, dry_run=False)
    restore, approval = fixtures.plan_for(env, action="restore", source=trash.plan_id)
    operation = journal.begin(restore, approval, "a", "untrash", adapter.messages["a"])
    journal.finish(operation, "confirmed", original)
    adapter.messages["a"] = original
    later, approval = fixtures.plan_for(env)
    executor.execute(later, approval, dry_run=False)
    journal.finish(operation, "unknown", reason="late_conflict")
    adapter.messages["a"] = original
    with pytest.raises((ValueError, ReclaimError), match="superseded"):
        recover(env, operation_id=operation)
    assert journal.blocked(trash.account_id)


def test_process_recovery_then_external_recovery_never_retries(env):
    before = interrupted(env, "process")
    assert env[2].recover(before[0]["account_id"]) == 1
    classified = env[2].operations(before[0]["account_id"])
    calls = list(env[0].calls)
    assert not recover(env)["blocked"]
    assert env[2].operations(before[0]["account_id"]) == classified
    assert env[0].calls == calls


def test_group_member_insert_failure_rolls_back_source_invalidation(env):
    before = interrupted(env, "repair")
    env[1].conn.execute("""CREATE TRIGGER synthetic_member_failure BEFORE INSERT ON sender_recovery_members
        WHEN json_extract(NEW.evidence_json,'$.step')='repair'
        BEGIN SELECT RAISE(ABORT,'synthetic commit boundary fault'); END""")
    env[1].conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        recover(env)
    assert env[1].conn.execute("SELECT count(*) FROM sender_recovery_groups").fetchone()[0] == 0
    assert env[1].conn.execute("SELECT count(*) FROM sender_recovery_members").fetchone()[0] == 0
    assert env[2].blocked(before[0]["account_id"])


def test_group_recovery_does_not_create_standing_approval(env):
    before = interrupted(env, "repair")
    recover(env)
    fresh, approval = fixtures.plan_for(env)
    calls = list(env[0].calls)
    assert env[3].execute(fresh, approval, dry_run=False)["confirmed"] == 1
    assert env[0].calls == calls + [("trash", "a")]
    # New trash has new provenance; the externally recovered cycle stays invalid.
    with pytest.raises(ValueError):
        fixtures.plan_for(env, action="restore", source=before[0]["plan_id"])
    restore, approval = fixtures.plan_for(env, action="restore", source=fresh.plan_id)
    assert env[3].restore(restore, approval, dry_run=False)["confirmed"] == 1


def test_recovery_approval_cannot_be_reused_for_sender_approval(env):
    interrupted(env, "repair")
    approved = []

    def approve(plan, identity, messages, **kwargs):
        value = decision(plan, identity, messages, **kwargs)
        approved.append(value)
        return value

    recover(env, confirm=approve)
    plan, _ = fixtures.plan_for(env, ids=("b",))
    reused = replace(approved[0], plan_id=plan.plan_id, action=plan.action, digest=plan.digest)
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        env[2].approve(plan, reused)


def test_partial_group_rows_never_unblock_account(env):
    from inbox_reclaimer.sender.journal import _json

    before = interrupted(env, "process")
    journal, conn = env[2], env[1].conn
    target = journal.external_recovery_target(before[0]["account_id"], "news@example.invalid")
    plan = ReconciliationPlan(
        before[0]["account_id"],
        before[0]["operation_id"],
        _json(before[0]["preimage"]),
        env[4][0],
        target["evidence_json"],
    )
    approval = decision(plan, env[0].identity, (), validation=True)
    # A malformed/incomplete batch must not resolve even one of its members.
    evidence = json.loads(plan.evidence_json)
    evidence["operations"].append({**before[1], "operation_id": uuid4().hex})
    plan = replace(plan, evidence_json=_json(evidence))
    approval = replace(approval, digest=plan.digest)
    conn.execute(
        "INSERT INTO sender_recovery_groups VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            plan.operation_id,
            plan.account_id,
            "externally_restored",
            _json(asdict(plan)),
            plan.digest,
            plan.observation_json,
            _json(asdict(approval)),
            approval.event_id,
            approval.challenge_id,
            env[4][0],
            env[4][0],
        ),
    )
    conn.execute(
        "INSERT INTO sender_recovery_members VALUES (?,?,?)",
        (
            before[1]["operation_id"],
            plan.operation_id,
            _json(before[1]),
        ),
    )
    conn.commit()
    assert journal.blocked(plan.account_id)
    assert not journal.resolved_operation_ids(plan.account_id)


def test_resolved_partial_repair_is_not_hidden_if_outcome_changes(env):
    before = interrupted(env, "repair")
    recover(env)
    # A later evidence downgrade must not be masked by the old resolution.
    untrash = next(o for o in before if o["step"] == "untrash")
    env[2].finish(untrash["operation_id"], "unknown", reason="late_conflict")
    assert env[2].blocked(before[0]["account_id"])
    assert untrash["operation_id"] not in env[2].resolved_operation_ids(before[0]["account_id"])
