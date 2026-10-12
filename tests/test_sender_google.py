"""Offline SDK doubles only; the live gate is opened solely by this test fixture."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inbox_reclaimer import gmail as base_gmail
from inbox_reclaimer.models import GateClosed, IdentityMismatch, ReadFailure, ReclaimError
from inbox_reclaimer.sender import gmail

READ = "https://www.googleapis.com/auth/gmail.readonly"
MODIFY = "https://www.googleapis.com/auth/gmail.modify"


class Request:
    def __init__(self, service, method, result):
        self.service, self.method, self.result = service, method, result
        self.headers = {}

    def execute(self, *, num_retries):
        assert num_retries == 0
        assert self.headers["authorization"].startswith("Bearer ")
        self.service.executions.append(self.method)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Service:
    def __init__(self):
        self.calls, self.executions = [], []
        self.route = "messages"
        self.responses = {
            "profile": {"emailAddress": "owner@example.test"},
            "list": {"messages": [{"id": "a"}], "nextPageToken": "next"},
            "labels": {"labels": [{"id": "Label_1", "type": "user"}]},
            "batchModify": b"",
            "untrash": {"id": "a"},
            "modify": {"id": "a"},
            "get": {
                "id": "a",
                "threadId": "t",
                "internalDate": "1",
                "sizeEstimate": 1,
                "labelIds": ["INBOX"],
                "payload": {"headers": [{"name": "From", "value": "x@y.test"}]},
            },
        }

    def users(self):
        return self

    def messages(self):
        self.route = "messages"
        return self

    def threads(self):
        self.route = "threads"
        return self

    def labels(self):
        self.route = "labels"
        return self

    def call(self, method, kwargs):
        self.calls.append((method, kwargs))
        return Request(self, method, self.responses[method])

    def getProfile(self, **kwargs):
        return self.call("profile", kwargs)

    def list(self, **kwargs):
        return self.call("labels" if self.route == "labels" else "list", kwargs)

    def get(self, **kwargs):
        return self.call("thread" if self.route == "threads" else "get", kwargs)

    def batchModify(self, **kwargs):
        return self.call("batchModify", kwargs)

    def untrash(self, **kwargs):
        return self.call("untrash", kwargs)

    def modify(self, **kwargs):
        return self.call("modify", kwargs)


@pytest.fixture
def google(tmp_path, monkeypatch):
    # This directory contains synthetic data, never the operator's profile.
    (tmp_path / "google_token.json").write_text(json.dumps({"client_id": "fixture-client"}))
    credentials = SimpleNamespace(client_id="fixture-client", token="FAKE", valid=True, expired=False)
    service = Service()
    info = {"scope": MODIFY, "aud": "fixture-client", "email": "owner@example.test"}
    response = Mock()
    response.json.side_effect = lambda: dict(info)
    monkeypatch.setattr(base_gmail.Credentials, "from_authorized_user_info", lambda _: credentials)
    monkeypatch.setattr(base_gmail, "build", lambda *a, **kw: service)
    tokeninfo = Mock(return_value=response)
    monkeypatch.setattr(base_gmail.requests, "get", tokeninfo)
    costs = {"profile": 1, "list": 5, "get": 20, "thread": 40, "trash": 50, "untrash": 5, "modify": 5}
    quota = SimpleNamespace(config=SimpleNamespace(method_costs=costs))
    quota.acquire = Mock(side_effect=lambda method, **kw: costs[method])
    base = base_gmail.GoogleReadAdapter(tmp_path, quota=quota, sleep=lambda _: None)
    return base, service, credentials, info, tokeninfo


@pytest.fixture
def writer(google, monkeypatch):
    monkeypatch.setattr(gmail, "require_live_release", lambda: None)
    return gmail.GoogleSenderWriter(google[0])


@pytest.mark.parametrize("status", [200, 204])
def test_batch_modify_accepts_real_sdk_empty_success_response(google, writer, status):
    import httplib2
    from googleapiclient.discovery import build

    # Exercise the real SDK response decoder without sending any request.
    service = build("gmail", "v1", http=httplib2.Http(), static_discovery=True, cache_discovery=False)
    request = (
        service.users().messages().batchModify(userId="me", body={"ids": ["a"], "addLabelIds": ["TRASH"]})
    )
    decoded = request.postproc(httplib2.Response({"status": str(status)}), b"")
    assert type(decoded) in (bytes, str) and not decoded
    google[1].responses["batchModify"] = decoded
    writer.prepare_write("trash")
    guards = []
    writer.set_dispatch_guard(lambda: guards.append(True))
    assert writer.trash_ids(["a"]) == {}
    assert guards == [True]
    assert google[1].executions.count("batchModify") == 1


@pytest.mark.parametrize("result", [None, False, [], b"unexpected", "unexpected"])
def test_batch_modify_does_not_accept_arbitrary_empty_or_raw_response(google, writer, result):
    google[1].responses["batchModify"] = result
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(gmail.WriteFailure):
        writer.trash_ids(["a"])
    assert google[1].executions.count("batchModify") == 1


@pytest.mark.parametrize("result", [b"", ""])
def test_untrash_still_requires_message_response(google, writer, result):
    google[1].responses["untrash"] = result
    writer.prepare_write("restore")
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(gmail.WriteFailure):
        writer.untrash_message("a")
    assert google[1].executions.count("untrash") == 1


@pytest.mark.parametrize("read_failure", [False, True])
def test_empty_ack_requires_postimage_before_journal_confirmation(
    google, writer, tmp_path, monkeypatch, read_failure
):
    import time
    from uuid import uuid4
    from inbox_reclaimer.storage import JournalStore
    from inbox_reclaimer.sender.journal import SenderJournal
    from inbox_reclaimer.sender.executor import SenderExecutor
    from inbox_reclaimer.sender.models import Approval, SenderPlan

    service = google[1]
    service.responses["thread"] = {"messages": [service.responses["get"]]}
    original_execute = Request.execute

    def execute(request, *, num_retries):
        result = original_execute(request, num_retries=num_retries)
        if request.method == "batchModify":
            service.responses["get"]["labelIds"] = ["TRASH"]
            if read_failure:
                service.responses["get"] = RuntimeError("synthetic observation failure")
        return result

    monkeypatch.setattr(Request, "execute", execute)
    identity = writer.resolve_identity()
    plan = SenderPlan(identity.account_id, uuid4().hex, "x@y.test", ("a",))
    with JournalStore(tmp_path / "journal.db") as store:
        store.bind_account(identity)
        journal = SenderJournal(store)
        journal.save_plan(plan)
        now = time.time()
        approval = Approval(
            identity.account_id,
            plan.plan_id,
            plan.digest,
            "trash",
            "synthetic-test",
            uuid4().hex,
            uuid4().hex,
            now,
            now + 900,
        )
        approval_id = journal.approve(plan, approval)
        executor = SenderExecutor(writer, journal)
        result = executor.execute(plan, approval_id, dry_run=False)
        state = "unknown" if read_failure else "confirmed"
        assert result[state] == 1
        operation = journal.operations(identity.account_id)[0]
        assert operation["state"] == state
        assert (operation["postimage"] is not None) == (not read_failure)
        executor.execute(plan, approval_id, dry_run=False)
        assert service.executions.count("batchModify") == 1


def test_writer_gate_precedes_any_base_access(monkeypatch):
    monkeypatch.setattr(
        "inbox_reclaimer.sender.models.release_status", lambda: {"live_mutation_released": False}
    )

    class NoAccess:
        def __getattribute__(self, name):
            pytest.fail("base touched before gate")

    with pytest.raises(GateClosed):
        gmail.GoogleSenderWriter(NoAccess())


def test_reader_query_parameters_and_delegation(google):
    base, service, *_ = google
    reader = gmail.GoogleSenderReader(base)
    assert reader.list_sender_ids("News@Example.TEST", "p", 20) == {"ids": ["a"], "next_page_token": "next"}
    assert (
        "list",
        {
            "userId": "me",
            "q": 'from:"News@example.test"',
            "maxResults": 20,
            "includeSpamTrash": True,
            "pageToken": "p",
        },
    ) in service.calls
    assert reader.resolve_identity() == base.resolve_identity()
    assert reader.get_metadata("a").id == "a"
    service.responses["thread"] = {"messages": [service.responses["get"]]}
    assert reader.get_thread("t")[0].id == "a"
    with pytest.raises(GateClosed):
        reader.validate_capability("trash")


@pytest.mark.parametrize(
    "sender", ["x@y.test OR from:z@y.test", "from:x@y.test", "Name <x@y.test>", "x@y.test\n", "x@y.test)"]
)
def test_sender_injection_rejected_without_network(google, sender):
    with pytest.raises(ValueError):
        gmail.GoogleSenderReader(google[0]).list_sender_ids(sender)
    assert not google[1].calls and not google[4].called


@pytest.mark.parametrize("size", [0, 501, True, 1.5])
def test_invalid_page_size_before_network(google, size):
    with pytest.raises(ValueError):
        gmail.GoogleSenderReader(google[0]).list_sender_ids("x@y.test", max_results=size)
    assert not google[1].calls


@pytest.mark.parametrize(
    "response",
    [
        [],
        {"messages": None},
        {"messages": [{}]},
        {"messages": [{"id": "a"}, {"id": "a"}]},
        {"nextPageToken": 2},
    ],
)
def test_malformed_enumeration_fails_closed(google, response):
    google[1].responses["list"] = response
    with pytest.raises(ReadFailure):
        gmail.GoogleSenderReader(google[0]).list_sender_ids("x@y.test")


def test_prepare_reserves_before_safety_reads_and_only_once(google, writer):
    base, service, *_ = google
    events = []
    base.quota.config.method_costs["trash"] = 73
    base.quota.acquire.side_effect = lambda method, **kw: (
        events.append(method) or base.quota.config.method_costs[method]
    )
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    assert events[0] == "trash"  # Configured mutation charge precedes all reads.
    assert base.quota.acquire.call_args_list[0].kwargs == {"priority": True}
    writer.get_metadata("a")
    writer.trash_ids(["a"])
    assert events.count("trash") == 1
    assert (
        "batchModify",
        {"userId": "me", "body": {"ids": ["a"], "addLabelIds": ["TRASH"]}},
    ) in service.calls
    assert "removeLabelIds" not in service.calls[-1][1]["body"]
    with pytest.raises(ReclaimError):
        writer.trash_ids(["a"])
    assert service.executions.count("batchModify") == 1


@pytest.mark.parametrize("scope", [READ, "https://www.googleapis.com/auth/gmail.send"])
def test_insufficient_actual_grants_no_write(google, writer, scope):
    google[3]["scope"] = scope
    with pytest.raises(GateClosed):
        writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    assert "batchModify" not in google[1].executions


@pytest.mark.parametrize("scope", [MODIFY, "https://mail.google.com/"])
def test_stronger_scope_never_exposes_delete(google, writer, scope):
    google[3]["scope"] = scope
    writer.validate_capability("restore")
    assert not hasattr(writer, "delete_ids") and not hasattr(writer, "delete_message")
    before = len(google[1].calls)
    with pytest.raises(GateClosed):
        writer.validate_capability("permanent_delete")
    assert len(google[1].calls) == before


def test_final_dispatch_rechecks_identity(google, writer):
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    google[1].responses["profile"]["emailAddress"] = "other@example.test"
    with pytest.raises(IdentityMismatch):
        writer.trash_ids(["a"])
    assert "batchModify" not in google[1].executions


def test_refresh_rechecks_current_grants_before_dispatch(google, writer):
    base, service, creds, info, tokeninfo = google
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    creds.valid = False

    def refresh(_):
        creds.valid, creds.token = True, "NEW-FAKE"

    creds.refresh = refresh
    info["scope"] = READ
    with pytest.raises(GateClosed):
        writer.trash_ids(["a"])
    assert tokeninfo.call_count == 2
    assert "batchModify" not in service.executions


def test_ambiguous_write_is_single_attempt_redacted_and_reservation_spent(google, writer):
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    google[1].responses["batchModify"] = TimeoutError("SECRET access token")
    with pytest.raises(ReclaimError) as error:
        writer.trash_ids(["a"])
    assert "SECRET" not in str(error.value)
    assert "ambiguous" in str(error.value).lower()
    with pytest.raises(ReclaimError):
        writer.trash_ids(["a"])
    assert google[1].executions.count("batchModify") == 1


@pytest.mark.parametrize("ids", [[], ["a"] * 2, ["x" + str(i) for i in range(21)], "a"])
def test_batch_validation_no_write(google, writer, ids):
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises((ValueError, ReclaimError)):
        writer.trash_ids(ids)
    assert "batchModify" not in google[1].executions


def test_restore_supported_label_delta_and_single_attempt(google, writer):
    writer.prepare_write("untrash")
    writer.set_dispatch_guard(lambda: None)
    writer.untrash_message("a")
    writer.prepare_write("modify")
    writer.set_dispatch_guard(lambda: None)
    writer.modify_message("a", ["INBOX", "Label_1"], ["UNREAD"])
    method, params = google[1].calls[-1]
    assert method == "modify"
    assert params["body"] == {"addLabelIds": ["INBOX", "Label_1"], "removeLabelIds": ["UNREAD"]}


@pytest.mark.parametrize("label", ["TRASH", "SENT", "CATEGORY_PROMOTIONS", "SPAM", "Label_missing"])
def test_unknown_or_system_label_mutations_fail_safe(google, writer, label):
    writer.prepare_write("modify")
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(ReclaimError):
        writer.modify_message("a", [label], [])
    assert "modify" not in google[1].executions


def test_wrong_write_response_identity_is_ambiguous(google, writer):
    writer.prepare_write("untrash")
    writer.set_dispatch_guard(lambda: None)
    google[1].responses["untrash"] = {"id": "different"}
    with pytest.raises(ReclaimError):
        writer.untrash_message("a")
    assert google[1].executions.count("untrash") == 1


def test_grouping_characters_remain_inside_one_quoted_sender(google):
    reader = gmail.GoogleSenderReader(google[0])
    reader.list_sender_ids("{news}OR{other}@Example.TEST")
    query = [params["q"] for method, params in google[1].calls if method == "list"]
    assert query == ['from:"{news}OR{other}@example.test"']
    # Enumeration is only a candidate stage; metadata remains available for exact matching.
    assert reader.get_metadata("a").id == "a"


@pytest.mark.parametrize(
    "costs,method", [({"untrash": 31, "modify": 7}, "untrash"), ({"untrash": 7, "modify": 31}, "modify")]
)
@pytest.mark.parametrize("operation", ["untrash", "modify"])
def test_restore_reserves_larger_configured_cost_once(google, writer, costs, method, operation):
    quota = google[0].quota
    quota.config.method_costs.update(costs)
    writer.prepare_write("restore")
    writer.set_dispatch_guard(lambda: None)
    if operation == "untrash":
        writer.untrash_message("a")
    else:
        writer.modify_message("a", ["INBOX"], [])
    mutations = [c for c in quota.acquire.call_args_list if c.args[0] in costs]
    assert len(mutations) == 1
    assert mutations[0].args == (method,)
    assert mutations[0].kwargs == {"priority": True}
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(ReclaimError, match="reservation"):
        writer.untrash_message("a")
    assert google[1].executions.count(operation) == 1


@pytest.mark.parametrize(
    "operation,key",
    [
        ("trash", "trash"),
        ("untrash", "untrash"),
        ("modify", "modify"),
        ("restore", "untrash"),
        ("restore", "modify"),
    ],
)
@pytest.mark.parametrize("cost", [None, 0, -1, True, 5.5, "5"])
def test_missing_or_invalid_mutation_cost_fails_before_reads(google, writer, operation, key, cost):
    costs = google[0].quota.config.method_costs
    if cost is None:
        del costs[key]
    else:
        costs[key] = cost
    with pytest.raises(ReclaimError, match="quota"):
        writer.prepare_write(operation)
    assert not google[0].quota.acquire.called
    assert not google[1].calls


@pytest.mark.parametrize("charged", [0, True, 5, 51, None])
def test_incorrect_quota_charge_fails_without_retry(google, writer, charged):
    google[0].quota.acquire.side_effect = lambda *a, **kw: charged
    with pytest.raises(ReclaimError, match="quota"):
        writer.prepare_write("trash")
    google[0].quota.acquire.assert_called_once_with("trash", priority=True)
    assert not google[1].calls


@pytest.mark.parametrize("callback", [None, True, 1, "approve"])
def test_dispatch_guard_must_be_callable(writer, callback):
    with pytest.raises((TypeError, ValueError, ReclaimError)):
        writer.set_dispatch_guard(callback)


def test_missing_guard_consumes_reservation_without_sdk_dispatch(google, writer):
    writer.prepare_write("trash")
    with pytest.raises(ReclaimError, match="guard"):
        writer.trash_ids(["a"])
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(ReclaimError, match="reservation"):
        writer.trash_ids(["a"])
    assert not any(method == "batchModify" for method, _ in google[1].calls)


@pytest.mark.parametrize("reason", ["Safety read is stale", "Approval expired"])
def test_guard_runs_after_slow_final_identity_and_request_build(google, writer, monkeypatch, reason):
    writer.prepare_write("trash")
    elapsed = [0]
    resolve = writer.resolve_identity

    def slow_identity():
        identity = resolve()
        elapsed[0] = 100
        return identity

    monkeypatch.setattr(writer, "resolve_identity", slow_identity)

    def guard():
        assert elapsed[0] == 100
        assert google[1].calls[-1][0] == "batchModify"
        raise GateClosed(reason)

    check = Mock(side_effect=guard)
    writer.set_dispatch_guard(check)
    with pytest.raises(GateClosed, match=reason):
        writer.trash_ids(["a"])
    check.assert_called_once_with()
    assert "batchModify" not in google[1].executions
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(ReclaimError, match="reservation"):
        writer.trash_ids(["a"])


def test_new_preparation_discards_unused_guard(google, writer):
    writer.prepare_write("trash")
    guard = Mock()
    writer.set_dispatch_guard(guard)
    writer.prepare_write("trash")
    with pytest.raises(ReclaimError, match="guard"):
        writer.trash_ids(["a"])
    guard.assert_not_called()
    assert "batchModify" not in google[1].executions


def test_invalid_attempt_clears_guard_and_reservation(google, writer):
    writer.prepare_write("trash")
    writer.set_dispatch_guard(lambda: None)
    with pytest.raises(ReclaimError):
        writer.trash_ids([])
    with pytest.raises(ReclaimError, match="reservation"):
        writer.trash_ids(["a"])
    assert "batchModify" not in google[1].executions
