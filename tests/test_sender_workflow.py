from dataclasses import replace

from langgraph.checkpoint.sqlite import SqliteSaver
import pytest

from inbox_reclaimer.models import IdentityMismatch
from inbox_reclaimer.sender.workflow import run_sender_workflow
from sender_graph_helper import GraphEnvironment


@pytest.fixture
def env(tmp_path):
    fixture = GraphEnvironment(tmp_path)
    yield fixture
    fixture.close()


def checkpoint(env):
    with SqliteSaver.from_conn_string(str(env.paths.checkpoints)) as saver:
        return saver.get_tuple({"configurable": {"thread_id": "sender:plan"}})


def assert_private(env):
    with SqliteSaver.from_conn_string(str(env.paths.checkpoints)) as saver:
        evidence = repr(list(saver.list(None)))
    for secret in ("private-a", "private-b", "news@example.test", "owner@example.test", "PRIVATE SUBJECT"):
        assert secret not in evidence


def test_no_approval_creates_real_durable_interrupt_and_list_keeps_it(env):
    result = env.run(writer=False)
    assert result["status"] == "awaiting_approval"
    saved = checkpoint(env)
    assert saved.pending_writes
    assert any(channel == "__interrupt__" for _, channel, _ in saved.pending_writes)
    for _ in range(2):
        assert env.run(decision="list", writer=False)["status"] == "awaiting_approval"
        assert checkpoint(env).config == saved.config
    assert not env.mailbox.calls
    assert not env.journal.operations(env.plan.account_id)
    assert_private(env)


def test_sender_graph_reopen_is_inspection_only_and_checkpoint_contains_no_mail(env):
    approval = env.approve()
    first = env.run(approval)
    assert first["status"] == "sender_run_finished"
    assert first["counts"]["confirmed"] == 2
    assert env.run(approval, writer=False)["replayed_result"]
    assert env.run(writer=False)["replayed_result"]
    assert env.mailbox.calls == ["private-a", "private-b"]
    with pytest.raises(IdentityMismatch):
        env.run(env.approve())
    assert_private(env)


@pytest.mark.parametrize("reference", [True, {"approved": True}, "fabricated", ""])
def test_fabricated_approval_never_rewrites_checkpoint(env, reference):
    env.run(writer=False)
    saved = checkpoint(env)
    with pytest.raises(ValueError):
        env.run(reference)
    assert checkpoint(env) == saved
    assert not env.mailbox.calls


def test_wrong_scope_and_changed_plan_are_rejected_even_for_list(env):
    env.run(writer=False)
    saved = checkpoint(env)
    other = replace(env.plan, plan_id="other", ids=("private-a",))
    env.journal.save_plan(other)
    with pytest.raises(ValueError):
        env.run(env.approve(other))
    with pytest.raises(IdentityMismatch):
        run_sender_workflow(
            env.paths,
            env.identity,
            env.journal,
            None,
            replace(env.plan, ids=("private-a",)),
            decision="list",
        )
    with pytest.raises(IdentityMismatch):
        run_sender_workflow(
            env.paths,
            replace(env.identity, email="other@example.test"),
            env.journal,
            None,
            env.plan,
            decision="list",
        )
    assert checkpoint(env) == saved
    assert not env.mailbox.calls


def test_reject_is_durable_and_cannot_be_approved_later(env):
    env.run(writer=False)
    rejected = env.run(decision="reject", writer=False)
    assert rejected["status"] == "rejected"
    assert env.run(writer=False)["status"] == "rejected"
    with pytest.raises(IdentityMismatch):
        env.run(env.approve())
    assert not env.mailbox.calls


@pytest.mark.parametrize("decision", [True, "approve", {"approved": True}])
def test_decision_is_navigation_not_authorization(env, decision):
    with pytest.raises(ValueError):
        env.run(decision=decision)
    assert not env.mailbox.calls


def test_writer_required_only_for_actual_approved_dispatch(env):
    env.run(writer=False)
    saved = checkpoint(env)
    with pytest.raises(ValueError, match="executor"):
        env.run(env.approve(), writer=False)
    assert checkpoint(env) == saved
    assert env.run(decision="list", writer=False)["status"] == "awaiting_approval"


@pytest.mark.parametrize("invalidation", ["expiry", "revocation"])
def test_mid_run_invalidation_waits_and_fresh_approval_only_attempts_remaining(env, invalidation):
    approval = env.approve()

    def invalidate():
        if invalidation == "expiry":
            env.clock[0] += 101
        else:
            env.journal.revoke_approval(env.plan.account_id, approval, "human:synthetic")

    env.mailbox.after_write = invalidate
    result = env.run(approval)
    assert result["status"] == "awaiting_approval"
    assert result["counts"]["confirmed"] == 1
    assert env.mailbox.calls == ["private-a"]
    saved = checkpoint(env)
    assert env.run(approval, writer=False)["status"] == "awaiting_approval"
    with pytest.raises(ValueError):
        env.run("fabricated")
    assert checkpoint(env) == saved
    env.mailbox.after_write = lambda: None
    fresh = env.approve()
    result = env.run(fresh)
    assert result["status"] == "sender_run_finished"
    assert result["approval_id"] == fresh
    assert env.mailbox.calls == ["private-a", "private-b"]
    assert [o["approval_id"] for o in env.journal.operations(env.plan.account_id)] == [approval, fresh]
    assert_private(env)


def test_unrelated_executor_error_does_not_become_reapproval(env, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("unrelated failure")

    monkeypatch.setattr(env.executor, "execute", fail)
    with pytest.raises(ValueError, match="unrelated failure"):
        env.run(env.approve())
    saved = checkpoint(env)
    with pytest.raises(IdentityMismatch):
        env.run(env.approve())
    assert checkpoint(env) == saved


def test_local_prepare_after_interruption_returns_fresh_native_boundary(env, monkeypatch):
    original = env.executor.execute

    def stop(*args, **kwargs):
        raise ValueError("synthetic interruption before first intent")

    monkeypatch.setattr(env.executor, "execute", stop)
    approval = env.approve()
    with pytest.raises(ValueError):
        env.run(approval)
    monkeypatch.setattr(env.executor, "execute", original)
    result = env.run(writer=False)
    assert result["status"] == "awaiting_approval"
    assert env.journal.approval_status(env.plan.account_id)[0]["state"] == "revoked"
    assert not env.mailbox.calls
    fresh = env.approve()
    assert env.run(fresh)["status"] == "sender_run_finished"
    assert env.mailbox.calls == ["private-a", "private-b"]


def test_recovered_unknown_can_resume_only_remaining_under_fresh_approval(env):
    from uuid import uuid4
    from inbox_reclaimer.sender.reconciliation import reconcile_external
    from inbox_reclaimer.sender.models import Approval

    def timeout():
        raise TimeoutError("synthetic interrupted write")

    env.mailbox.after_write = timeout
    old = env.approve()
    assert env.run(old)["status"] == "blocked"
    # Operator external recovery, modelled entirely inside the synthetic mailbox.
    env.mailbox.messages["private-a"] = replace(
        env.mailbox.messages["private-a"], labels=frozenset({"INBOX"})
    )

    def confirm(plan, identity, messages, **kwargs):
        return Approval(
            plan.account_id,
            plan.plan_id,
            plan.digest,
            plan.action,
            "synthetic-human",
            uuid4().hex,
            uuid4().hex,
            env.clock[0],
            env.clock[0] + 100,
        )

    assert (
        reconcile_external(
            env.journal,
            env.mailbox,
            env.identity,
            env.plan.sender,
            confirm=confirm,
            clock=lambda: env.clock[0],
        )["reconciled"]
        == 1
    )
    env.mailbox.after_write = lambda: None
    assert env.run(writer=False)["status"] == "awaiting_approval"
    assert env.mailbox.calls == ["private-a"]
    result = env.run(env.approve())
    assert result["status"] == "sender_run_finished"
    assert env.mailbox.calls == ["private-a", "private-b"]
    assert env.mailbox.messages["private-a"].labels == frozenset({"INBOX"})


def test_terminal_checkpoint_missing_approval_uses_journal_for_inspection_only(env):
    from langgraph.graph import StateGraph, START, END
    from inbox_reclaimer.sender.workflow import SenderState

    approval = env.approve()
    assert env.run(approval)["status"] == "sender_run_finished"
    # Model a lagging reference without altering any authoritative journal evidence.
    with SqliteSaver.from_conn_string(str(env.paths.checkpoints)) as saver:
        builder = StateGraph(SenderState)
        builder.add_node("dispatch", lambda state: {})
        builder.add_edge(START, "dispatch")
        builder.add_edge("dispatch", END)
        graph = builder.compile(checkpointer=saver)
        graph.update_state(
            {"configurable": {"thread_id": "sender:plan"}}, {"approval_id": None}, as_node="dispatch"
        )
    assert env.run(approval, writer=False)["replayed_result"]
    with pytest.raises(IdentityMismatch):
        env.run(env.approve(), writer=False)
    assert env.mailbox.calls == ["private-a", "private-b"]


def test_unknown_stops_blocked_without_graph_retry(env):
    def timeout():
        raise TimeoutError("PRIVATE SUBJECT")

    env.mailbox.after_write = timeout
    approval = env.approve()
    assert env.run(approval)["status"] == "blocked"
    assert env.run(approval)["status"] == "blocked"
    assert env.mailbox.calls == ["private-a"]
    assert env.journal.operations(env.plan.account_id)[0]["state"] == "unknown"
    assert_private(env)
