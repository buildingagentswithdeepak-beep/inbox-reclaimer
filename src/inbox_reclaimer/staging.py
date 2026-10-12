"""Durable full-scan baselines. Cached metadata is never reused for history/safety reads."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import GateClosed, HistoryExpired, IdentityMismatch, Message, ReadFailure
from .storage import CacheStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS resume_scans (
 account_id TEXT PRIMARY KEY, generation TEXT NOT NULL, h0 TEXT NOT NULL, started_at TEXT,
 UNIQUE(account_id,generation));
CREATE TABLE IF NOT EXISTS resume_pages (
 account_id TEXT NOT NULL,generation TEXT NOT NULL,page_token TEXT NOT NULL,payload_json TEXT NOT NULL,
 PRIMARY KEY(account_id,generation,page_token),
 FOREIGN KEY(account_id,generation) REFERENCES resume_scans(account_id,generation) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS resume_metadata (
 account_id TEXT NOT NULL,generation TEXT NOT NULL,message_id TEXT NOT NULL,payload_json TEXT NOT NULL,
 PRIMARY KEY(account_id,generation,message_id),
 FOREIGN KEY(account_id,generation) REFERENCES resume_scans(account_id,generation) ON DELETE CASCADE);
"""


class ResumableReadAdapter:
    def __init__(self, adapter, cache_path: Path, redact_subjects: bool = False):
        self.adapter = adapter
        self.identity = adapter.resolve_identity()
        self.redact_subjects = redact_subjects
        self._active = False
        self._replaying = False
        self._generation = None
        self._closed = False
        self.scan_started_at = None
        # Own only a new connection; establish the actual cache migration first.
        with CacheStore(cache_path):
            pass
        self.conn = sqlite3.connect(cache_path, timeout=30)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.executescript(_SCHEMA)
        if "started_at" not in {r[1] for r in self.conn.execute("PRAGMA table_info(resume_scans)")}:
            self.conn.execute("ALTER TABLE resume_scans ADD COLUMN started_at TEXT")
            self.conn.commit()

    def close(self):
        if not self._closed:
            self.conn.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def resolve_identity(self):
        actual = self.adapter.resolve_identity()
        if actual != self.identity:
            raise IdentityMismatch("Account changed while reading a resumable inventory")
        return actual

    def validate_capability(self, action):
        if action not in {"read", "analyze", "propose"}:
            raise GateClosed("Only read operations are available in Gate A")
        self.adapter.validate_capability(action)
        self.resolve_identity()

    def _clean(self, message):
        if self.redact_subjects:
            return replace(
                message,
                subject=None,
                headers={k: v for k, v in message.headers.items() if k.lower() != "subject"},
            )
        return replace(message, headers=dict(message.headers))

    def has_pending_scan(self):
        self.resolve_identity()
        return (
            self.conn.execute(
                "SELECT 1 FROM resume_scans WHERE account_id=?", (self.identity.account_id,)
            ).fetchone()
            is not None
        )

    def history_boundary(self):
        self.resolve_identity()
        row = self.conn.execute(
            "SELECT generation,h0,started_at FROM resume_scans WHERE account_id=?",
            (self.identity.account_id,),
        ).fetchone()
        if row is None:
            h0 = self.adapter.history_boundary()
            self.resolve_identity()
            if not isinstance(h0, str) or not h0:
                raise ReadFailure("Cannot stage a scan without a history boundary")
            with self.conn:
                self.conn.execute(
                    "INSERT OR IGNORE INTO resume_scans VALUES (?,?,?,?)",
                    (self.identity.account_id, uuid4().hex, h0, datetime.now(timezone.utc).isoformat()),
                )
            row = self.conn.execute(
                "SELECT generation,h0,started_at FROM resume_scans WHERE account_id=?",
                (self.identity.account_id,),
            ).fetchone()
        self._generation, h0, self.scan_started_at = row
        self._active, self._replaying = True, False
        return h0

    def list_message_ids(self, page_token=None):
        self.resolve_identity()
        if not self._active:
            raise ReadFailure("Capture a history boundary before enumeration")
        key = (self.identity.account_id, self._generation, page_token or "")
        row = self.conn.execute(
            "SELECT payload_json FROM resume_pages WHERE account_id=? AND generation=? AND page_token=?", key
        ).fetchone()
        if row:
            return json.loads(row[0])
        result = self.adapter.list_message_ids(page_token=page_token)
        self.resolve_identity()
        with self.conn:
            self.conn.execute(
                "INSERT INTO resume_pages VALUES (?,?,?,?)", (*key, json.dumps(result, ensure_ascii=True))
            )
        return result

    def get_metadata(self, message_id):
        self.resolve_identity()
        key = (self.identity.account_id, self._generation, message_id)
        cacheable = self._active and not self._replaying
        if cacheable:
            row = self.conn.execute(
                "SELECT payload_json FROM resume_metadata WHERE account_id=? AND generation=? "
                "AND message_id=?",
                key,
            ).fetchone()
            if row:
                values = json.loads(row[0])
                values["labels"] = frozenset(values["labels"])
                return self._clean(Message(**values))
        message = self.adapter.get_metadata(message_id)
        self.resolve_identity()
        if not isinstance(message, Message) or message.id != message_id:
            raise ReadFailure("Invalid staged metadata identity")
        message = self._clean(message)
        if cacheable:
            values = asdict(message)
            values["labels"] = sorted(message.labels)
            with self.conn:
                self.conn.execute(
                    "INSERT INTO resume_metadata VALUES (?,?,?,?)",
                    (*key, json.dumps(values, ensure_ascii=True)),
                )
        return message

    def get_thread(self, thread_id):
        self.resolve_identity()
        result = self.adapter.get_thread(thread_id)
        self.resolve_identity()
        return result

    def read_history(self, start_history_id, page_token=None):
        self.resolve_identity()
        self._replaying = True
        try:
            result = self.adapter.read_history(start_history_id, page_token=page_token)
            self.resolve_identity()
            return result
        except HistoryExpired:
            self.discard_stage()
            raise

    def complete_scan(self):
        """Controller calls only after successful atomic cache publication."""
        self.resolve_identity()
        if self._active:
            self.discard_stage()

    def discard_stage(self):
        self.resolve_identity()
        with self.conn:
            self.conn.execute("DELETE FROM resume_scans WHERE account_id=?", (self.identity.account_id,))
        self._active, self._replaying, self._generation = False, False, None
