"""Durable scan baselines must never become cached safety observations."""

from dataclasses import replace
import sqlite3

import pytest

from inbox_reclaimer.gmail import FakeGmailAdapter
from inbox_reclaimer.models import (
    GateClosed,
    HistoryExpired,
    Identity,
    IdentityMismatch,
    Message,
    MissingMessage,
    ReadFailure,
)
from inbox_reclaimer.staging import ResumableReadAdapter
from inbox_reclaimer.storage import CacheStore
from inbox_reclaimer.sync import SyncCancelled, SyncService


def message(id="a", subject="private subject"):
    return Message(
        id,
        "t" + id,
        1000,
        50,
        frozenset(),
        "sender@example.com",
        subject,
        {"sUbJeCt": subject, "From": "sender@example.com"},
    )


def history(affected=(), deleted=(), token=None, cursor="H1"):
    return dict(
        affected_ids=list(affected),
        deleted_ids=list(deleted),
        thread_ids=[],
        unknown_threads=False,
        next_page_token=token,
        history_id=cursor,
    )


class Reader(FakeGmailAdapter):
    def __init__(self, identity=None):
        super().__init__([message("a"), message("b"), message("c")], identity, page_size=2)
        self.calls = []
        self.boundary = "H0"
        self.history_pages = {None: history()}
        self.failure = None
        self.closed = False

    def history_boundary(self):
        self.calls.append(("boundary",))
        return self.boundary

    def list_message_ids(self, page_token=None):
        self.calls.append(("list", page_token))
        return super().list_message_ids(page_token)

    def get_metadata(self, message_id):
        self.calls.append(("metadata", message_id))
        if self.failure == message_id:
            raise ReadFailure("interrupted")
        return super().get_metadata(message_id)

    def read_history(self, start_history_id, page_token=None):
        self.calls.append(("history", start_history_id, page_token))
        page = self.history_pages[page_token]
        if isinstance(page, Exception):
            raise page
        return page

    def close(self):
        self.closed = True

    def delete_messages(self, ids):
        raise AssertionError("must not expose write surface")


def stage_count(path):
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM resume_scans").fetchone()[0]


def test_interrupted_partial_page_resumes_saved_h0_pages_and_metadata(tmp_path):
    path = tmp_path / "cache.db"
    first = Reader()
    first.failure = "b"
    with CacheStore(path) as cache, ResumableReadAdapter(first, path) as wrapper:
        with pytest.raises(ReadFailure, match="interrupted"):
            SyncService(wrapper, cache).full_sync()
        assert cache.load(first.identity.account_id) is None
    second = Reader()
    second.boundary = "H-later"
    with CacheStore(path) as cache, ResumableReadAdapter(second, path) as wrapper:
        inv = SyncService(wrapper, cache).full_sync()
        assert inv.complete and len(inv.messages) == 3
        assert ("boundary",) not in second.calls
        assert ("list", None) not in second.calls
        assert ("metadata", "a") not in second.calls
        assert ("list", "2") in second.calls
        assert ("history", "H0", None) in second.calls
        assert stage_count(path) == 1  # Publication alone does not discard staging.
        wrapper.complete_scan()
        assert stage_count(path) == 0
        assert cache.load(inv.account_id) == inv


def test_replay_refresh_and_later_safety_reads_are_always_fresh(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    with ResumableReadAdapter(reader, path) as wrapper:
        assert wrapper.history_boundary() == "H0"
        old = wrapper.get_metadata("a")
        reader.messages["a"] = replace(old, labels=frozenset({"STARRED"}))
        wrapper.read_history("H0")
        assert wrapper.get_metadata("a").labels == {"STARRED"}
        reader.messages["a"] = replace(old, labels=frozenset({"SENT"}))
        assert wrapper.get_metadata("a").labels == {"SENT"}
        wrapper.complete_scan()
        assert wrapper.get_metadata("a").labels == {"SENT"}
        assert reader.calls.count(("metadata", "a")) == 4


def test_restart_during_history_replays_every_page_from_original_boundary(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    reader.history_pages = {None: history(["a"], token="p2"), "p2": ReadFailure("offline")}
    with CacheStore(path) as cache, ResumableReadAdapter(reader, path) as wrapper:
        with pytest.raises(ReadFailure):
            SyncService(wrapper, cache).full_sync()
    reader = Reader()
    reader.messages["a"] = replace(message("a"), labels=frozenset({"STARRED"}))
    reader.history_pages = {
        None: history(["a"], token="p2"),
        "p2": history(["b"], deleted=["c"], cursor="H2"),
    }
    with CacheStore(path) as cache, ResumableReadAdapter(reader, path) as wrapper:
        inv = SyncService(wrapper, cache).full_sync()
        assert inv.cursor == "H2"
        assert [m.id for m in inv.messages] == ["a", "b"]
        assert inv.messages[0].labels == {"STARRED"}
        assert reader.calls == [
            ("history", "H0", None),
            ("history", "H0", "p2"),
            ("metadata", "a"),
            ("metadata", "b"),
        ]


def test_expired_history_discards_all_stage_rows_and_restarts(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    with ResumableReadAdapter(reader, path) as wrapper:
        wrapper.history_boundary()
        wrapper.list_message_ids()
        wrapper.get_metadata("a")
        reader.history_pages[None] = HistoryExpired("expired")
        with pytest.raises(HistoryExpired):
            wrapper.read_history("H0")
        with sqlite3.connect(path) as conn:
            for table in ("resume_scans", "resume_pages", "resume_metadata"):
                assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        reader.boundary = "H-new"
        reader.history_pages[None] = history(cursor="H-final")
        with CacheStore(path) as cache:
            inv = SyncService(wrapper, cache).full_sync()
            assert inv.cursor == "H-final"
            assert ("history", "H-new", None) in reader.calls
            assert reader.calls.count(("metadata", "a")) == 2


def test_cancellation_and_failed_atomic_publish_keep_old_inventory_and_resume(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    with CacheStore(path) as cache:
        old = SyncService(reader, cache).full_sync()
        with ResumableReadAdapter(reader, path) as wrapper:
            events = []
            with pytest.raises(SyncCancelled):
                SyncService(
                    wrapper,
                    cache,
                    progress=events.append,
                    cancelled=lambda: any(e["phase"] == "metadata" for e in events),
                ).full_sync()
            assert cache.load(old.account_id) == old
        with ResumableReadAdapter(reader, path) as wrapper:
            cache.conn.execute(
                "CREATE TRIGGER fail_resume_publish BEFORE INSERT ON messages "
                "BEGIN SELECT RAISE(ABORT, 'disk full'); END"
            )
            with pytest.raises(sqlite3.IntegrityError, match="disk full"):
                SyncService(wrapper, cache).full_sync()
            assert cache.load(old.account_id) == old
            assert stage_count(path) == 1
            cache.conn.execute("DROP TRIGGER fail_resume_publish")
        with ResumableReadAdapter(reader, path) as wrapper:
            inv = SyncService(wrapper, cache).full_sync()
            wrapper.complete_scan()
            assert cache.load(old.account_id) == inv
            assert stage_count(path) == 0


def test_redaction_before_persistence_and_after_resume(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    with ResumableReadAdapter(reader, path, redact_subjects=True) as wrapper:
        wrapper.history_boundary()
        result = wrapper.get_metadata("a")
        assert result.subject is None and set(result.headers) == {"From"}
        with sqlite3.connect(path) as conn:
            assert "private subject" not in "\n".join(conn.iterdump())
        for file in tmp_path.glob("cache.db*"):
            assert b"private subject" not in file.read_bytes()
    with ResumableReadAdapter(reader, path, redact_subjects=True) as wrapper:
        wrapper.history_boundary()
        assert wrapper.get_metadata("a") == result
        assert reader.calls.count(("metadata", "a")) == 1
    assert reader.messages["a"].subject == "private subject"


def test_accounts_have_isolated_stages_and_scoped_discard(tmp_path):
    path = tmp_path / "cache.db"
    a, b = Reader(), Reader(Identity("other@example.com", "fake-client"))
    b.boundary = "other-H0"
    b.messages["a"] = message("a", "other subject")
    with ResumableReadAdapter(a, path) as wrapper:
        wrapper.history_boundary()
        wrapper.get_metadata("a")
    with ResumableReadAdapter(b, path) as wrapper:
        assert wrapper.history_boundary() == "other-H0"
        assert wrapper.get_metadata("a").subject == "other subject"
        assert stage_count(path) == 2
        wrapper.discard_stage()
        assert stage_count(path) == 1
    with ResumableReadAdapter(a, path) as wrapper:
        assert wrapper.history_boundary() == "H0"
        assert wrapper.get_metadata("a").subject == "private subject"
        wrapper.complete_scan()
    assert stage_count(path) == 0


def test_changed_identity_cannot_read_or_clear_bound_stage(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    with ResumableReadAdapter(reader, path) as wrapper:
        wrapper.history_boundary()
        wrapper.get_metadata("a")
        reader.identity = Identity("switched@example.com", "fake-client")
        for operation in (
            wrapper.resolve_identity,
            wrapper.history_boundary,
            lambda: wrapper.get_metadata("a"),
            wrapper.complete_scan,
            wrapper.discard_stage,
        ):
            with pytest.raises(IdentityMismatch):
                operation()
        assert stage_count(path) == 1


def test_identity_switch_during_network_read_never_persists_result(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    with ResumableReadAdapter(reader, path) as wrapper:
        wrapper.history_boundary()
        original = reader.get_metadata

        def switched(id):
            result = original(id)
            reader.identity = Identity("switched@example.com", "fake-client")
            return result

        reader.get_metadata = switched
        with pytest.raises(IdentityMismatch):
            wrapper.get_metadata("a")
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM resume_metadata").fetchone()[0] == 0


def test_bootstrap_coexists_with_cache_and_close_owns_only_its_connection(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    wrapper = ResumableReadAdapter(reader, path)
    wrapper.history_boundary()
    with CacheStore(path) as cache:
        wrapper.close()
        wrapper.close()
        assert cache.load(reader.identity.account_id) is None
    assert not reader.closed


def test_only_read_contract_exposed_and_thread_reads_never_cached(tmp_path):
    reader = Reader()
    with ResumableReadAdapter(reader, tmp_path / "cache.db") as wrapper:
        assert not hasattr(wrapper, "delete_messages")
        with pytest.raises(GateClosed):
            wrapper.validate_capability("delete")
        wrapper.validate_capability("analyze")
        assert wrapper.get_thread("ta")[0].labels == frozenset()
        reader.messages["a"] = replace(message("a"), labels=frozenset({"STARRED"}))
        assert wrapper.get_thread("ta")[0].labels == {"STARRED"}


def test_missing_and_failed_metadata_are_retryable_not_cached(tmp_path):
    reader = Reader()
    with ResumableReadAdapter(reader, tmp_path / "cache.db") as wrapper:
        wrapper.history_boundary()
        with pytest.raises(MissingMessage):
            wrapper.get_metadata("gone")
        reader.messages["gone"] = message("gone")
        assert wrapper.get_metadata("gone").id == "gone"


def test_no_network_inside_write_transaction_and_boundary_precedes_enumeration(tmp_path):
    path = tmp_path / "cache.db"
    reader = Reader()
    with ResumableReadAdapter(reader, path) as wrapper:
        original = reader.history_boundary

        def boundary():
            with sqlite3.connect(path, timeout=0) as conn:
                conn.execute("BEGIN IMMEDIATE")
            return original()

        reader.history_boundary = boundary
        wrapper.history_boundary()
        original_list = reader.list_message_ids

        def listing(page_token=None):
            with sqlite3.connect(path, timeout=0) as conn:
                conn.execute("BEGIN IMMEDIATE")
                assert conn.execute("SELECT h0 FROM resume_scans").fetchone()[0] == "H0"
            return original_list(page_token)

        reader.list_message_ids = listing
        wrapper.list_message_ids()
