from dataclasses import replace
from datetime import datetime, timezone

import pytest

from inbox_reclaimer.models import Identity, IdentityMismatch, IncompleteInventory, Inventory, Message, Rule
from inbox_reclaimer.proposals import ProposalService
from inbox_reclaimer.storage import CacheStore, JournalStore


CUT = datetime(2026, 3, 31, tzinfo=timezone.utc)


def msg(i, **kwargs):
    m = Message(
        i,
        "t" + i,
        1577836800000,
        10_000_001,
        frozenset({"CATEGORY_PROMOTIONS"}),
        "sender@example.test",
        "PRIVATE SUBJECT",
        {"list-unsubscribe": "<mailto:leave@example.test>"},
    )
    return replace(m, **kwargs)


class Adapter:
    def __init__(self, identity, messages):
        self.identity = identity
        self.threads = {}
        self.calls = []
        for m in messages:
            self.threads.setdefault(m.thread_id, []).append(m)

    def resolve_identity(self):
        return self.identity

    def get_thread(self, thread_id):
        self.calls.append(thread_id)
        result = self.threads[thread_id]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture
def setup(tmp_path):
    identity = Identity("owner@example.test", "client")
    cache = CacheStore(tmp_path / "cache.db")
    journal = JournalStore(tmp_path / "journal.db")
    journal.bind_account(identity)

    def make(messages):
        cache.publish(Inventory(identity.account_id, "g1", "h1", "start", "end", True, (), tuple(messages)))
        adapter = Adapter(identity, messages)
        return ProposalService(cache, journal, adapter), adapter, identity

    yield make, cache, journal
    cache.close()
    journal.close()


RULES = [
    Rule("category", "CATEGORY_AGE", older_months=6, category="CATEGORY_PROMOTIONS"),
    Rule("newsletter", "SENDER_NEWSLETTER"),
    Rule("size-z", "SIZE_AGE", min_bytes=5_000_000),
    Rule("size-a", "SIZE_AGE", min_bytes=5_000_000),
]


def test_unique_priority_tags_bounding_reject_new_revision(setup):
    make, cache, journal = setup
    service, adapter, identity = make([msg(str(i)) for i in range(5)])
    p = service.build_revision(identity, RULES, CUT, min_batch_bytes=1, max_batch_messages=2)
    assert [len(b.ids) for b in p.batches] == [2, 2, 1]
    assert all(b.kind == "SIZE_AGE" for b in p.batches)
    ids = [i for b in p.batches for i in b.ids]
    assert len(ids) == len(set(ids)) == 5
    assert sum(b.estimated_bytes for b in p.batches) == 50_000_005
    assert p.batches[0].reasons[p.batches[0].ids[0]] == ["size-a", "size-z", "newsletter", "category"]
    journal.reject_batch(identity.account_id, p.plan_id, p.revision, p.batches[0].batch_id)
    assert journal.get_plan(identity.account_id, p.plan_id) == p
    p2 = service.build_revision(
        identity, list(reversed(RULES)), CUT, min_batch_bytes=1, max_batch_messages=2, plan_id=p.plan_id
    )
    assert p2.revision == 2
    assert [b.ids for b in p2.batches] == [b.ids for b in p.batches]
    assert p2.batches[0].digest != p.batches[0].digest
    assert journal.conn.execute("SELECT count(*) FROM approvals").fetchone()[0] == 0


@pytest.mark.parametrize("label", ["STARRED", "IMPORTANT", "SENT", "DRAFT", "TRASH", "SPAM"])
def test_protected_labels(setup, label):
    make, _, _ = setup
    service, _, identity = make([msg("1", labels=frozenset({label}))])
    assert not service.build_revision(identity, RULES, CUT, min_batch_bytes=1).batches


def test_thread_sent_failed_read_malformed_and_sender_protection(setup):
    make, _, journal = setup
    messages = [msg(str(i)) for i in range(7)]
    service, adapter, identity = make(messages)
    adapter.threads["t0"].append(msg("sent", thread_id="t0", labels=frozenset({"SENT"})))
    adapter.threads["t1"] = OSError("read failed")
    adapter.threads["t2"] = [msg("2", raw_from="malformed")]
    adapter.threads["t3"] = [msg("3", size_estimate=None)]
    adapter.threads["t4"] = []
    adapter.threads["t5"] = [msg("5", labels=frozenset({"STARRED"}))]
    adapter.threads["t6"] = [msg("6", raw_from="protected@example.test")]
    journal.protect_sender(identity.account_id, "protected@example.test")
    assert not service.build_revision(identity, RULES, CUT, min_batch_bytes=1).batches


def test_incomplete_and_account_switch_stop(setup):
    make, cache, _ = setup
    service, adapter, identity = make([msg("1")])
    adapter.identity = Identity("other@example.test", "client")
    with pytest.raises(IdentityMismatch):
        service.build_revision(identity, RULES, CUT)
    adapter.identity = identity
    old = cache.load(identity.account_id)
    cache.publish(replace(old, generation="g2", complete=False, unresolved=("missing",)))
    with pytest.raises(IncompleteInventory):
        service.build_revision(identity, RULES, CUT)


def test_unknown_kind_and_naive_cutoff_rejected(setup):
    make, _, _ = setup
    service, _, identity = make([msg("1")])
    with pytest.raises(ValueError):
        service.build_revision(identity, [Rule("bad", "ATTACHMENT")], CUT)
    with pytest.raises(ValueError):
        service.build_revision(identity, RULES, CUT.replace(tzinfo=None))
