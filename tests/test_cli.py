import json

import pytest
from typer.testing import CliRunner

from inbox_reclaimer.cli import app

runner = CliRunner()


@pytest.fixture
def local(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "_hermes_home.py").write_text(
        'import os\nfrom pathlib import Path\ndef get_hermes_home():\n    return Path(os.environ["HERMES_HOME"])\n'
    )
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profile"))
    return ["--workspace-scripts", str(scripts), "--demo"], tmp_path / "profile"


def invoke(args):
    result = runner.invoke(app, args)
    assert result.exit_code == 0, (result.output, result.exception)
    return result


def data(result):
    # Rich status banners go to stderr; stdout is machine-readable JSON.
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "command",
    [
        ["execute", "--approval", "forged", "--execute"],
        ["execute", "--approval", "forged"],
        ["restore", "--source-operation", "forged", "--execute"],
        ["confirm", "--plan", "forged", "--revision", "1", "--batch", "b", "--action", "trash"],
        ["propose", "--action", "permanent_delete", "--source-plan", "forged"],
        ["protections", "remove", "--sender", "a@example.test"],
    ],
)
def test_closed_gate_never_loads_credentials_or_profile(command, monkeypatch):
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    result = runner.invoke(app, command)
    assert result.exit_code == 2
    assert "Gate" in result.output or "unavailable" in result.output


def test_full_offline_cli_flow_redaction_and_cache_boundaries(local, tmp_path):
    args, home = local
    report_path = home / "inbox_reclaimer/reports/demo.html"
    report = data(invoke(args + ["analyze", "--json", "--redact-subjects", "--html", str(report_path)]))
    assert report["fixture"] == "synthetic"
    assert report_path.is_file()
    assert "Synthetic newsletter edition" not in report_path.read_text()
    plan = data(invoke(args + ["propose", "--action", "trash", "--min-batch-mb", "0"]))
    assert plan["executable"] is False
    assert plan["batches"]
    batch = plan["batches"][0]["batch_id"]
    selection = ["--plan", plan["plan_id"], "--revision", str(plan["revision"]), "--batch", batch]
    members = data(invoke(args + ["list"] + selection))
    assert members["ids"]
    assert all(m.get("subject") is None for m in members["messages"])
    rejected = data(invoke(args + ["confirm"] + selection + ["--reject"]))
    assert rejected["decision"] == "rejected"
    after = data(invoke(args + ["list"] + selection))
    assert after["ids"] == members["ids"]
    invoke(args + ["protect", "--sender", "newsletter@example.test"])
    second = data(invoke(args + ["propose", "--min-batch-mb", "0"]))
    assert not second["batches"]
    export_path = home / "inbox_reclaimer/audit/events.jsonl"
    invoke(args + ["audit", "export", "--output", str(export_path)])
    before = export_path.read_bytes()
    invoke(args + ["audit", "export", "--output", str(export_path)])
    assert export_path.read_bytes() == before
    invoke(args + ["cache", "rebuild"])
    assert (home / "inbox_reclaimer/journal.db").is_file()
    assert (home / "inbox_reclaimer/checkpoints.db").is_file()
    assert data(invoke(args + ["status"]))["mutation_enabled"] is False


def test_hermes_surface_minimizes_sender_and_subjects(local):
    args, _ = local
    result = invoke(args + ["--hermes", "analyze", "--json"])
    assert "@example.test" not in result.output
    assert "newsletter-" not in result.output
    assert "Synthetic newsletter edition" not in result.output
    assert data(result)["mutation_enabled"] is False


def test_real_cli_process_help_and_no_token_side_effects(local):
    args, home = local
    invoke(["--help"])
    assert not (home / "google_token.json").exists()
