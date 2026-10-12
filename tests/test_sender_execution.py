"""Offline mutation fault tests: no credentials, Gmail service, or network."""

from dataclasses import replace
import sqlite3
import time
from uuid import uuid4

import pytest

from inbox_reclaimer.gmail import FakeGmailAdapter
from inbox_reclaimer.models import GateClosed, Identity, IdentityMismatch, Message
from inbox_reclaimer.sender.models import Approval, SenderPlan
from inbox_reclaimer.storage import JournalStore


class Mailbox(FakeGmailAdapter):
    def __init__(self):
        super().__init__(
            [
                Message(
                    i,
                    "t-" + i,
                    1,
                    100,
                    frozenset({"INBOX", "UNREAD", "Label_1"}),
                    "News <news@example.invalid>",
                    subject="PRIVATE SUBJECT",
                )
                for i in ("a", "b")
            ]
        )
        self.calls = []
        self.capabilities = []
        self.timeout = None
        self.after_write = None
        self.prepare = None

    def validate_capability(self, action):
        self.capabilities.append(action)
        if action not in {"trash", "restore"}:
            raise GateClosed("Unsupported capability")

    def prepare_write(self, action):
        if self.prepare:
            self.prepare(action)

    def _effect(self, step, i, labels):
        self.calls.append((step, i))
        self.messages[i] = replace(self.messages[i], labels=frozenset(labels))
        if self.after_write:
            self.after_write(step, i)
        if self.timeout == step:
            raise TimeoutError("PRIVATE remote content must not be journaled")
        return {}

    def trash_ids(self, ids):
        assert len(ids) == 1
        i = ids[0]
        return self._effect("trash", i, (self.messages[i].labels - {"INBOX"}) | {"TRASH"})

    def untrash_message(self, i):
        return self._effect("untrash", i, self.messages[i].labels - {"TRASH"})

    def modify_message(self, i, add_labels, remove_labels):
        assert set(remove_labels) <= self.messages[i].labels
        return self._effect("repair", i, (self.messages[i].labels | set(add_labels)) - set(remove_labels))


@pytest.fixture
def env(tmp_path):
    # Imports deliberately inside fixture: missing implementation is a test failure, not collection failure.
    from inbox_reclaimer.sender.journal import SenderJournal
    from inbox_reclaimer.sender.executor import SenderExecutor

    adapter = Mailbox()
    clock = [time.time()]
    store = JournalStore(tmp_path / "journal.db")
    store.bind_account(adapter.identity)
    journal = SenderJournal(store, clock=lambda: clock[0])
    executor = SenderExecutor(adapter, journal, clock=lambda: clock[0])
    yield adapter, store, journal, executor, clock
    store.close()


def plan_for(env, ids=("a",), action="trash", source=None):
    a, _, journal, _, clock = env
    plan = SenderPlan(
        a.identity.account_id, uuid4().hex, "news@example.invalid", ids, action, source, created_at=clock[0]
    )
    journal.save_plan(plan)
    approval = Approval(
        plan.account_id,
        plan.plan_id,
        plan.digest,
        plan.action,
        "human:test",
        uuid4().hex,
        uuid4().hex,
        clock[0],
        clock[0] + 300,
    )
    return plan, journal.approve(plan, approval)


def trash_then_restore_plan(env):
    plan, approval = plan_for(env)
    result = env[3].execute(plan, approval, dry_run=False)
    assert result["confirmed"] == 1
    return plan_for(env, action="restore", source=plan.plan_id)


def test_dryrun_is_read_only(env):
    a, store, journal, executor, _ = env
    plan, approval = plan_for(env)
    assert executor.execute(plan, approval)["would_change"] == 1
    assert not a.calls and not journal.operations(plan.account_id)
    assert store.status(plan.account_id)["operations"] == 0


def test_trash_restore_label_roundtrip_and_source_binding(env):
    a, store, journal, executor, _ = env
    before = a.messages["a"].labels
    plan, approval = trash_then_restore_plan(env)
    assert executor.restore(plan, approval, dry_run=False)["confirmed"] == 1
    assert a.messages["a"].labels == before
    assert a.calls == [("trash", "a"), ("untrash", "a"), ("repair", "a")]
    ops = journal.operations(plan.account_id)
    assert [o["step"] for o in ops] == ["trash", "untrash", "repair"]
    assert all(o["state"] == "confirmed" for o in ops)
    assert ops[1]["source_operation_id"] == ops[0]["operation_id"]
    assert ops[2]["source_operation_id"] == ops[0]["operation_id"]
    assert {"trash", "restore"} <= set(a.capabilities)
    assert "PRIVATE" not in "\n".join(store.conn.iterdump())


def test_replays_never_dispatch_again_even_with_new_approval(env):
    a, _, journal, executor, clock = env
    plan, approval = plan_for(env)
    executor.execute(plan, approval, dry_run=False)
    executor.execute(plan, approval, dry_run=False)
    new = Approval(
        plan.account_id,
        plan.plan_id,
        plan.digest,
        "trash",
        "human:test",
        uuid4().hex,
        uuid4().hex,
        clock[0],
        clock[0] + 100,
    )
    executor.execute(plan, journal.approve(plan, new), dry_run=False)
    assert a.calls == [("trash", "a")]


@pytest.mark.parametrize("label", ["STARRED", "IMPORTANT", "SENT", "DRAFT", "TRASH", "SPAM"])
def test_changed_protection_skips(env, label):
    a, _, _, executor, _ = env
    plan, approval = plan_for(env)
    a.messages["a"] = replace(a.messages["a"], labels=frozenset({label}))
    assert executor.execute(plan, approval, dry_run=False)["skipped"] == 1
    assert not a.calls


def test_new_star_in_matching_thread_member_wins(env):
    a, _, _, executor, _ = env
    plan, approval = plan_for(env)
    get = a.get_thread
    a.get_thread = lambda tid: [replace(m, labels=m.labels | {"STARRED"}) for m in get(tid)]
    assert executor.execute(plan, approval, dry_run=False)["skipped"] == 1
    assert not a.calls


def test_sender_and_sent_thread_protection(env):
    a, store, _, executor, _ = env
    plan, approval = plan_for(env, ids=("a", "b"))
    a.messages["sent"] = replace(a.messages["a"], id="sent", labels=frozenset({"SENT"}))
    a.messages["b"] = replace(a.messages["b"], raw_from="other@example.invalid")
    assert executor.execute(plan, approval, dry_run=False)["skipped"] == 2
    assert not a.calls
    store.protect_sender(plan.account_id, plan.sender)
    assert executor.execute(plan, approval, dry_run=False)["skipped"] == 2


def test_failed_intent_transaction_prevents_network_call(env, monkeypatch):
    a, store, journal, executor, _ = env
    plan, approval = plan_for(env)

    def fail(*args):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(store, "_event", fail)
    with pytest.raises(sqlite3.Error):
        executor.execute(plan, approval, dry_run=False)
    assert not a.calls and not journal.operations(plan.account_id)


def test_timeout_is_unknown_and_blocks_entire_account(env):
    a, _, journal, executor, _ = env
    plan, approval = plan_for(env, ids=("a", "b"))
    a.timeout = "trash"
    result = executor.execute(plan, approval, dry_run=False)
    assert result["unknown"] == 1 and result["blocked"]
    assert a.calls == [("trash", "a")]
    assert journal.operations(plan.account_id)[0]["state"] == "unknown"
    other, ap = plan_for(env, ids=("b",))
    assert executor.execute(other, ap, dry_run=False)["blocked"]
    assert len(a.calls) == 1


def test_sqlite_reopen_recovery_never_retries(env):
    from inbox_reclaimer.sender.journal import SenderJournal
    from inbox_reclaimer.sender.executor import SenderExecutor

    a, store, journal, _, clock = env
    plan, approval = plan_for(env)
    operation = journal.begin(plan, approval, "a", "trash", a.get_metadata("a"))
    # A second connection observes the durable intent even without a graceful close.
    with JournalStore(store.path) as reopened:
        recovered = SenderJournal(reopened, clock=lambda: clock[0])
        assert recovered.get_plan(plan.account_id, plan.plan_id) == plan
        assert recovered.recover(plan.account_id) == 1
        assert recovered.recover(plan.account_id) == 0
        assert recovered.operations(plan.account_id)[0]["operation_id"] == operation
        assert recovered.operations(plan.account_id)[0]["state"] == "unknown"
        assert SenderExecutor(a, recovered).execute(plan, approval, dry_run=False)["blocked"]
    assert not a.calls


def test_expiry_and_maximum_approval_lifetime(env):
    a, _, journal, executor, clock = env
    plan, approval = plan_for(env)
    evidence = journal.validate_approval(plan, approval, clock[0])
    for changed in [
        replace(evidence, expires_at=evidence.issued_at + 901),
        replace(evidence, issued_at=float("nan")),
        replace(evidence, digest="caller-controlled"),
        replace(evidence, principal=""),
    ]:
        with pytest.raises(ValueError):
            journal.approve(plan, changed)
    clock[0] = evidence.expires_at
    with pytest.raises(ValueError):
        executor.execute(plan, approval, dry_run=False)
    assert not a.calls


def test_scope_and_approval_are_immutable_even_direct_sql(env):
    _, store, journal, _, clock = env
    plan, approval = plan_for(env)
    with pytest.raises(ValueError):
        journal.validate_approval(replace(plan, ids=("b",)), approval, clock[0])
    for sql in [
        "UPDATE sender_plans SET sender='other@example.invalid'",
        "DELETE FROM sender_plans",
        "UPDATE sender_approvals SET expires_at=expires_at+1",
        "DELETE FROM sender_approvals",
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            with store.conn:
                store.conn.execute(sql)
    evidence = journal.validate_approval(plan, approval, clock[0])
    for copied in [replace(evidence, event_id=uuid4().hex), replace(evidence, challenge_id=uuid4().hex)]:
        with pytest.raises((ValueError, sqlite3.IntegrityError)):
            journal.approve(plan, copied)
    assert store.conn.execute("SELECT name FROM sqlite_master WHERE name='no_operations_gate_a'").fetchone()


def test_capability_and_identity_mismatch_fail_before_effect(env):
    a, _, _, executor, _ = env
    plan, approval = plan_for(env)
    a.validate_capability = lambda action: (_ for _ in ()).throw(GateClosed("denied"))
    with pytest.raises(GateClosed):
        executor.execute(plan, approval, dry_run=False)
    a.identity = Identity("other@example.invalid", "fake-client")
    with pytest.raises(IdentityMismatch):
        executor.execute(plan, approval, dry_run=False)
    assert not a.calls


def test_identity_change_after_effect_is_unknown(env):
    a, _, journal, executor, _ = env
    plan, approval = plan_for(env)
    a.after_write = lambda *_: setattr(a, "identity", Identity("other@example.invalid", "fake-client"))
    assert executor.execute(plan, approval, dry_run=False)["unknown"] == 1
    assert journal.operations(plan.account_id)[0]["state"] == "unknown"


def test_quota_wait_precedes_final_safety_reads(env):
    a, _, _, executor, clock = env
    plan, approval = plan_for(env)

    def prepare(action):
        clock[0] += 20
        a.messages["a"] = replace(a.messages["a"], labels=frozenset({"STARRED"}))

    a.prepare = prepare
    assert executor.execute(plan, approval, dry_run=False)["skipped"] == 1
    assert not a.calls


@pytest.mark.parametrize("delay", [11, 901])
def test_final_transport_delay_cannot_outlive_safety_or_approval(env, delay):
    a, _, _, executor, clock = env
    plan, approval = plan_for(env)
    guards, installed = [], []

    def install(guard):
        guards.append(guard)
        installed.append(True)

    a.set_dispatch_guard = install
    original = a.trash_ids

    def delayed(ids):
        clock[0] += delay
        assert guards, "Executor must provide a last-moment local dispatch check"
        guards.pop()()
        return original(ids)

    a.trash_ids = delayed
    result = executor.execute(plan, approval, dry_run=False)
    assert installed == [True]
    assert guards == []
    assert not a.calls
    assert result["unknown"] == 1 or result["skipped"] == 1


def test_stale_safety_reads_do_not_dispatch(env):
    a, _, _, executor, clock = env
    plan, approval = plan_for(env)
    get = a.get_thread

    def slow(tid):
        clock[0] += 11
        return get(tid)

    a.get_thread = slow
    assert executor.execute(plan, approval, dry_run=False)["skipped"] == 1
    assert not a.calls


def test_acknowledged_effect_postread_failure_is_unknown(env):
    a, _, _, executor, _ = env
    plan, approval = plan_for(env)

    def postread_failure(*_):
        a.get_metadata = lambda _: (_ for _ in ()).throw(OSError("read failed"))

    a.after_write = postread_failure
    assert executor.execute(plan, approval, dry_run=False)["unknown"] == 1
    assert a.calls == [("trash", "a")]


def test_restore_rejects_unconfirmed_or_wrong_source(env):
    a, _, journal, executor, _ = env
    source, _ = plan_for(env)
    with pytest.raises(ValueError):
        plan_for(env, action="restore", source=source.plan_id)
    source, approval = plan_for(env)
    executor.execute(source, approval, dry_run=False)
    with pytest.raises(ValueError):
        plan_for(env, ids=("b",), action="restore", source=source.plan_id)
    assert a.calls == [("trash", "a")]


def test_restore_external_label_conflict_is_preserved(env):
    a, _, _, executor, _ = env
    plan, approval = trash_then_restore_plan(env)
    a.messages["a"] = replace(a.messages["a"], labels=a.messages["a"].labels | {"Label_external"})
    assert executor.restore(plan, approval, dry_run=False)["skipped"] == 1
    assert a.calls == [("trash", "a")]


@pytest.mark.parametrize("step", ["untrash", "repair"])
def test_partial_restore_timeout_blocks_without_retry(env, step):
    a, _, journal, executor, _ = env
    plan, approval = trash_then_restore_plan(env)
    a.timeout = step
    result = executor.restore(plan, approval, dry_run=False)
    assert result["unknown"] == 1 and result["blocked"]
    calls = list(a.calls)
    assert executor.restore(plan, approval, dry_run=False)["blocked"]
    assert a.calls == calls
    assert any(o["state"] == "unknown" for o in journal.operations(plan.account_id))


def test_external_edit_after_untrash_stops_repair(env):
    a, _, _, executor, _ = env
    plan, approval = trash_then_restore_plan(env)

    def external(step, i):
        if step == "untrash":
            a.messages[i] = replace(a.messages[i], labels=a.messages[i].labels | {"Label_external"})

    a.after_write = external
    assert executor.restore(plan, approval, dry_run=False)["unknown"] == 1
    assert a.calls == [("trash", "a"), ("untrash", "a")]
    assert "Label_external" in a.messages["a"].labels
