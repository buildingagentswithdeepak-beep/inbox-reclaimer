import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from inbox_reclaimer import gmail
from inbox_reclaimer.models import (
    Identity,
    Message,
    GateClosed,
    IdentityMismatch,
    MissingMessage,
    HistoryExpired,
    ReadFailure,
)

READ = "https://www.googleapis.com/auth/gmail.readonly"


class Credentials:
    def __init__(self):
        self.token = "access-SECRET"
        self.client_id = "client-123"
        self.valid = True
        self.expired = False
        self.refresh_count = 0

    def refresh(self, request):
        self.refresh_count += 1
        self.token = "refreshed-SECRET"
        self.valid = True
        self.expired = False


class Request:
    def __init__(self, result):
        self.result = result
        self.headers = {}

    def execute(self, **kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Resource:
    def __init__(self):
        self.calls = []
        self.responses = {
            "profile": {"emailAddress": "owner@example.com", "historyId": "H0"},
            "list": {"messages": [{"id": "1"}], "nextPageToken": "next"},
            "get": {
                "id": "1",
                "threadId": "t1",
                "internalDate": "1000",
                "sizeEstimate": 20,
                "labelIds": [],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "a@example.com"},
                        {"name": "Subject", "value": "secret"},
                    ]
                },
            },
            "thread": {"messages": []},
            "history": {"historyId": "H1"},
        }
        self.route = None

    def users(self):
        return self

    def messages(self):
        self.route = "messages"
        return self

    def threads(self):
        self.route = "threads"
        return self

    def history(self):
        self.route = "history"
        return self

    def call(self, method, kwargs):
        self.calls.append((method, kwargs))
        result = self.responses[method]
        if isinstance(result, list):
            result = result.pop(0)
        return Request(result)

    def getProfile(self, **kw):
        return self.call("profile", kw)

    def list(self, **kw):
        return self.call("history" if self.route == "history" else "list", kw)

    def get(self, **kw):
        return self.call("thread" if self.route == "threads" else "get", kw)


class HTTPError(Exception):
    def __init__(self, status, retry_after=None):
        super().__init__("access-SECRET response content")
        self.resp = {"retry-after": retry_after} if retry_after else {}
        self.resp = type("Response", (dict,), {"status": status})(self.resp)
        self.content = b"{}"


@pytest.fixture
def google(tmp_path, monkeypatch):
    token = tmp_path / "google_token.json"
    token.write_text(
        json.dumps(
            {
                "client_id": "client-123",
                "client_secret": "SECRET",
                "refresh_token": "SECRET",
                "token": "access-SECRET",
                "scopes": [READ],
            }
        )
    )
    creds, service = Credentials(), Resource()
    monkeypatch.setattr(gmail.Credentials, "from_authorized_user_info", lambda info: creds)
    monkeypatch.setattr(gmail, "build", lambda *args, **kwargs: service)
    info = {"scope": READ, "aud": "client-123", "email": "owner@example.com"}
    response = Mock()
    response.json.side_effect = lambda: dict(info)
    response.raise_for_status.return_value = None
    get = Mock(return_value=response)
    monkeypatch.setattr(gmail.requests, "get", get)
    quota = SimpleNamespace(acquire=Mock())
    adapter = gmail.GoogleReadAdapter(tmp_path, quota=quota, sleep=lambda _: None)
    return adapter, creds, service, info, token, get, quota


def test_fake_is_deterministic_paged_and_read_only():
    m = Message("a", "t", 1, 10, frozenset(), "a@example.com")
    a = gmail.FakeGmailAdapter([m], page_size=1)
    assert a.resolve_identity() == a.resolve_identity()
    assert a.list_message_ids() == {"ids": ["a"], "next_page_token": None}
    assert a.get_thread("t") == [m]
    with pytest.raises(MissingMessage):
        a.get_metadata("missing")
    for method in ["trash_ids", "untrash_message", "modify_message", "delete_ids"]:
        assert not hasattr(a, method)
    with pytest.raises(GateClosed):
        a.validate_capability("trash")


@pytest.mark.parametrize(
    "grant", [READ, "https://www.googleapis.com/auth/gmail.modify", "https://mail.google.com/"]
)
def test_stronger_scopes_map_to_read_but_never_mutation(google, grant):
    a, c, s, info, *_ = google
    info["scope"] = grant
    assert a.resolve_identity() == Identity("owner@example.com", "client-123")
    a.validate_capability("analyze")
    with pytest.raises(GateClosed):
        a.validate_capability("permanent_delete")
    assert not hasattr(a, "delete_ids")


@pytest.mark.parametrize("scope", ["", None, "https://www.googleapis.com/auth/gmail.send"])
def test_actual_unknown_or_insufficient_grants_fail_before_gmail(google, scope):
    a, c, s, info, *_ = google
    info["scope"] = scope
    with pytest.raises(GateClosed):
        a.list_message_ids()
    assert not s.calls


def test_client_identity_and_account_switch_fail_closed(google):
    a, c, s, info, *_ = google
    a.resolve_identity()
    s.responses["profile"]["emailAddress"] = "other@example.com"
    with pytest.raises(IdentityMismatch):
        a.list_message_ids()
    assert not any(m == "list" for m, _ in s.calls)


def test_wrong_oauth_audience_fails_before_profile(google):
    a, c, s, info, *_ = google
    info["aud"] = "other-client"
    with pytest.raises(IdentityMismatch):
        a.resolve_identity()
    assert not s.calls


def test_credentials_loaded_once_refresh_revalidates_actual_grants(google):
    a, c, s, info, token, get, q = google
    a.resolve_identity()
    token.write_text("replaced invalid token file")
    a.list_message_ids()
    assert get.call_count == 1
    c.valid = False
    c.expired = True
    info["scope"] = ""
    with pytest.raises(GateClosed):
        a.get_metadata("1")
    assert c.refresh_count == 1 and get.call_count == 2
    assert token.read_text() == "replaced invalid token file"


def test_list_and_metadata_parameters_and_opaque_history(google):
    a, c, s, *_ = google
    assert a.list_message_ids("page") == {"ids": ["1"], "next_page_token": "next"}
    kw = next(kw for m, kw in s.calls if m == "list")
    assert kw == {"userId": "me", "maxResults": 500, "includeSpamTrash": True, "pageToken": "page"}
    m = a.get_metadata("1")
    assert m.valid and m.headers["subject"] == "secret"
    kw = next(kw for method, kw in s.calls if method == "get")
    assert kw["format"] == "metadata"
    assert {h.lower() for h in kw["metadataHeaders"]} == {
        "from",
        "subject",
        "message-id",
        "in-reply-to",
        "references",
        "list-unsubscribe",
        "list-unsubscribe-post",
    }


def test_history_uses_every_structured_event_and_unknown_threads(google):
    a, c, s, *_ = google
    s.responses["history"] = {
        "historyId": "opaque",
        "nextPageToken": "p2",
        "history": [
            {
                "messages": [{"id": "generic", "threadId": "tg"}],
                "messagesAdded": [{"message": {"id": "a", "threadId": "ta"}}],
                "messagesDeleted": [{"message": {"id": "b", "threadId": "tb"}}],
                "labelsAdded": [{"message": {"id": "c", "threadId": "tc"}, "labelIds": ["SENT"]}],
                "labelsRemoved": [{"message": {"id": "d"}, "labelIds": ["SENT"]}],
            }
        ],
    }
    h = a.read_history("start", "page")
    assert set(h["affected_ids"]) >= {"a", "c", "d"}
    assert h["deleted_ids"] == ["b"]
    assert {"ta", "tb", "tc"} <= set(h["thread_ids"])
    assert h["unknown_threads"] and h["history_id"] == "opaque" and h["next_page_token"] == "p2"


def test_read_retries_charge_each_attempt_and_honor_retry_after(google):
    a, c, s, info, token, get, q = google
    sleeps = []
    a.sleep = sleeps.append
    s.responses["get"] = [HTTPError(429, "7"), s.responses["get"]]
    assert a.get_metadata("1").id == "1"
    assert sleeps and sleeps[0] >= 7
    assert sum(call.args == ("get",) for call in q.acquire.call_args_list) == 2


@pytest.mark.parametrize(
    "method,status,error",
    [("get", 404, MissingMessage), ("history", 404, HistoryExpired), ("get", 403, ReadFailure)],
)
def test_errors_are_classified_and_never_disclose_secrets(google, method, status, error):
    a, c, s, *_ = google
    s.responses[method] = HTTPError(status)
    with pytest.raises(error) as caught:
        a.get_metadata("1") if method == "get" else a.read_history("H0")
    assert "SECRET" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_malformed_metadata_is_not_silently_valid(google):
    a, c, s, *_ = google
    s.responses["get"] = {
        "id": "1",
        "threadId": "",
        "sizeEstimate": "wrong",
        "internalDate": "wrong",
        "payload": {},
    }
    assert not a.get_metadata("1").valid


def test_refresh_revalidates_even_if_provider_returns_same_access_token(google):
    a, c, s, info, token, get, q = google
    a.resolve_identity()
    c.valid = False
    c.expired = True

    def same_token(request):
        c.valid = True
        c.expired = False

    c.refresh = same_token
    info["scope"] = ""
    with pytest.raises(GateClosed):
        a.get_metadata("1")
    assert get.call_count == 2


def test_refresh_account_switch_cannot_dispatch_metadata(google):
    a, c, s, info, *_ = google
    a.resolve_identity()
    c.valid = False
    c.expired = True
    info["email"] = "switched@example.com"
    s.responses["profile"]["emailAddress"] = "switched@example.com"
    with pytest.raises(IdentityMismatch):
        a.get_metadata("1")
    assert not any(m == "get" for m, _ in s.calls)


def test_failed_refresh_sanitizes_and_does_not_write_token(google):
    a, c, s, info, token, *_ = google
    original = token.read_bytes()

    def fail(request):
        raise RuntimeError("refresh-SECRET")

    c.refresh = fail
    c.valid = False
    with pytest.raises(ReadFailure) as error:
        a.resolve_identity()
    assert "SECRET" not in str(error.value)
    assert token.read_bytes() == original


def test_network_retry_exhaustion_is_bounded_and_sanitized(google):
    a, c, s, info, token, get, q = google
    s.responses["get"] = TimeoutError("SECRET")
    a.jitter = lambda low, high: high
    sleeps = []
    a.sleep = sleeps.append
    with pytest.raises(ReadFailure) as error:
        a.get_metadata("1")
    assert "SECRET" not in str(error.value)
    assert len([m for m, _ in s.calls if m == "get"]) == a.max_attempts
    assert sleeps == [1, 2, 4]


def test_403_rate_limit_retries_but_permissions_do_not(google):
    a, c, s, *_ = google
    failure = HTTPError(403)
    failure.content = b'{"error":{"errors":[{"reason":"userRateLimitExceeded"}]}}'
    s.responses["get"] = [failure, s.responses["get"]]
    assert a.get_metadata("1").id == "1"
    assert len([m for m, _ in s.calls if m == "get"]) == 2


def test_retry_after_http_date(google):
    a, *_ = google
    a.wall_clock = lambda: 0
    assert a._retry_after({"Retry-After": "Thu, 01 Jan 1970 00:00:10 GMT"}) == 10


def test_no_profile_fallback_when_expected_token_is_missing(tmp_path):
    with pytest.raises(ReadFailure):
        gmail.GoogleReadAdapter(tmp_path / "absent-profile")
    assert list(tmp_path.iterdir()) == []


def test_bad_tokeninfo_failure_sanitized_before_any_gmail_call(google):
    a, c, s, info, token, get, _ = google
    get.side_effect = ValueError("SECRET")
    with pytest.raises(GateClosed) as error:
        a.resolve_identity()
    assert "SECRET" not in str(error.value) and not s.calls


def test_thread_metadata_and_complete_member_coverage(google):
    a, c, s, *_ = google
    s.responses["thread"] = {"messages": [s.responses["get"]]}
    assert a.get_thread("t1")[0].id == "1"
    params = next(kw for m, kw in s.calls if m == "thread")
    assert params["format"] == "metadata" and params["id"] == "t1"
    assert set(params["metadataHeaders"]) == set(gmail.METADATA_HEADERS)
    s.responses["thread"] = {"messages": []}
    with pytest.raises(ReadFailure):
        a.get_thread("t1")


def test_malformed_history_cannot_silently_advance_cursor(google):
    a, c, s, *_ = google
    s.responses["history"] = {"historyId": "bad", "history": [{"messagesAdded": [{}]}]}
    with pytest.raises(ReadFailure):
        a.read_history("old")
