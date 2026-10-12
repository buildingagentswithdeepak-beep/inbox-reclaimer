import json

import pytest
from typer.testing import CliRunner

from inbox_reclaimer.cli import app


@pytest.fixture
def local(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "_hermes_home.py").write_text(
        'import os\nfrom pathlib import Path\ndef get_hermes_home():\n    return Path(os.environ["HERMES_HOME"])\n'
    )
    home = tmp_path / "profile"
    monkeypatch.setenv("HERMES_HOME", str(home))
    return ["--workspace-scripts", str(scripts), "--demo"], home


def invoke(args):
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, (result.output, result.exception)
    return result


def test_sender_cleanup_is_preview_by_default_and_preserves_analysis_cache(local):
    args, home = local
    report = home / "inbox_reclaimer/reports/report-sender.html"
    result = invoke(
        args
        + [
            "sender-cleanup",
            "--sender",
            "newsletter@example.test",
            "--max-messages",
            "10",
            "--html",
            str(report),
        ]
    )
    data = json.loads(result.stdout)
    assert data["examined_count"] == 10
    assert data["eligible_count"] == 8
    assert not data["approval_created"] and not data["mail_changed"]
    assert all(m["subject"] is None for m in data["messages"])
    assert report.exists()
    assert json.loads(invoke(args + ["status"]).stdout)["inventory"] is None
    assert not (home / "google_token.json").exists()


def test_hermes_sender_preview_contains_no_addresses_or_message_samples(local):
    args, _ = local
    result = invoke(args + ["--hermes", "sender-cleanup", "--sender", "newsletter@example.test"])
    assert "@" not in result.output
    assert "newsletter-000" not in result.output
    assert "messages" not in json.loads(result.stdout)


@pytest.mark.parametrize(
    "args",
    [
        ["sender-cleanup", "--sender", "news@example.test", "--execute"],
        ["sender-restore", "--source-plan", "plan", "--execute"],
    ],
)
def test_live_sender_effects_are_blocked_before_any_profile_access(args, monkeypatch):
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert "interactive local terminal" in result.output


def test_sender_query_input_and_unbounded_limit_rejected_before_profile(monkeypatch):
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    for args in [
        ["--sender", "a@example.test OR from:b@example.test"],
        ["--sender", "a@example.test", "--max-messages", "1001"],
    ]:
        result = CliRunner().invoke(app, ["sender-cleanup"] + args)
        assert result.exit_code == 2


def test_demo_native_confirmation_to_journaled_execution(local, monkeypatch):
    import time
    from uuid import uuid4
    from inbox_reclaimer.sender.models import Approval

    args, _ = local
    monkeypatch.setattr("inbox_reclaimer.sender.commands._execution_preflight", lambda options, execute: None)

    def decision(plan, identity, messages, synthetic):
        assert synthetic and len(messages) == len(plan.ids)
        now = time.time()
        return Approval(
            identity.account_id,
            plan.plan_id,
            plan.digest,
            plan.action,
            "synthetic-test",
            uuid4().hex,
            uuid4().hex,
            now,
            now + 900,
        )

    monkeypatch.setattr("inbox_reclaimer.sender.confirmation.confirm_plan", decision)
    result = invoke(
        args + ["sender-cleanup", "--sender", "newsletter@example.test", "--max-messages", "5", "--execute"]
    )
    data = json.loads(result.stdout)
    assert data["fixture"] == "synthetic"
    assert data["result"]["counts"]["confirmed"] == 3
    status = json.loads(invoke(args + ["sender-status"]).stdout)
    assert status["outcomes"]["confirmed"] == 3


def test_cancelled_native_confirmation_has_no_effects(local, monkeypatch):
    args, _ = local
    monkeypatch.setattr("inbox_reclaimer.sender.commands._execution_preflight", lambda options, execute: None)
    monkeypatch.setattr("inbox_reclaimer.sender.confirmation.confirm_plan", lambda *args, **kwargs: None)
    result = invoke(args + ["sender-cleanup", "--sender", "newsletter@example.test", "--execute"])
    assert json.loads(result.stdout)["result"]["decision"] == "rejected"
    assert json.loads(invoke(args + ["sender-status"]).stdout)["outcomes"] == {}


def test_local_revoke_lists_invalidated_approval_without_new_effects(local, monkeypatch):
    from inbox_reclaimer.sender import commands

    test_demo_native_confirmation_to_journaled_execution(local, monkeypatch)
    args, _ = local
    before = json.loads(invoke(args + ["sender-status"]).stdout)["outcomes"]
    listed = json.loads(invoke(args + ["sender-approvals"]).stdout)
    approval_id = listed["approvals"][0]["approval_id"]

    # CliRunner installs non-TTY streams. Override only the detection seam.
    monkeypatch.setattr(commands, "_require_local_revocation", lambda options: None)
    result = json.loads(invoke(args + ["sender-revoke", "--approval", approval_id]).stdout)
    assert result["invalidated"] and result["new_record"] and not result["mail_changed"]
    assert json.loads(invoke(args + ["sender-approvals"]).stdout)["approvals"][0]["state"] == "revoked"
    assert json.loads(invoke(args + ["sender-status"]).stdout)["outcomes"] == before


def test_noninteractive_revocation_refuses_before_profile(monkeypatch):
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    result = CliRunner().invoke(app, ["sender-revoke", "--approval", "opaque-reference"])
    assert result.exit_code == 2 and "interactive local terminal" in result.output


def test_missing_or_noninteractive_approval_never_creates_operations(local):
    args, _ = local
    result = CliRunner().invoke(
        app, args + ["sender-cleanup", "--sender", "newsletter@example.test", "--execute"]
    )
    assert result.exit_code == 2
    assert "interactive local terminal" in result.output
