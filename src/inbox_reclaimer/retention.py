"""Conservative local retention; never delete journal evidence or arbitrary user files."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3


def cleanup(paths, account_id, *, now=None):
    """Caller holds the account lock. Only recognized local outputs/read-only workflows expire."""
    now = now or datetime.now(timezone.utc)
    result = {"reports_removed": 0, "logs_removed": 0, "checkpoints_removed": 0}
    for folder, patterns, days, counter in (
        (paths.reports, ("report-*.html", "report-*.json"), 7, "reports_removed"),
        (paths.root / "logs", ("reclaim-*.jsonl",), 14, "logs_removed"),
    ):
        for pattern in patterns:
            for file in folder.glob(pattern):
                if file.is_symlink() or not file.is_file():
                    continue
                if file.stat().st_mtime < (now - timedelta(days=days)).timestamp():
                    file.unlink()
                    result[counter] += 1
    if not paths.journal.is_file() or not paths.checkpoints.is_file():
        return result
    # Read-only journal inspection; never initialize/reset an absent or unfamiliar journal.
    with sqlite3.connect(f"{paths.journal.as_uri()}?mode=ro", uri=True) as journal:
        account = journal.execute("SELECT account_id FROM accounts").fetchone()
        if not account or account[0] != account_id:
            return result
        if journal.execute("SELECT count(*) FROM operations WHERE state IN ('pending','unknown')").fetchone()[
            0
        ]:
            return result
        sender_table = journal.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sender_operations'"
        ).fetchone()
        if sender_table and journal.execute(
            "SELECT 1 FROM sender_operations WHERE state IN ('pending','unknown') LIMIT 1"
        ).fetchone():
            return result
    from langgraph.checkpoint.sqlite import SqliteSaver

    with SqliteSaver.from_conn_string(str(paths.checkpoints)) as saver:
        saver.setup()
        ids = [row[0] for row in saver.conn.execute("SELECT DISTINCT thread_id FROM checkpoints")]
        for workflow_id in ids:
            item = saver.get_tuple({"configurable": {"thread_id": workflow_id}})
            if item is None:
                continue
            state = item.checkpoint.get("channel_values", {})
            if state.get("account_id") != account_id or state.get("status") != "read_only_complete":
                continue
            # Explicitly narrow to this release's inspection-only workflow state.
            if any(key in state for key in ("approval_id", "operation_id", "operation_ids")):
                continue
            try:
                stamp = datetime.fromisoformat(item.checkpoint["ts"])
                if stamp.tzinfo is None:
                    continue
            except (KeyError, ValueError, TypeError):
                continue
            if stamp < now - timedelta(days=30):
                saver.delete_thread(workflow_id)
                result["checkpoints_removed"] += 1
    return result
