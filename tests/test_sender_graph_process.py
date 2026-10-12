"""Real SqliteSaver across OS process death, with a durable synthetic call log."""

import json
import os
from pathlib import Path
import subprocess
import sys

from langgraph.checkpoint.sqlite import SqliteSaver
import pytest
import inbox_reclaimer

from inbox_reclaimer.profile import ProfilePaths


WORKER = Path(__file__).with_name("sender_graph_process_worker.py")


def process(root, mode, *, approval=None, fault=None, now=None, expected=0):
    command = [sys.executable, str(WORKER), str(root), mode]
    for name, value in (("approval", approval), ("fault", fault), ("now", now)):
        if value is not None:
            command += ["--" + name, str(value)]
    env = os.environ.copy()
    # Do not depend on an editable install or pytest's in-process pythonpath.
    env["PYTHONPATH"] = str(Path(inbox_reclaimer.__file__).resolve().parent.parent)
    run = subprocess.run(
        command, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=40
    )
    assert run.returncode == expected, (run.stdout, run.stderr)
    return json.loads(run.stdout) if run.stdout.strip() else None


def snapshot(root):
    with SqliteSaver.from_conn_string(str(ProfilePaths(root).checkpoints)) as saver:
        return saver.get_tuple({"configurable": {"thread_id": "sender:plan"}})


def test_process_termination_after_interrupt_then_list_and_approved_resume(tmp_path):
    process(tmp_path, "prepare", fault="after_interrupt", expected=73)
    saved = snapshot(tmp_path)
    assert any(channel == "__interrupt__" for _, channel, _ in saved.pending_writes)
    listed = process(tmp_path, "list")
    assert listed["status"] == "awaiting_approval"
    assert listed["calls"] == listed["operations"] == []
    assert snapshot(tmp_path) == saved
    approval = process(tmp_path, "approve")["approval_id"]
    accepted = process(tmp_path, "resume", approval=approval)
    assert accepted["status"] == "sender_run_finished"
    assert accepted["calls"] == ["private-a", "private-b"]
    duplicate = process(tmp_path, "resume", approval=approval)
    assert duplicate["replayed_result"]
    assert duplicate["calls"] == accepted["calls"]


def test_second_process_reject_is_durable_and_has_no_effects(tmp_path):
    process(tmp_path, "prepare", fault="after_interrupt", expected=73)
    rejected = process(tmp_path, "reject")
    assert rejected["status"] == "rejected"
    assert rejected["calls"] == rejected["operations"] == []
    assert process(tmp_path, "list")["status"] == "rejected"
    approval = process(tmp_path, "approve")["approval_id"]
    process(tmp_path, "resume", approval=approval, expected=2)
    assert process(tmp_path, "list")["calls"] == []


@pytest.mark.parametrize("bad", ["fabricated", "expired"])
def test_second_process_invalid_reference_leaves_interrupt_untouched(tmp_path, bad):
    process(tmp_path, "prepare")
    approval = "fabricated" if bad == "fabricated" else process(tmp_path, "approve")["approval_id"]
    saved = snapshot(tmp_path)
    process(tmp_path, "resume", approval=approval, now=1200, expected=2)
    assert snapshot(tmp_path) == saved
    assert process(tmp_path, "list")["calls"] == []
    fresh = process(tmp_path, "approve", now=1200)["approval_id"]
    assert process(tmp_path, "resume", approval=fresh, now=1200)["calls"] == ["private-a", "private-b"]


@pytest.mark.parametrize(
    "stage,expected_calls,expected_state",
    [
        ("before_intent", [], None),
        ("after_intent", [], "unknown"),
        ("before_dispatch", [], "unknown"),
        ("after_dispatch", ["private-a"], "unknown"),
        ("after_response", ["private-a"], "unknown"),
        ("before_outcome", ["private-a"], "unknown"),
        ("after_outcome", ["private-a"], "confirmed"),
        ("before_checkpoint", ["private-a", "private-b"], "confirmed"),
        ("after_checkpoint", ["private-a", "private-b"], "confirmed"),
    ],
)
def test_process_fault_boundaries_never_duplicate_effects(tmp_path, stage, expected_calls, expected_state):
    process(tmp_path, "prepare")
    approval = process(tmp_path, "approve")["approval_id"]
    process(tmp_path, "resume", approval=approval, fault=stage, expected=73)
    listed = process(tmp_path, "list")
    assert listed["calls"] == expected_calls
    resumed = process(tmp_path, "resume", approval=approval)
    if expected_state == "unknown":
        assert resumed["status"] == "blocked"
        assert resumed["calls"] == expected_calls
        assert resumed["operations"][0]["state"] == "unknown"
    else:
        assert resumed["status"] == "sender_run_finished"
        assert resumed["calls"] == ["private-a", "private-b"]
        assert all(o["state"] == "confirmed" for o in resumed["operations"])
    assert len(resumed["calls"]) == len(set(resumed["calls"]))
    duplicate = process(tmp_path, "resume", approval=approval)
    assert duplicate["replayed_result"]
    assert duplicate["calls"] == resumed["calls"]


@pytest.mark.parametrize("stage", ["before_export", "after_export"])
def test_export_process_failure_never_replays_completed_effects(tmp_path, stage):
    approval = process(tmp_path, "approve")["approval_id"]
    assert process(tmp_path, "resume", approval=approval)["calls"] == ["private-a", "private-b"]
    process(tmp_path, "export", fault=stage, expected=73)
    restored = process(tmp_path, "resume", approval=approval)
    assert restored["replayed_result"]
    assert restored["calls"] == ["private-a", "private-b"]
    process(tmp_path, "export")
    first = (tmp_path / "audit.jsonl").read_bytes()
    process(tmp_path, "export")
    assert (tmp_path / "audit.jsonl").read_bytes() == first


def test_crash_then_expiry_requires_real_waiting_boundary_before_reapproval(tmp_path):
    process(tmp_path, "prepare")
    old = process(tmp_path, "approve")["approval_id"]
    process(tmp_path, "resume", approval=old, fault="after_outcome", expected=73)
    fresh = process(tmp_path, "approve", now=1200)["approval_id"]
    saved = snapshot(tmp_path)
    process(tmp_path, "resume", approval=fresh, now=1200, expected=2)
    assert snapshot(tmp_path) == saved
    waiting = process(tmp_path, "resume", approval=old, now=1200)
    assert waiting["status"] == "awaiting_approval"
    assert waiting["calls"] == ["private-a"]
    result = process(tmp_path, "resume", approval=fresh, now=1200)
    assert result["status"] == "sender_run_finished"
    assert result["calls"] == ["private-a", "private-b"]
    assert [o["approval_id"] for o in result["operations"]] == [old, fresh]
