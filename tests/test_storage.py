import json
import sqlite3
from dataclasses import replace

import pytest

from inbox_reclaimer.models import Batch, Identity, IdentityMismatch, Inventory, Message, Plan
from inbox_reclaimer.storage import CacheStore, JournalStore, membership_digest


@pytest.fixture
def identity():
    return Identity("owner@example.test", "client")


def inventory(identity, generation="g1", cursor="opaque:1"):
    return Inventory(
        identity.account_id,
        generation,
        cursor,
        "start",
        "end",
        True,
        (),
        (Message("m1", "t1", 1, 200, frozenset({"INBOX"}), "a@example.test", "PRIVATE"),),
    )


def plan(identity, ids=("m1", "m2")):
    digest = membership_digest(identity.account_id, "p1", 1, "trash", "v1", ids)
    return Plan(
        identity.account_id,
        "p1",
        1,
        "trash",
        "v1",
        "g1",
        "now",
        (Batch("b1", "SIZE_AGE", ids, 400, digest, {i: ["r1"] for i in ids}),),
    )


def test_cache_atomic_publication_and_account_isolation(tmp_path, identity):
    c = CacheStore(tmp_path / "cache.db")
    old = inventory(identity)
    c.publish(old)
    broken = replace(old, generation="g2", cursor="new", messages=old.messages * 2)
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        c.publish(broken)
    assert c.load(identity.account_id) == old
    assert c.load("other") is None
    c.close()
    c = CacheStore(tmp_path / "cache.db")
    assert c.load(identity.account_id).cursor == "opaque:1"
    c.close()


def test_rebuild_does_not_touch_journal(tmp_path, identity):
    c = CacheStore(tmp_path / "cache.db")
    j = JournalStore(tmp_path / "journal.db")
    j.bind_account(identity)
    j.save_plan(plan(identity))
    c.publish(inventory(identity))
    c.rebuild(identity.account_id)
    assert c.load(identity.account_id) is None
    assert j.get_plan(identity.account_id, "p1") == plan(identity)
    c.close()
    j.close()


def test_persisted_account_switch_fails(tmp_path, identity):
    path = tmp_path / "journal.db"
    j = JournalStore(path)
    j.bind_account(identity)
    j.close()
    j = JournalStore(path)
    j.bind_account(identity)
    with pytest.raises(IdentityMismatch):
        j.bind_account(Identity("other@example.test", "client"))
    j.close()


def test_plan_immutable_digests_and_pagination(tmp_path, identity):
    j = JournalStore(tmp_path / "journal.db")
    j.bind_account(identity)
    p = plan(identity)
    j.save_plan(p)
    assert j.get_plan(identity.account_id, "p1") == p
    assert j.list_batch(identity.account_id, "p1", 1, "b1", page=2, page_size=1)["ids"] == ["m2"]
    with pytest.raises(ValueError):
        j.save_plan(replace(p, plan_id="bad"))
    for sql in [
        "UPDATE batch_members SET message_id='changed'",
        "DELETE FROM batch_members",
        "UPDATE batches SET estimated_bytes=0",
        "UPDATE plans SET action='restore'",
        "UPDATE plans SET status='draft'",
        "DELETE FROM plans",
        "INSERT INTO batch_members VALUES (?, 'p1', 1, 'b1', 'new', NULL, '[]')",
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            with j.conn:
                j.conn.execute(sql, (identity.account_id,) if "?" in sql else ())
    j.reject_batch(identity.account_id, "p1", 1, "b1")
    j.reject_batch(identity.account_id, "p1", 1, "b1")
    assert j.get_plan(identity.account_id, "p1") == p
    assert j.status(identity.account_id)["rejected_batches"] == 1
    assert j.conn.execute("SELECT count(*) FROM approvals").fetchone()[0] == 0
    j.close()


def test_audit_idempotent_partial_line_and_backup(tmp_path, identity):
    j = JournalStore(tmp_path / "journal.db")
    j.bind_account(identity)
    j.protect_sender(identity.account_id, "a@example.test", "keep")
    j.save_plan(plan(identity))
    out = tmp_path / "audit.jsonl"
    first = j.export_audit(out)
    before = out.read_bytes()
    assert first["exported"] > 0
    assert j.export_audit(out)["exported"] == 0
    assert out.read_bytes() == before
    with out.open("ab") as f:
        f.write(b'{"event_id":')
    assert j.export_audit(out)["exported"] == 0
    assert out.read_bytes() == before
    rows = [json.loads(line) for line in before.splitlines()]
    assert len({r["event_id"] for r in rows}) == len(rows)
    assert "PRIVATE" not in before.decode()
    j.backup(tmp_path / "backup.db")
    restored = JournalStore(tmp_path / "backup.db")
    assert restored.get_plan(identity.account_id, "p1") == plan(identity)
    assert restored.protections(identity.account_id) == {"a@example.test"}
    restored.close()
    j.close()
