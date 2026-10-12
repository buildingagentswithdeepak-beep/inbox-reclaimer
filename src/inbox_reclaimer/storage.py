"""Separate rebuildable metadata and durable, account-bound Gate A journals.

The journal has no approval or mutation API. SQLite schema migrations deliberately
block those inserts until an independently verified future release replaces them.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import portalocker

from .models import Batch, GateClosed, IdentityMismatch, Inventory, Message, Plan, canonical_digest


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _now():
    return datetime.now(timezone.utc).isoformat()


def membership_digest(account_id, plan_id, revision, action, policy_version, ids):
    """Canonical persisted membership; a digest is never approval evidence."""
    return canonical_digest(
        {
            "account_id": account_id,
            "plan_id": plan_id,
            "revision": revision,
            "action": action,
            "policy_version": policy_version,
            "ids": sorted(set(ids)),
        }
    )


_CACHE_SCHEMA = """
CREATE TABLE generations (
 account_id TEXT NOT NULL,generation TEXT NOT NULL,cursor TEXT NOT NULL,
 started_at TEXT NOT NULL,completed_at TEXT NOT NULL,complete INTEGER NOT NULL,
 unresolved_json TEXT NOT NULL,PRIMARY KEY(account_id,generation));
CREATE TABLE active_inventory (
 account_id TEXT PRIMARY KEY,generation TEXT NOT NULL,
 FOREIGN KEY(account_id,generation) REFERENCES generations(account_id,generation));
CREATE TABLE messages (
 account_id TEXT NOT NULL,generation TEXT NOT NULL,message_id TEXT NOT NULL,
 thread_id TEXT NOT NULL,internal_date INTEGER,size_estimate INTEGER,raw_from TEXT NOT NULL,
 sender_address TEXT,subject TEXT,headers_json TEXT NOT NULL,valid INTEGER NOT NULL,
 PRIMARY KEY(account_id,generation,message_id),
 FOREIGN KEY(account_id,generation) REFERENCES generations(account_id,generation) ON DELETE CASCADE);
CREATE TABLE message_labels (
 account_id TEXT NOT NULL,generation TEXT NOT NULL,message_id TEXT NOT NULL,label TEXT NOT NULL,
 PRIMARY KEY(account_id,generation,message_id,label),
 FOREIGN KEY(account_id,generation,message_id) REFERENCES messages(account_id,generation,message_id)
 ON DELETE CASCADE);
CREATE INDEX cache_sender ON messages(account_id,generation,sender_address);
CREATE INDEX cache_size ON messages(account_id,generation,size_estimate);
CREATE INDEX cache_date ON messages(account_id,generation,internal_date);
CREATE INDEX cache_thread ON messages(account_id,generation,thread_id);
CREATE INDEX cache_labels ON message_labels(account_id,generation,label,message_id);
CREATE TABLE thread_observations (
 account_id TEXT NOT NULL,thread_id TEXT NOT NULL,observation_json TEXT NOT NULL,
 PRIMARY KEY(account_id,thread_id));
"""


class _Store:
    application_id = 0
    schema = ""

    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA foreign_keys=ON")
            app_id = self.conn.execute("PRAGMA application_id").fetchone()[0]
            version = self.conn.execute("PRAGMA user_version").fetchone()[0]
            tables = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if app_id not in (0, self.application_id) or version > 1 or (app_id == 0 and tables):
                raise ValueError("Unrecognized database; refusing to reset or migrate it")
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=FULL")
            if version == 0:
                self.conn.executescript(
                    "BEGIN IMMEDIATE;\n" + self.schema + f"\nPRAGMA application_id={self.application_id};"
                    "\nPRAGMA user_version=1;\nCOMMIT;"
                )
            if self.conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity check failed")
            if self.conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Database foreign key integrity check failed")
        except BaseException:
            self.conn.close()
            raise

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class CacheStore(_Store):
    application_id = 1229996867
    schema = _CACHE_SCHEMA

    def _insert_generation(self, inv):
        from .analytics import parse_sender
        from .models import LimitedInventory

        if isinstance(inv, LimitedInventory):
            raise ValueError("Limited preview cannot be published or staged as a full inventory")
        if not inv.account_id or not inv.generation or not inv.cursor:
            raise ValueError("Inventory requires account, generation and cursor")
        self.conn.execute(
            "INSERT INTO generations VALUES (?,?,?,?,?,?,?)",
            (
                inv.account_id,
                inv.generation,
                inv.cursor,
                inv.started_at,
                inv.completed_at,
                int(inv.complete),
                _json(inv.unresolved),
            ),
        )
        for m in inv.messages:
            self.conn.execute(
                "INSERT INTO messages (account_id,generation,message_id,thread_id,"
                "internal_date,size_estimate,raw_from,sender_address,subject,headers_json,valid) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    inv.account_id,
                    inv.generation,
                    m.id,
                    m.thread_id,
                    m.internal_date,
                    m.size_estimate,
                    m.raw_from,
                    parse_sender(m.raw_from),
                    m.subject,
                    _json(m.headers),
                    int(m.valid),
                ),
            )
            self.conn.executemany(
                "INSERT INTO message_labels VALUES (?,?,?,?)",
                [(inv.account_id, inv.generation, m.id, label) for label in sorted(m.labels)],
            )

    def _activate(self, account_id, generation):
        self.conn.execute(
            "INSERT INTO active_inventory VALUES (?,?) ON CONFLICT(account_id) "
            "DO UPDATE SET generation=excluded.generation",
            (account_id, generation),
        )
        # Conservative whole-account invalidation participates in cursor publication.
        self.conn.execute("DELETE FROM thread_observations WHERE account_id=?", (account_id,))

    def publish(self, inv):
        """Atomic generation and cursor publication; duplicate generations fail, never overwrite."""
        with self.conn:
            self._insert_generation(inv)
            self._activate(inv.account_id, inv.generation)

    def stage(self, inv):
        """Optional sync extension: persist a generation without changing the active cursor."""
        with self.conn:
            self._insert_generation(inv)

    def publish_staged(self, account_id, generation):
        with self.conn:
            self._activate(account_id, generation)

    def discard_stage(self, account_id, generation):
        with self.conn:
            self.conn.execute(
                "DELETE FROM generations WHERE account_id=? AND generation=?", (account_id, generation)
            )

    def load(self, account_id):
        # One read transaction prevents mixing generations across concurrent publication.
        with self.conn:
            self.conn.execute("BEGIN")
            row = self.conn.execute(
                "SELECT g.* FROM generations g JOIN active_inventory a "
                "USING(account_id,generation) WHERE account_id=?",
                (account_id,),
            ).fetchone()
            if row is None:
                return None
            key = (account_id, row["generation"])
            labels = {}
            for r in self.conn.execute(
                "SELECT message_id,label FROM message_labels WHERE account_id=? AND generation=?", key
            ):
                labels.setdefault(r["message_id"], set()).add(r["label"])
            messages = tuple(
                Message(
                    r["message_id"],
                    r["thread_id"],
                    r["internal_date"],
                    r["size_estimate"],
                    frozenset(labels.get(r["message_id"], ())),
                    r["raw_from"],
                    r["subject"],
                    json.loads(r["headers_json"]),
                    bool(r["valid"]),
                )
                for r in self.conn.execute(
                    "SELECT * FROM messages WHERE account_id=? AND generation=? ORDER BY message_id", key
                )
            )
            return Inventory(
                account_id,
                row["generation"],
                row["cursor"],
                row["started_at"],
                row["completed_at"],
                bool(row["complete"]),
                tuple(json.loads(row["unresolved_json"])),
                messages,
            )

    def invalidate_thread(self, account_id, thread_id=None):
        with self.conn:
            if thread_id is None:
                self.conn.execute("DELETE FROM thread_observations WHERE account_id=?", (account_id,))
            else:
                self.conn.execute(
                    "DELETE FROM thread_observations WHERE account_id=? AND thread_id=?",
                    (account_id, thread_id),
                )

    def rebuild(self, account_id):
        with self.conn:
            self.conn.execute("DELETE FROM active_inventory WHERE account_id=?", (account_id,))
            self.conn.execute("DELETE FROM generations WHERE account_id=?", (account_id,))
            self.conn.execute("DELETE FROM thread_observations WHERE account_id=?", (account_id,))


def _journal_schema():
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    for table in ("batches", "batch_members"):
        for action in ("INSERT", "UPDATE", "DELETE"):
            refs = ["NEW"] if action == "INSERT" else ["OLD"] if action == "DELETE" else ["OLD", "NEW"]
            condition = " OR ".join(
                f"EXISTS(SELECT 1 FROM plans WHERE account_id={ref}.account_id "
                f"AND plan_id={ref}.plan_id AND revision={ref}.revision AND status!='draft')"
                for ref in refs
            )
            schema += (
                f"\nCREATE TRIGGER immutable_{table}_{action} BEFORE {action} ON {table} "
                f"WHEN {condition} BEGIN SELECT RAISE(ABORT,'sealed membership immutable'); END;"
            )
    return schema


class JournalStore(_Store):
    application_id = 1229996874
    schema = _journal_schema()

    def _event(self, account_id, event_type, payload):
        self.conn.execute(
            "INSERT INTO journal_events(account_id,event_type,payload_json,created_at) VALUES (?,?,?,?)",
            (account_id, event_type, _json(payload), _now()),
        )

    def _require_account(self, account_id):
        row = self.conn.execute("SELECT account_id FROM accounts").fetchone()
        if row is None or row[0] != account_id:
            raise IdentityMismatch("Journal is not bound to this account")

    def bind_account(self, identity):
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute("SELECT * FROM accounts").fetchone()
            if row:
                if tuple(row) != (
                    identity.account_id,
                    identity.email,
                    identity.oauth_client_id,
                    identity.subject,
                ):
                    raise IdentityMismatch("Persisted account differs; automatic migration is forbidden")
                return
            self.conn.execute(
                "INSERT INTO accounts VALUES (?,?,?,?)",
                (identity.account_id, identity.email, identity.oauth_client_id, identity.subject),
            )
            self._event(identity.account_id, "account_bound", {})

    def protect_sender(self, account_id, address, reason=""):
        from .analytics import parse_sender

        parsed = parse_sender(address)
        if not parsed:
            raise ValueError("A valid sender address is required")
        with self.conn:
            self._require_account(account_id)
            self.conn.execute(
                "INSERT INTO sender_protections VALUES (?,?,?,?) "
                "ON CONFLICT(account_id,sender_address) DO UPDATE SET reason=excluded.reason",
                (account_id, parsed, reason, _now()),
            )
            self._event(account_id, "sender_protected", {"sender_address": parsed})

    def protections(self, account_id):
        self._require_account(account_id)
        return {
            r[0]
            for r in self.conn.execute(
                "SELECT sender_address FROM sender_protections WHERE account_id=?", (account_id,)
            )
        }

    def save_plan(self, plan):
        if plan.action != "trash":
            raise GateClosed("Gate A only creates trash proposals, never approvals")
        if plan.status != "sealed" or plan.revision < 1:
            raise ValueError("Only a sealed positive plan revision can be saved")
        all_ids = []
        for b in plan.batches:
            if not b.ids or tuple(sorted(set(b.ids))) != b.ids:
                raise ValueError("Batch membership must be sorted, unique and nonempty")
            if set(b.reasons) - set(b.ids):
                raise ValueError("Reason tags must refer only to batch members")
            if b.digest != membership_digest(
                plan.account_id, plan.plan_id, plan.revision, plan.action, plan.policy_version, b.ids
            ):
                raise ValueError("Membership digest mismatch")
            all_ids.extend(b.ids)
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Each message must have exactly one owning batch")
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            self._require_account(plan.account_id)
            key = (plan.account_id, plan.plan_id, plan.revision)
            self.conn.execute(
                "INSERT INTO plans (account_id,plan_id,revision,action,policy_version,"
                "inventory_generation,created_at,status) VALUES (?,?,?,?,?,?,?,?)",
                (*key, plan.action, plan.policy_version, plan.inventory_generation, plan.created_at, "draft"),
            )
            for b in plan.batches:
                self.conn.execute(
                    "INSERT INTO batches VALUES (?,?,?,?,?,?,?,?)",
                    (*key, b.batch_id, b.kind, b.digest, len(b.ids), b.estimated_bytes),
                )
                self.conn.executemany(
                    "INSERT INTO batch_members VALUES (?,?,?,?,?,?,?)",
                    [(*key, b.batch_id, i, None, _json(b.reasons.get(i, []))) for i in b.ids],
                )
            self.conn.execute(
                "UPDATE plans SET status='sealed' WHERE account_id=? AND plan_id=? AND revision=?", key
            )
            self._event(
                plan.account_id,
                "plan_sealed",
                {
                    "plan_id": plan.plan_id,
                    "revision": plan.revision,
                    "action": plan.action,
                    "message_count": len(all_ids),
                },
            )

    def get_plan(self, account_id, plan_id, revision=1):
        self._require_account(account_id)
        key = (account_id, plan_id, revision)
        p = self.conn.execute(
            "SELECT * FROM plans WHERE account_id=? AND plan_id=? AND revision=?", key
        ).fetchone()
        if p is None:
            raise KeyError("Plan revision not found")
        batches = []
        for b in self.conn.execute(
            "SELECT * FROM batches WHERE account_id=? AND plan_id=? AND revision=? ORDER BY rowid", key
        ):
            members = self.conn.execute(
                "SELECT message_id,reasons_json FROM batch_members WHERE account_id=? "
                "AND plan_id=? AND revision=? AND batch_id=? ORDER BY message_id",
                (*key, b["batch_id"]),
            ).fetchall()
            ids = tuple(r["message_id"] for r in members)
            digest = membership_digest(account_id, plan_id, revision, p["action"], p["policy_version"], ids)
            if digest != b["membership_digest"] or len(ids) != b["message_count"]:
                raise ValueError("Stored plan membership integrity failure")
            batches.append(
                Batch(
                    b["batch_id"],
                    b["kind"],
                    ids,
                    b["estimated_bytes"],
                    digest,
                    {r["message_id"]: json.loads(r["reasons_json"]) for r in members},
                )
            )
        return Plan(
            account_id,
            plan_id,
            revision,
            p["action"],
            p["policy_version"],
            p["inventory_generation"],
            p["created_at"],
            tuple(batches),
            p["status"],
        )

    def plans(self, account_id):
        self._require_account(account_id)
        return [
            self.get_plan(account_id, r["plan_id"], r["revision"])
            for r in self.conn.execute(
                "SELECT plan_id,revision FROM plans WHERE account_id=? ORDER BY created_at,plan_id,revision",
                (account_id,),
            ).fetchall()
        ]

    def list_batch(self, account_id, plan_id, revision, batch_id, page=1, page_size=50):
        if type(page) is not int or type(page_size) is not int or page < 1 or not 1 <= page_size <= 1000:
            raise ValueError("Invalid pagination (page >= 1, page_size 1..1000)")
        self._require_account(account_id)
        key = (account_id, plan_id, revision, batch_id)
        b = self.conn.execute(
            "SELECT message_count FROM batches WHERE account_id=? AND plan_id=? "
            "AND revision=? AND batch_id=?",
            key,
        ).fetchone()
        if b is None:
            raise KeyError("Batch not found")
        ids = [
            r[0]
            for r in self.conn.execute(
                "SELECT message_id FROM batch_members WHERE account_id=? "
                "AND plan_id=? AND revision=? AND batch_id=? "
                "ORDER BY message_id LIMIT ? OFFSET ?",
                (*key, page_size, (page - 1) * page_size),
            )
        ]
        return {"ids": ids, "total": b[0], "page": page}

    def reject_batch(self, account_id, plan_id, revision, batch_id):
        with self.conn:
            self._require_account(account_id)
            result = self.conn.execute(
                "INSERT INTO batch_rejections VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                (account_id, plan_id, revision, batch_id, _now()),
            )
            if result.rowcount:
                self._event(
                    account_id,
                    "batch_rejected",
                    {"plan_id": plan_id, "revision": revision, "batch_id": batch_id},
                )

    def status(self, account_id):
        self._require_account(account_id)
        result = {"account_id": account_id, "gate": "A", "mutations_enabled": False}
        for key, table in [
            ("plans", "plans"),
            ("batches", "batches"),
            ("rejected_batches", "batch_rejections"),
            ("protections", "sender_protections"),
            ("approvals", "approvals"),
            ("operations", "operations"),
            ("events", "journal_events"),
        ]:
            result[key] = self.conn.execute(
                f"SELECT count(*) FROM {table} WHERE account_id=?", (account_id,)
            ).fetchone()[0]
        return result

    def _safe_output(self, output):
        path = Path(output).expanduser().resolve()
        reserved = {
            self.path,
            self.path.with_name("cache.db"),
            self.path.with_name("checkpoints.db"),
            self.path.parent.parent / "google_token.json",
            self.path.parent.parent / "google_client_secret.json",
        }
        if any(path == Path(str(item) + suffix) for item in reserved for suffix in ("", "-wal", "-shm")):
            raise ValueError("Output cannot overwrite application databases or credentials")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def export_audit(self, output):
        """Validate the complete prefix; repair only a torn final line and replay from SQLite.

        The file, not an optimistic export cursor, determines replay. A crash after
        fsync but before cursor commit therefore cannot duplicate an event.
        """
        path = self._safe_output(output)
        with portalocker.Lock(str(path) + ".lock", timeout=30):
            rows = self.conn.execute("SELECT * FROM journal_events ORDER BY event_id").fetchall()
            records = [
                {
                    "event_id": r["event_id"],
                    "account_id": r["account_id"],
                    "operation_id": r["operation_id"],
                    "event_type": r["event_type"],
                    "payload": json.loads(r["payload_json"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
            expected = [(_json(r) + "\n").encode("utf-8") for r in records]
            with path.open("a+b") as f:
                from .profile import make_private

                make_private(path)
                f.seek(0)
                count = 0
                good_end = 0
                for line in f:
                    if not line.endswith(b"\n"):
                        break
                    if count >= len(expected) or line != expected[count]:
                        raise ValueError("Audit export is not an exact journal prefix; refusing to overwrite")
                    count += 1
                    good_end += len(line)
                f.seek(good_end)
                f.truncate()
                for line in expected[count:]:
                    f.write(line)
                f.flush()
                os.fsync(f.fileno())
            last = records[-1]["event_id"] if records else 0
            with self.conn:
                self.conn.execute(
                    "INSERT INTO export_cursors VALUES (?,?) ON CONFLICT(export_name) "
                    "DO UPDATE SET last_event_id=excluded.last_event_id",
                    (str(path), last),
                )
            return {"exported": len(expected) - count, "last_event_id": last, "output": str(path)}

    def backup(self, output):
        path = self._safe_output(output)
        # Never silently replace another database or backup.
        with path.open("xb"):
            from .profile import make_private

            make_private(path)
        destination = sqlite3.connect(path)
        try:
            self.conn.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed")
        finally:
            destination.close()
