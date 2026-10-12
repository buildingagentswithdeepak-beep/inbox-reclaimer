"""Local recovery/resume composition, entirely synthetic profiles and approvals."""

import json
from uuid import uuid4
import time

import pytest
from typer.testing import CliRunner
import test_sender_commands as fixtures

from inbox_reclaimer.cli import app
from inbox_reclaimer.sender.models import Approval

local = fixtures.local
invoke = fixtures.invoke


def approve(plan, identity, messages, **kwargs):
    assert kwargs.get("synthetic") is True
    now = time.time()
    return Approval(
        plan.account_id,
        plan.plan_id,
        plan.digest,
        plan.action,
        "synthetic-human",
        uuid4().hex,
        uuid4().hex,
        now,
        now + 900,
    )


def preview_plan(args):
    return json.loads(
        invoke(args + ["sender-cleanup", "--sender", "newsletter@example.test", "--max-messages", "3"]).stdout
    )["plan_id"]


def test_resume_preview_then_native_approval_uses_exact_persisted_selection(local, monkeypatch):
    from inbox_reclaimer.sender import commands

    args, _ = local
    plan_id = preview_plan(args)
    monkeypatch.setattr(
        "inbox_reclaimer.sender.selection.select_sender",
        lambda *a, **k: pytest.fail("resume must not rediscover messages"),
    )
    preview = json.loads(invoke(args + ["sender-resume", "--plan", plan_id]).stdout)
    assert preview["plan_id"] == plan_id and not preview["mail_changed"]
    assert preview["status"] == "awaiting_approval"
    assert json.loads(invoke(args + ["sender-status"]).stdout)["outcomes"] == {}
    monkeypatch.setattr(commands, "_execution_preflight", lambda *a: None)
    monkeypatch.setattr("inbox_reclaimer.sender.confirmation.confirm_plan", approve)
    result = json.loads(invoke(args + ["sender-resume", "--plan", plan_id, "--execute"]).stdout)
    assert result["result"]["plan_id"] == plan_id
    assert result["result"]["counts"]["confirmed"] >= 1
    before = json.loads(invoke(args + ["sender-status"]).stdout)["outcomes"]
    # Completed workflow inspection must not create another native approval/effect.
    monkeypatch.setattr(
        "inbox_reclaimer.sender.confirmation.confirm_plan",
        lambda *a, **k: pytest.fail("completed plan prompted again"),
    )
    again = json.loads(invoke(args + ["sender-resume", "--plan", plan_id, "--execute"]).stdout)
    assert again["result"]["replayed_result"]
    assert json.loads(invoke(args + ["sender-status"]).stdout)["outcomes"] == before


def test_resume_rejection_is_durable_without_writer_or_mail_changes(local, monkeypatch):
    from inbox_reclaimer.sender import commands

    args, _ = local
    plan_id = preview_plan(args)
    monkeypatch.setattr(commands, "_require_local_control", lambda *a: None)
    result = json.loads(invoke(args + ["sender-resume", "--plan", plan_id, "--reject"]).stdout)
    assert result["status"] == "rejected"
    assert json.loads(invoke(args + ["sender-status"]).stdout)["outcomes"] == {}


@pytest.mark.parametrize(
    "args",
    [
        ["sender-resume", "--plan", "plan", "--execute"],
        ["sender-resume", "--plan", "plan", "--reject"],
        ["sender-reconcile", "--sender", "news@example.test"],
    ],
)
def test_live_effect_or_local_decision_rejected_before_profile_when_not_interactive(args, monkeypatch):
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("profile accessed"))
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert "No such command" not in result.output
    assert "interactive local terminal" in result.output or "not released" in result.output


def test_resume_reject_and_execute_are_mutually_exclusive(local, monkeypatch):
    args, _ = local
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("profile accessed"))
    result = CliRunner().invoke(app, args + ["sender-resume", "--plan", "plan", "--execute", "--reject"])
    assert result.exit_code == 2 and "Cannot combine" in result.output


def test_reconcile_is_reader_only_and_forwards_explicit_operation(local, monkeypatch):
    from inbox_reclaimer.sender import commands, reconciliation

    args, _ = local
    monkeypatch.setattr(commands, "_require_local_control", lambda *a: None)

    def reconcile(journal, reader, identity, sender, **kwargs):
        assert sender == "news@example.test"
        assert kwargs["operation_id"] == "opaque-operation"
        assert kwargs["validation"] is False
        assert callable(kwargs["confirm"])
        return {"reconciled": 1, "mail_changed": False, "blocked": False}

    monkeypatch.setattr(reconciliation, "reconcile_external", reconcile)
    monkeypatch.setattr(
        "inbox_reclaimer.sender.gmail.GoogleSenderWriter",
        lambda *a, **k: pytest.fail("recovery must not construct live writer"),
    )
    result = json.loads(
        invoke(
            args + ["sender-reconcile", "--sender", "news@example.test", "--operation", "opaque-operation"]
        ).stdout
    )
    assert not result["mail_changed"] and result["reconciled"] == 1
