from dataclasses import replace
import pytest
from inbox_reclaimer.gmail import FakeGmailAdapter
from inbox_reclaimer.sync import SyncService, SyncCancelled
from inbox_reclaimer.models import Identity, Message, HistoryExpired, IdentityMismatch, ReadFailure


def msg(id, thread=None, **kwargs):
    return Message(
        id,
        thread or "t" + id,
        1000,
        50,
        frozenset(),
        "a@example.com",
        subject="private subject",
        headers={"Subject": "private subject"},
        **kwargs,
    )


class Cache:
    def __init__(self):
        self.current = None
        self.invalidations = []
        self.publications = []

    def load(self, account):
        return self.current if self.current and self.current.account_id == account else None

    def publish(self, inventory):
        self.current = inventory
        self.publications.append(inventory)

    def invalidate_thread(self, account, thread_id=None):
        self.invalidations.append((account, thread_id))


def history(affected=(), deleted=(), threads=(), unknown=False, next=None, cursor="end"):
    return dict(
        affected_ids=list(affected),
        deleted_ids=list(deleted),
        thread_ids=list(threads),
        unknown_threads=unknown,
        next_page_token=next,
        history_id=cursor,
    )


def test_full_scan_boundary_before_enumeration_and_all_page_replay():
    class Racing(FakeGmailAdapter):
        def __init__(self):
            super().__init__([msg("a"), msg("b"), msg("c")], page_size=1)
            self.calls = []

        def history_boundary(self):
            self.calls.append("boundary")
            return "opaque-start"

        def list_message_ids(self, page_token=None):
            self.calls.append("list")
            return super().list_message_ids(page_token)

        def read_history(self, start_history_id, page_token=None):
            assert start_history_id == "opaque-start"
            self.calls.append("history")
            if page_token is None:
                self.messages["d"] = msg("d")
                self.messages["b"] = replace(msg("b"), labels=frozenset({"SENT"}))
                return history(["b", "b", "d"], threads=["tb", "td"], next="p2", cursor="not-final")
            self.messages.pop("c")
            return history(["b"], ["c"], ["tc"], cursor="opaque-final")

        def get_metadata(self, id):
            self.calls.append("get:" + id)
            return super().get_metadata(id)

    a, cache = Racing(), Cache()
    inv = SyncService(a, cache).full_sync()
    assert a.calls.index("boundary") < a.calls.index("list")
    assert a.calls.count("list") == 3
    assert a.calls.count("history") == 2
    assert a.calls.count("get:b") == 2
    assert {m.id for m in inv.messages} == {"a", "b", "d"}
    assert inv.cursor == "opaque-final" and inv.complete
    assert next(m for m in inv.messages if m.id == "b").labels == {"SENT"}
    assert {(inv.account_id, t) for t in ["tb", "tc", "td"]} <= set(cache.invalidations)
    assert len(cache.publications) == 1


def test_incremental_missing_thread_invalidation_and_redaction_of_existing_rows():
    a, cache = FakeGmailAdapter([msg("a"), msg("b")]), Cache()
    SyncService(a, cache).full_sync()
    a.read_history = lambda *args, **kw: history(["a"], ["b"], unknown=True, cursor="new")
    inv = SyncService(a, cache, redact_subjects=True).incremental_sync()
    assert inv.cursor == "new" and [m.id for m in inv.messages] == ["a"]
    assert inv.messages[0].subject is None
    assert not any(k.lower() == "subject" for k in inv.messages[0].headers)
    assert (inv.account_id, None) in cache.invalidations


def test_crash_preserves_previous_generation_and_cursor():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()
    old = SyncService(a, cache).full_sync()

    def fail(start, page_token=None):
        if page_token is None:
            return history(["a"], next="second", cursor="wrong-advanced")
        raise ReadFailure("offline")

    a.read_history = fail
    with pytest.raises(ReadFailure):
        SyncService(a, cache).incremental_sync()
    assert cache.current is old and len(cache.publications) == 1


def test_expired_history_restarts_full_scan_bounded():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()
    original = a.read_history
    calls = []

    def once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise HistoryExpired("expired")
        return original(*args, **kwargs)

    a.read_history = once
    assert SyncService(a, cache).full_sync().complete
    assert len(calls) == 2 and len(cache.publications) == 1

    def forever(*args, **kwargs):
        calls.append(1)
        raise HistoryExpired("expired")

    a.read_history = forever
    with pytest.raises(HistoryExpired):
        SyncService(a, cache, max_history_restarts=1).full_sync()
    assert len(calls) == 4 and len(cache.publications) == 1


def test_account_change_before_publication_aborts():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()

    def switched(*args, **kwargs):
        a.identity = Identity("other@example.com", "fake-client")
        return history()

    a.read_history = switched
    with pytest.raises(IdentityMismatch):
        SyncService(a, cache).full_sync()
    assert cache.current is None


def test_disappearance_not_failure_and_invalid_metadata_blocks_complete():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()
    a.list_message_ids = lambda page_token=None: {"ids": ["a", "vanished"], "next_page_token": None}
    inv = SyncService(a, cache).full_sync()
    assert "vanished" in inv.unresolved and not inv.complete
    a.messages["a"] = replace(msg("a"), valid=False)
    inv = SyncService(a, cache).full_sync()
    assert "a" in inv.unresolved and not inv.complete


def test_cancellation_never_publishes_and_progress_contains_no_subjects():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()
    events = []
    with pytest.raises(SyncCancelled):
        SyncService(a, cache, cancelled=lambda: bool(events), progress=events.append).full_sync()
    assert cache.current is None and events
    assert "private subject" not in repr(events)


def test_incremental_expiry_rebuilds_without_deleting_old_cache():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()
    old = SyncService(a, cache).full_sync()
    calls = []

    def replay(start, page_token=None):
        calls.append(start)
        if len(calls) == 1:
            raise HistoryExpired("expired")
        return history(cursor="fresh")

    a.read_history = replay
    new = SyncService(a, cache).incremental_sync()
    assert new.cursor == "fresh" and cache.publications == [old, new]


def test_tombstone_resolves_message_that_disappeared_during_scan():
    a, cache = FakeGmailAdapter([]), Cache()
    a.list_message_ids = lambda page_token=None: {"ids": ["gone"], "next_page_token": None}
    a.read_history = lambda *args, **kwargs: history(deleted=["gone"], unknown=True)
    inv = SyncService(a, cache).full_sync()
    assert inv.complete and not inv.messages and not inv.unresolved


def test_repeated_history_page_token_never_publishes():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()
    a.read_history = lambda *args, **kwargs: history(next="loop")
    with pytest.raises(ReadFailure):
        SyncService(a, cache).full_sync()
    assert cache.current is None


def test_failed_publish_preserves_old_cursor():
    a, cache = FakeGmailAdapter([msg("a")]), Cache()
    old = SyncService(a, cache).full_sync()

    def fail(inv):
        raise OSError("disk full")

    cache.publish = fail
    a.read_history = lambda *args, **kwargs: history(["a"], cursor="new")
    with pytest.raises(OSError):
        SyncService(a, cache).incremental_sync()
    assert cache.current is old


def test_sqlite_roundtrip_redaction_and_failure_rollback(tmp_path):
    from inbox_reclaimer.storage import CacheStore

    path = tmp_path / "cache.db"
    a = FakeGmailAdapter([msg("a")])
    cache = CacheStore(path)
    try:
        inv = SyncService(a, cache, redact_subjects=True).full_sync()
        assert cache.load(inv.account_id) == inv
    finally:
        cache.close()
    cache = CacheStore(path)
    try:
        before = cache.load(inv.account_id)
        assert before.messages[0].subject is None
        assert not any(k.lower() == "subject" for k in before.messages[0].headers)
        a.read_history = lambda *args, **kwargs: history(["a"], cursor="later")
        cache.conn.execute(
            "CREATE TRIGGER fail_insert BEFORE INSERT ON messages BEGIN SELECT RAISE(ABORT, 'disk failure'); END"
        )
        with pytest.raises(Exception, match="disk failure"):
            SyncService(a, cache).incremental_sync()
        assert cache.load(inv.account_id) == before
    finally:
        cache.close()
