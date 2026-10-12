import pytest

from inbox_reclaimer.models import GateClosed, ReclaimError
from inbox_reclaimer.profile import ProfilePaths, account_lock, gate_check, resolve_profile, private_write


def helper(tmp_path):
    scripts = tmp_path / "skill" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "_hermes_home.py").write_text(
        'import os\nfrom pathlib import Path\ndef get_hermes_home():\n    return Path(os.environ["HERMES_HOME"])\n'
    )
    return scripts


def test_explicit_helper_profile_isolation_a_b_a(tmp_path, monkeypatch):
    scripts = helper(tmp_path)
    seen = []
    for name in ("a", "b", "a"):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / name))
        paths = resolve_profile(scripts)
        paths.initialize()
        seen.append(paths.root)
        assert paths.root == tmp_path / name / "inbox_reclaimer"
    assert seen[0] == seen[2] != seen[1]
    assert not (tmp_path / "a" / "google_token.json").exists()


def test_missing_helper_fails_instead_of_searching_profiles(tmp_path):
    with pytest.raises(ReclaimError, match="helper"):
        resolve_profile(tmp_path / "missing")


@pytest.mark.parametrize("action", ["trash", "restore", "permanent_delete"])
@pytest.mark.parametrize("execute", [True, False])
def test_gates_cannot_be_opened_by_environment_or_execute(monkeypatch, action, execute):
    monkeypatch.setenv("RECLAIM_ENABLE_MUTATIONS", "true")
    with pytest.raises(GateClosed):
        gate_check(action, execute)


def test_private_write_and_account_lock(tmp_path):
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    output = paths.reports / "report.html"
    private_write(output, "safe")
    assert output.read_text() == "safe"
    with account_lock(paths, "a" * 64):
        with pytest.raises(ReclaimError, match="locked"):
            with account_lock(paths, "a" * 64):
                pass
    with account_lock(paths, "a" * 64):
        pass
    with pytest.raises(ReclaimError):
        with account_lock(paths, "../escape"):
            pass


def test_output_cannot_replace_application_state(tmp_path):
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    with pytest.raises(ReclaimError):
        paths.validate_export(paths.journal)
    with pytest.raises(ReclaimError):
        paths.validate_export(tmp_path / "google_token.json")
    paths.validate_export(paths.reports / "okay.html")
