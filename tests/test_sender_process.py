"""Crash the actual Python process after durable intent; never replay the effect."""

import subprocess
import sys

from inbox_reclaimer.gmail import FakeGmailAdapter
from inbox_reclaimer.models import Identity
from inbox_reclaimer.profile import ProfilePaths, account_lock
from inbox_reclaimer.sender.executor import SenderExecutor
from inbox_reclaimer.sender.journal import SenderJournal
from inbox_reclaimer.storage import JournalStore


def test_process_death_preserves_intent_and_releases_lock_without_replay(tmp_path):
    script = """
import os,sys
from pathlib import Path
from inbox_reclaimer.models import Identity,Message
from inbox_reclaimer.profile import ProfilePaths,account_lock
from inbox_reclaimer.sender.models import SenderPlan,Approval
from inbox_reclaimer.sender.journal import SenderJournal
from inbox_reclaimer.storage import JournalStore
p=ProfilePaths(Path(sys.argv[1])); p.initialize()
i=Identity('fixture@example.test','synthetic-client')
with account_lock(p,i.account_id), JournalStore(p.journal) as store:
    store.bind_account(i)
    journal=SenderJournal(store,clock=lambda:1000.0)
    plan=SenderPlan(i.account_id,'plan','sender@example.test',('id',),created_at=1000)
    journal.save_plan(plan)
    approval=journal.approve(plan,Approval(i.account_id,'plan',plan.digest,'trash','synthetic','event','challenge',1000,1900))
    journal.begin(plan,approval,'id','trash',Message('id','thread',1,100,frozenset({'INBOX'}),'sender@example.test'))
    os._exit(23)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 23, result.stderr
    paths = ProfilePaths(tmp_path)
    identity = Identity("fixture@example.test", "synthetic-client")
    with account_lock(paths, identity.account_id), JournalStore(paths.journal) as store:
        journal = SenderJournal(store, clock=lambda: 1000.0)
        assert journal.recover(identity.account_id) == 1
        operation = journal.operations(identity.account_id)[0]
        assert operation["state"] == "unknown"
        adapter = FakeGmailAdapter([], identity=identity)  # No mutation methods exist.
        executor = SenderExecutor(adapter, journal, clock=lambda: 1000.0)
        plan = journal.get_plan(identity.account_id, "plan")
        assert executor.execute(plan, operation["approval_id"], dry_run=False)["blocked"]
        assert journal.recover(identity.account_id) == 0
