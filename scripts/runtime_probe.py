"""Two-process checkpoint/interrupt/resume acceptance probe; no Gmail integration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict, total=False):
    reference: str
    decision: str
    completion_count: int


def review(state: State):
    while True:
        response = interrupt({"reference": state["reference"], "mutation_enabled": False})
        if response == "list":
            continue
        return {"decision": response if response in {"approved", "rejected"} else "invalid"}


def finish(state: State):
    return {"completion_count": state.get("completion_count", 0) + 1}


def run(root: Path, phase: str, case: str):
    root.mkdir(parents=True, exist_ok=True)
    builder = StateGraph(State)
    builder.add_node("review", review)
    effect_file = root / f"{case}-fake-effect.log"

    def instrumented_finish(state):
        with effect_file.open("a", encoding="utf-8") as stream:
            stream.write("completed\n")
        return finish(state)

    builder.add_node("finish", instrumented_finish)
    builder.add_edge(START, "review")
    builder.add_edge("review", "finish")
    builder.add_edge("finish", END)
    config = {"configurable": {"thread_id": case}}
    with SqliteSaver.from_conn_string(str(root / "probe.db")) as saver:
        app = builder.compile(checkpointer=saver)
        if phase == "pause":
            result = app.invoke({"reference": "opaque-batch", "completion_count": 0}, config)
            assert result["__interrupt__"]
            assert app.get_state(config).values["completion_count"] == 0
            assert not effect_file.exists()
        else:
            snapshot = app.get_state(config)
            assert snapshot.next == ("review",)
            assert snapshot.values["completion_count"] == 0
            if case == "list":
                result = app.invoke(Command(resume="list"), config)
                assert result["__interrupt__"]
                assert app.get_state(config).values["completion_count"] == 0
            choice = "approved" if case in {"approved", "list"} else case
            result = app.invoke(Command(resume=choice), config)
            assert result["decision"] == (choice if choice in {"approved", "rejected"} else "invalid")
            assert result["completion_count"] == 1
            app.invoke(None, config)
            assert app.get_state(config).values["completion_count"] == 1
            assert effect_file.read_text(encoding="utf-8").splitlines() == ["completed"]
        print(
            json.dumps({"phase": phase, "case": case, "state": app.get_state(config).values, "passed": True})
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pause", "resume"])
    parser.add_argument("case", choices=["approved", "rejected", "list", "invalid", "expired"])
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.phase, args.case)
