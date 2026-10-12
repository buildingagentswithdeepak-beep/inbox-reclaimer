"""Architectural release boundaries and real OS-lock lifetime contracts."""

import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest

from inbox_reclaimer.profile import ProfilePaths, account_lock
from inbox_reclaimer.models import ReclaimError


def test_no_permanent_delete_or_model_client_and_gate_a_has_no_mutations():
    root = Path(__file__).parents[1] / "src/inbox_reclaimer"
    for path in root.rglob("*.py"):
        forbidden = {"batchDelete", "delete_ids", "emptyTrash", "OpenAI", "ChatOpenAI"}
        if path.parent.name != "sender":
            forbidden |= {"batchModify", "untrash", "trash"}
        else:
            # Sender trash/restore transports exist but their live release gate is closed.
            forbidden.add("delete")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not calls & forbidden, path.name


def test_account_os_lock_blocks_second_process_and_releases_on_process_death(tmp_path):
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    script = (
        "import sys,time; from pathlib import Path; "
        "from inbox_reclaimer.profile import ProfilePaths,account_lock; "
        "p=ProfilePaths(Path(sys.argv[1])); "
        'lock=account_lock(p,"a"*64); lock.__enter__(); '
        'print("LOCKED",flush=True); time.sleep(60)'
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(tmp_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout.readline().strip() == "LOCKED"
        with pytest.raises(ReclaimError, match="locked"):
            with account_lock(paths, "a" * 64):
                pass
    finally:
        proc.kill()
        proc.communicate(timeout=10)
    with account_lock(paths, "a" * 64):
        pass


@pytest.mark.skipif(os.name != "nt", reason="Windows DACL semantics")
def test_windows_state_acl_is_private_and_inheritable(tmp_path):
    import win32security
    import win32api
    import win32con
    from inbox_reclaimer.profile import private_write

    paths = ProfilePaths(tmp_path)
    paths.initialize()
    target = paths.reports / "report.html"
    private_write(target, "synthetic")
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        owner = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    permitted = {str(owner), str(win32security.CreateWellKnownSid(win32security.WinLocalSystemSid))}
    for path in (paths.root, target):
        security = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
        acl = security.GetSecurityDescriptorDacl()
        actual = {str(acl.GetAce(i)[2]) for i in range(acl.GetAceCount())}
        assert actual == permitted
