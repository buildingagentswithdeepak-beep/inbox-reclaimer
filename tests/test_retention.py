from datetime import datetime, timezone
import os

from inbox_reclaimer.models import Identity, Inventory
from inbox_reclaimer.profile import ProfilePaths
from inbox_reclaimer.retention import cleanup
from inbox_reclaimer.storage import JournalStore
from inbox_reclaimer.workflow import run_read_workflow


def test_only_expired_application_owned_reports_and_logs_are_removed(tmp_path):
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    old_report = paths.reports / "report-old.html"
    new_report = paths.reports / "report-new.html"
    user_file = paths.reports / "keep.html"
    old_log = paths.root / "logs" / "reclaim-old.jsonl"
    for file in (old_report, new_report, user_file, old_log):
        file.write_text("test")
        os.utime(file, (now.timestamp() - 15 * 86400,) * 2)
    os.utime(new_report, (now.timestamp(),) * 2)
    result = cleanup(paths, "a" * 64, now=now)
    assert result["reports_removed"] == 1
    assert result["logs_removed"] == 1
    assert new_report.exists() and user_file.exists()


def test_sender_pending_operations_block_checkpoint_retention(tmp_path):
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    identity = Identity("owner@example.test", "client")
    with JournalStore(paths.journal) as journal:
        journal.bind_account(identity)
        with journal.conn:
            journal.conn.execute("CREATE TABLE sender_operations(account_id TEXT,state TEXT)")
            journal.conn.execute(
                "INSERT INTO sender_operations VALUES (?,?)", (identity.account_id, "unknown")
            )
    inventory = Inventory(identity.account_id, "gen", "H", "start", "end", True, (), ())
    run_read_workflow(paths, identity, lambda: inventory, workflow_id="completed")
    result = cleanup(paths, identity.account_id, now=datetime(2099, 1, 1, tzinfo=timezone.utc))
    assert result["checkpoints_removed"] == 0


def test_only_completed_read_only_checkpoints_expire_and_journal_is_untouched(tmp_path):
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    identity = Identity("owner@example.test", "client")
    with JournalStore(paths.journal) as journal:
        journal.bind_account(identity)
    inventory = Inventory(identity.account_id, "gen", "H", "start", "end", True, (), ())
    run_read_workflow(paths, identity, lambda: inventory, workflow_id="completed")
    before = paths.journal.read_bytes()
    result = cleanup(paths, identity.account_id, now=datetime(2099, 1, 1, tzinfo=timezone.utc))
    assert result["checkpoints_removed"] == 1
    assert paths.journal.read_bytes() == before
    from langgraph.checkpoint.sqlite import SqliteSaver

    with SqliteSaver.from_conn_string(str(paths.checkpoints)) as saver:
        assert saver.get_tuple({"configurable": {"thread_id": "completed"}}) is None
