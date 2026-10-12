from pathlib import Path
import subprocess
import sys
import pytest

from inbox_reclaimer.models import Identity, IdentityMismatch, Inventory
from inbox_reclaimer.profile import ProfilePaths
from inbox_reclaimer.workflow import run_read_workflow


@pytest.mark.parametrize("case", ["approved", "rejected", "list", "invalid", "expired"])
def test_real_second_process_reopens_and_resumes_interrupt(tmp_path, case):
    script = Path(__file__).resolve().parents[1] / "scripts/runtime_probe.py"
    for phase in ("pause", "resume"):
        result = subprocess.run(
            [sys.executable, str(script), phase, case, "--root", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert result.returncode == 0, result.stderr
        assert '"passed": true' in result.stdout


def test_workflow_persists_only_references_and_completed_replay_is_inspection(tmp_path):
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    identity = Identity("owner@example.test", "test-client")
    calls = []
    inventory = Inventory(identity.account_id, "gen", "opaque-history", "start", "end", True, (), ())

    def analyze():
        calls.append("read")
        return inventory

    result = run_read_workflow(paths, identity, analyze, workflow_id="workflow-1")
    assert calls == ["read"]
    assert result["inventory_generation"] == "gen"
    assert set(result) <= {
        "account_id",
        "workflow_id",
        "inventory_generation",
        "cursor",
        "plan_id",
        "revision",
        "status",
    }
    again = run_read_workflow(paths, identity, analyze, workflow_id="workflow-1")
    assert again == result
    assert calls == ["read"]
    with pytest.raises(IdentityMismatch):
        run_read_workflow(
            paths, Identity("other@example.test", "test-client"), analyze, workflow_id="workflow-1"
        )
