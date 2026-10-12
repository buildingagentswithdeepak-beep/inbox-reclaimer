"""Integration regressions discovered while exercising the release, not snapshots."""


import pytest
from typer.testing import CliRunner

from inbox_reclaimer.cli import app
from inbox_reclaimer.models import Identity
from inbox_reclaimer.profile import private_write
from inbox_reclaimer.storage import JournalStore


@pytest.mark.parametrize(
    "name", ["journal.db", "cache.db", "checkpoints.db", "cache.db-wal", "checkpoints.db-shm"]
)
def test_repository_export_cannot_overwrite_other_application_stores(tmp_path, name):
    with JournalStore(tmp_path / "journal.db") as journal:
        journal.bind_account(Identity("owner@example.test", "client"))
        target = tmp_path / name
        with pytest.raises(ValueError, match="overwrite"):
            journal.export_audit(target)


def test_failed_permission_setup_cleans_private_export_temporary(tmp_path, monkeypatch):
    def deny(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("inbox_reclaimer.profile.make_private", deny)
    with pytest.raises(OSError):
        private_write(tmp_path / "report.html", "private content")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "content",
    [
        "[quota]\nunknown_setting = 5",
        '[privacy]\nredact_subjects = "false"',
        "quota = [1,2,3]",
    ],
)
def test_invalid_config_is_classified_without_profile_or_token_access(tmp_path, monkeypatch, content):
    config = tmp_path / "config.toml"
    config.write_text(content)
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    result = CliRunner().invoke(app, ["--config", str(config), "analyze"])
    assert result.exit_code == 2
    assert "configuration" in result.output


def test_confirm_cannot_misuse_read_action_to_enter_profile(monkeypatch):
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    result = CliRunner().invoke(
        app, ["confirm", "--plan", "p", "--revision", "1", "--batch", "b", "--action", "read"]
    )
    assert result.exit_code == 2
    assert "Gate A" in result.output
