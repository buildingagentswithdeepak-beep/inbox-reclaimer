"""Synthetic durable mailbox and journal fixture; never uses credentials or a network."""

from dataclasses import replace
import sqlite3
from uuid import uuid4

from inbox_reclaimer.gmail import FakeGmailAdapter
from inbox_reclaimer.models import Identity, Message
from inbox_reclaimer.profile import ProfilePaths
from inbox_reclaimer.sender.executor import SenderExecutor
from inbox_reclaimer.sender.journal import SenderJournal
from inbox_reclaimer.sender.models import Approval, SenderPlan
from inbox_reclaimer.sender.workflow import run_sender_workflow
from inbox_reclaimer.storage import JournalStore


class DurableMailbox(FakeGmailAdapter):
    def __init__(self, root, identity):
        self.db = sqlite3.connect(root / "synthetic-mailbox.db")
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS calls (id TEXT NOT NULL);"
            "CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, trashed INTEGER NOT NULL);"
            "INSERT OR IGNORE INTO messages VALUES ('private-a',0),('private-b',0);"
        )
        super().__init__(
            [
                Message(
                    i,
                    "thread-" + i,
                    1,
                    100,
                    frozenset({"TRASH"} if trashed else {"INBOX"}),
                    "news@example.test",
                    subject="PRIVATE SUBJECT",
                )
                for i, trashed in self.db.execute("SELECT id,trashed FROM messages ORDER BY id")
            ],
            identity=identity,
        )
        self.hook = lambda stage: None
        self.after_write = lambda: None

    @property
    def calls(self):
        return [row[0] for row in self.db.execute("SELECT id FROM calls ORDER BY rowid")]

    def validate_capability(self, action):
        assert action in {"trash", "restore"}
        return True

    def trash_ids(self, ids):
        assert len(ids) == 1
        self.hook("before_dispatch")
        i = ids[0]
        with self.db:
            self.db.execute("INSERT INTO calls VALUES (?)", (i,))
            self.db.execute("UPDATE messages SET trashed=1 WHERE id=?", (i,))
        self.messages[i] = replace(self.messages[i], labels=frozenset({"TRASH"}))
        self.hook("after_dispatch")
        self.after_write()
        return {}


class GraphEnvironment:
    def __init__(self, root):
        self.paths = ProfilePaths(root)
        self.paths.initialize()
        self.identity = Identity("owner@example.test", "synthetic-client")
        self.clock = [1000.0]
        self.store = JournalStore(self.paths.journal)
        self.store.bind_account(self.identity)
        self.journal = SenderJournal(self.store, clock=lambda: self.clock[0])
        self.mailbox = DurableMailbox(root, self.identity)
        self.executor = SenderExecutor(self.mailbox, self.journal, clock=lambda: self.clock[0])
        self.plan = SenderPlan(
            self.identity.account_id,
            "plan",
            "news@example.test",
            ("private-a", "private-b"),
            created_at=1000,
        )
        self.journal.save_plan(self.plan)

    def approve(self, plan=None):
        plan = plan or self.plan
        return self.journal.approve(
            plan,
            Approval(
                plan.account_id,
                plan.plan_id,
                plan.digest,
                plan.action,
                "human:synthetic",
                uuid4().hex,
                uuid4().hex,
                self.clock[0],
                self.clock[0] + 100,
            ),
        )

    def run(self, approval=None, *, decision=None, writer=True):
        return run_sender_workflow(
            self.paths,
            self.identity,
            self.journal,
            self.executor if writer else None,
            self.plan,
            approval,
            decision=decision,
        )

    def close(self):
        self.mailbox.db.close()
        self.store.close()
