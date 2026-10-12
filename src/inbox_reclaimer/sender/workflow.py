"""Durable, reference-only approval pauses; the journal guards every effect.

The caller holds the account lock throughout and captures native human consent
outside this graph. A resume value is only a reference to that persisted consent.
Completed/blocked runs are inspection-only; recovery is a separate manual path.
"""

from dataclasses import asdict
import os
from typing import TypedDict

from ..models import IdentityMismatch


class SenderState(TypedDict, total=False):
    workflow_version: int
    account_id: str
    plan_id: str
    plan_digest: str
    approval_id: str | None
    status: str
    counts: dict


def _counts(result):
    counters = {}
    for key in ("confirmed", "unknown", "failed", "skipped", "attempted", "restored", "dry_run"):
        value = result.get(key)
        if type(value) in (int, bool):
            counters[key] = value
        elif isinstance(value, (tuple, list)):
            counters[key] = len(value)
    return counters


def run_sender_workflow(paths, identity, journal, executor, plan, approval_id=None, *, decision=None):
    """Prepare, inspect, reject, or resume using an existing native approval ID.

    No writer is needed for preparation/navigation. An active approval cannot be
    swapped after a crash: first resume/inspect its invalidation into a durable
    waiting boundary, then supply fresh approval for the same immutable plan.
    """
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    if decision is not None and (type(decision) is not str or decision not in ("list", "reject")):
        raise ValueError("decision must be list or reject; approval requires a journal reference")
    if approval_id is not None and (type(approval_id) is not str or not approval_id.strip()):
        raise ValueError("Expected a persisted native approval reference")
    if plan.account_id != identity.account_id:
        raise IdentityMismatch("Sender workflow belongs to a different account")

    def checked_plan():
        stored = journal.get_plan(identity.account_id, plan.plan_id)
        if asdict(stored) != asdict(plan):
            raise IdentityMismatch("Sender workflow plan scope changed")
        return stored

    checked_plan()

    def active(reference):
        # Only genuine expired/revoked records may become a new approval pause.
        # Fabricated IDs, mismatched scopes and unrelated errors still fail closed.
        stored = checked_plan()
        try:
            journal.validate_approval(stored, reference, journal.clock())
        except ValueError:
            if any(
                row["approval_id"] == reference
                and row["plan_id"] == stored.plan_id
                and row["state"] in ("expired", "revoked")
                for row in journal.approval_status(identity.account_id)
            ):
                return False
            raise
        return True

    def journal_counts():
        operations = journal.operations(identity.account_id, plan.plan_id)
        counts = {
            status: len({o["message_id"] for o in operations if o["state"] == status})
            for status in ("confirmed", "unknown", "failed", "skipped")
        }
        counts["attempted"] = len({o["message_id"] for o in operations})
        return counts

    def await_approval(state):
        # No effects before interrupt: this node starts again on every resume.
        response = interrupt(
            {"account_id": state["account_id"], "plan_id": state["plan_id"], "status": "awaiting_approval"}
        )
        if response == {"decision": "reject"}:
            if state.get("approval_id"):
                journal.revoke_approval(identity.account_id, state["approval_id"], "workflow:rejection")
            return {"status": "rejected"}
        if type(response) is not str or not response.strip():
            raise ValueError("Resume requires a persisted native approval reference")
        # Recheck after resume; neither Command nor checkpoint state grants consent.
        valid = active(response)
        return {"approval_id": response, "status": "ready" if valid else "awaiting_approval"}

    def dispatch(state):
        stored = checked_plan()
        journal.recover(identity.account_id)
        if journal.blocked(identity.account_id):
            return {"counts": journal_counts(), "status": "blocked"}
        if not active(state["approval_id"]):
            return {"counts": journal_counts(), "status": "awaiting_approval"}
        if executor is None:
            raise ValueError("An executor is required for approved dispatch")
        try:
            result = (
                executor.execute(stored, state["approval_id"], dry_run=False)
                if stored.action == "trash"
                else executor.restore(stored, state["approval_id"], dry_run=False)
            )
        except ValueError:
            # Expiry/revocation can happen between any two messages. Never turn
            # arbitrary execution failures into authorization requests.
            if active(state["approval_id"]):
                raise
            journal.recover(identity.account_id)
            status = "blocked" if journal.blocked(identity.account_id) else "awaiting_approval"
            return {"counts": journal_counts(), "status": status}
        status = (
            "blocked"
            if result.get("blocked") or journal.blocked(identity.account_id)
            else "sender_run_finished"
        )
        return {"counts": _counts(result), "status": status}

    def route(state):
        if state["status"] == "awaiting_approval":
            return "await_approval"
        return "dispatch" if state["status"] == "ready" else END

    builder = StateGraph(SenderState)
    builder.add_node("await_approval", await_approval)
    builder.add_node("dispatch", dispatch)
    builder.add_edge(START, "await_approval")
    builder.add_conditional_edges("await_approval", route)
    builder.add_conditional_edges("dispatch", route)
    expected = {
        "workflow_version": 2,
        "account_id": identity.account_id,
        "plan_id": plan.plan_id,
        "plan_digest": plan.digest,
    }
    config = {"configurable": {"thread_id": "sender:" + plan.plan_id}, "callbacks": []}
    with SqliteSaver.from_conn_string(str(paths.checkpoints)) as saver:
        saver.conn.execute("PRAGMA journal_mode=WAL")
        saver.conn.execute("PRAGMA synchronous=FULL")
        graph = builder.compile(checkpointer=saver)
        previous = graph.get_state(config)
        if previous.values:
            if previous.values.get("workflow_version") != 2:
                raise ValueError("Incompatible sender checkpoint; inspect journal and use manual recovery")
            if any(previous.values.get(key) != value for key, value in expected.items()):
                raise IdentityMismatch("Cannot reuse a sender workflow for a different account or plan scope")
            preparing = approval_id is None and decision is None and executor is None
            restartable = previous.values.get("status") in {"blocked", "ready"} or (
                bool(previous.next) and not previous.interrupts
            )
            if preparing and restartable:
                # Preparation cannot dispatch. Reconcile pending journal intents
                # first, then retire the old grant before creating a new pause.
                journal.recover(identity.account_id)
                if journal.blocked(identity.account_id):
                    if previous.values.get("status") != "blocked":
                        graph.update_state(
                            config, {"status": "blocked", "counts": journal_counts()}, as_node="dispatch"
                        )
                    return dict(graph.get_state(config).values)
                old = previous.values.get("approval_id")
                if old and active(old):
                    journal.revoke_approval(identity.account_id, old, "workflow:reapproval")
                graph.update_state(
                    config, {"status": "awaiting_approval", "counts": journal_counts()}, as_node="dispatch"
                )
                graph.invoke(None, config)
                previous = graph.get_state(config)
            if not previous.next and previous.values.get("status") in {
                "sender_run_finished",
                "blocked",
                "rejected",
            }:
                if approval_id is not None and approval_id != previous.values.get("approval_id"):
                    # Checkpoint persistence can lag the dispatch journal. A
                    # reference already attached to this plan's intent can inspect
                    # its terminal result, but a newly minted/unrelated one cannot.
                    if not any(
                        o["approval_id"] == approval_id
                        for o in journal.operations(identity.account_id, plan.plan_id)
                    ):
                        raise IdentityMismatch("Completed sender workflows are inspection-only")
                return dict(previous.values) | {"replayed_result": True}

        waiting = previous.values.get("status") == "awaiting_approval" and bool(previous.interrupts)
        old_reference = previous.values.get("approval_id")
        valid = False
        if approval_id is not None:
            if old_reference and approval_id != old_reference and not waiting:
                raise IdentityMismatch("Active approval cannot change outside a durable waiting boundary")
            if approval_id == old_reference:
                valid = active(approval_id)
            else:
                # Validate BEFORE persisting any input/resume writes. Invalid references
                # must not poison a legitimate pending approval checkpoint.
                journal.validate_approval(checked_plan(), approval_id, journal.clock())
                valid = True
            if valid and decision is None and executor is None:
                raise ValueError("An executor is required for approved dispatch")

        if not previous.values:
            graph.invoke(
                expected | {"approval_id": None, "status": "awaiting_approval", "counts": {}}, config
            )
            previous = graph.get_state(config)
        if decision == "list":
            return dict(previous.values)
        if decision == "reject":
            if not previous.interrupts or previous.values.get("status") != "awaiting_approval":
                raise ValueError(
                    "Reject requires a waiting approval boundary; revoke the active approval first"
                )
            graph.invoke(Command(resume={"decision": "reject"}), config)
        elif previous.interrupts and previous.values.get("status") == "awaiting_approval":
            if valid:
                graph.invoke(Command(resume=approval_id), config)
        elif approval_id is not None or (old_reference and not active(old_reference)):
            # Resume unfinished dispatch, or establish the reapproval boundary after
            # an old approval expires during process downtime. Never replace it here.
            # Durable approval-node writes can outlive the next checkpoint and
            # leave ready values with a stale interrupt and no scheduled task.
            if previous.values.get("status") == "ready" and not previous.next:
                graph.update_state(
                    config,
                    expected
                    | {
                        "status": "ready",
                        "approval_id": old_reference or approval_id,
                        "counts": journal_counts(),
                    },
                    as_node="await_approval",
                )
            graph.invoke(None, config)
            current = graph.get_state(config)
            if current.interrupts and valid and not old_reference:
                graph.invoke(Command(resume=approval_id), config)
        # Return only the allowlisted state, not LangGraph task/error payloads.
        return dict(graph.get_state(config).values)
