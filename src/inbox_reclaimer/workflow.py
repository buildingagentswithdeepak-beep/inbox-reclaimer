"""Reference-only LangGraph orchestration. Gate A has no mutation edges or approval inputs."""

from __future__ import annotations

import os
from typing import Callable, TypedDict
from uuid import uuid4

from .models import Identity, IdentityMismatch, Inventory, Plan
from .profile import ProfilePaths


class ReadState(TypedDict, total=False):
    account_id: str
    workflow_id: str
    inventory_generation: str
    cursor: str
    plan_id: str
    revision: int
    status: str


def run_read_workflow(
    paths: ProfilePaths,
    identity: Identity,
    analyze: Callable[[], Inventory],
    propose: Callable[[], Plan] | None = None,
    workflow_id: str | None = None,
) -> dict:
    # Disable hosted traces before importing the runtime; no mailbox data leaves through callbacks.
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    workflow_id = workflow_id or uuid4().hex

    def analysis_node(state):
        inventory = analyze()
        if inventory.account_id != identity.account_id:
            raise IdentityMismatch("Workflow inventory belongs to another account")
        return {"inventory_generation": inventory.generation, "cursor": inventory.cursor}

    def proposal_node(state):
        plan = propose()
        if (
            plan.account_id != identity.account_id
            or plan.inventory_generation != state["inventory_generation"]
        ):
            raise IdentityMismatch("Workflow proposal does not match the bound inventory")
        return {"plan_id": plan.plan_id, "revision": plan.revision}

    builder = StateGraph(ReadState)
    builder.add_node("analyze", analysis_node)
    builder.add_node("summarize", lambda state: {"status": "read_only_complete"})
    builder.add_edge(START, "analyze")
    if propose is not None:
        builder.add_node("propose", proposal_node)
        builder.add_edge("analyze", "propose")
        builder.add_edge("propose", "summarize")
    else:
        builder.add_edge("analyze", "summarize")
    builder.add_edge("summarize", END)
    config = {"configurable": {"thread_id": workflow_id}, "callbacks": []}
    with SqliteSaver.from_conn_string(str(paths.checkpoints)) as saver:
        saver.conn.execute("PRAGMA journal_mode=WAL")
        saver.conn.execute("PRAGMA synchronous=FULL")
        saver.conn.execute("PRAGMA foreign_keys=ON")
        app = builder.compile(checkpointer=saver)
        previous = app.get_state(config)
        if previous.values:
            if previous.values.get("account_id") != identity.account_id:
                raise IdentityMismatch("Cannot reopen a workflow under another account")
            if not previous.next:
                return dict(previous.values)
            # Gate A restarts only read operations; no approval or external write can be replayed.
            return dict(app.invoke(None, config))
        return dict(app.invoke({"account_id": identity.account_id, "workflow_id": workflow_id}, config))
