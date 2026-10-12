from dataclasses import replace

import pytest

from inbox_reclaimer.gmail import FakeGmailAdapter
from inbox_reclaimer.models import Identity, IdentityMismatch, Message, ReadFailure


def message(i, sender="news@example.test", labels=frozenset()):
    return Message(
        str(i), "t" + str(i), 1000, 100, labels, sender, "Private subject", {"Subject": "Private subject"}
    )


class Journal:
    def __init__(self):
        self.addresses = set()

    def protections(self, account_id):
        return set(self.addresses)


def build(adapter, journal=None, **kwargs):
    from inbox_reclaimer.sender.selection import select_sender

    return select_sender(
        adapter, journal or Journal(), adapter.resolve_identity(), "news@example.test", **kwargs
    )


def fake(messages):
    from inbox_reclaimer.sender.demo import DemoSenderAdapter

    return DemoSenderAdapter(FakeGmailAdapter(messages))


def test_targeted_selection_1000_cap_not_full_mailbox_and_redaction():
    a = fake([message(i) for i in range(1500)] + [message("other", "other@example.test")])
    result = build(a, max_messages=1000, redact_subjects=True)
    assert result.examined_count == len(result.messages) == len(result.plan.ids) == 1000
    assert not result.exhausted
    assert a.list_calls == 2
    assert all(m.subject is None and "Subject" not in m.headers for m in result.messages)


@pytest.mark.parametrize("labels", [{"STARRED"}, {"IMPORTANT"}, {"SENT"}, {"DRAFT"}, {"TRASH"}, {"SPAM"}])
def test_selection_excludes_protected_labels(labels):
    result = build(fake([message(1, labels=frozenset(labels))]))
    assert result.plan is None and not result.messages
    assert result.skips == {"1": "protected_label"}


def test_thread_member_starred_after_message_fetch_is_excluded():
    a = fake([message(1)])
    a.get_thread = lambda _: [replace(message(1), labels=frozenset({"STARRED"}))]
    result = build(a)
    assert not result.messages


def test_replied_thread_and_sender_protection_and_bad_thread_fail_closed():
    a = fake([message(1), replace(message(2, labels=frozenset({"SENT"})), thread_id="t1")])
    assert not build(a).messages
    a = fake([message(1)])
    journal = Journal()
    journal.addresses.add("news@example.test")
    assert not build(a, journal).messages
    a.get_thread = lambda _: []
    assert not build(a).messages


def test_gmail_query_is_only_candidate_filter_and_no_extra_reads_after_cap():
    a = fake([message(1), message(2, sender="not-news@example.test"), message(3)])
    a.list_sender_ids = lambda *args, **kwargs: {"ids": ["1", "2", "3"], "next_page_token": "more"}
    result = build(a, max_messages=2)
    assert result.examined_count == 2
    assert result.plan.ids == ("1",)
    assert result.skips["2"] == "sender_mismatch"


def test_page_error_and_identity_change_abort_instead_of_creating_plan():
    a = fake([message(1)])
    a.list_sender_ids = lambda *args, **kwargs: {"ids": ["1"], "next_page_token": "loop"}
    with pytest.raises(ReadFailure):
        build(a)
    a = fake([message(1)])

    def switch(*args, **kwargs):
        a.base.identity = Identity("other@example.test", "other-client")
        return {"ids": ["1"], "next_page_token": None}

    a.list_sender_ids = switch
    with pytest.raises(IdentityMismatch):
        build(a)


@pytest.mark.parametrize("limit", [0, 1001, True, -1])
def test_invalid_candidate_cap_rejected(limit):
    with pytest.raises(ValueError):
        build(fake([]), max_messages=limit)


def test_no_age_size_or_newsletter_header_requirement():
    result = build(fake([replace(message(1), size_estimate=0, headers={})]))
    assert result.plan.ids == ("1",)


@pytest.mark.parametrize("thread", [None, 3, "malformed"])
def test_malformed_thread_responses_are_excluded(thread):
    a = fake([message(1)])
    a.get_thread = lambda _: thread
    result = build(a)
    assert not result.messages
    assert result.skips == {"1": "invalid_thread_read"}


def test_missing_records_consume_slots_and_no_silent_query_refill():
    a = fake([])
    a.list_sender_ids = lambda *args, **kwargs: {"ids": ["gone", "old"], "next_page_token": "more"}
    result = build(a, max_messages=1)
    assert result.examined_count == 1 and result.plan is None
    assert result.skips == {"gone": "missing"}
