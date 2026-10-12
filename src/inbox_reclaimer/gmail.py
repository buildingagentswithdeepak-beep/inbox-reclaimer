"""Gate A Gmail readers. No mutation interface or OAuth setup is exposed.

Only profile_root/google_token.json is read, once. Requested scopes in that file
are NEVER grant evidence: Google's tokeninfo response must validate the actual
access-token scopes and OAuth client. Credentials may refresh in memory; neither
the original token file nor any other profile is written/reloaded. Discovery gets
an unauthenticated transport; only allowlisted read requests receive an access
header. This prevents implicit transport refresh bypassing identity revalidation.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import replace
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable

import httplib2
import requests
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .models import (
    GateClosed,
    HistoryExpired,
    Identity,
    IdentityMismatch,
    Message,
    MissingMessage,
    ReadFailure,
    canonical_digest,
)
from .quota import QuotaLimiter


METADATA_HEADERS = (
    "From",
    "Subject",
    "Message-ID",
    "In-Reply-To",
    "References",
    "List-Unsubscribe",
    "List-Unsubscribe-Post",
)
# Deliberately explicit; gmail.send/metadata and unrelated Workspace grants do
# not become general Gmail read capability through substring/prefix matching.
READ_SCOPES = frozenset(
    {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://mail.google.com/",
    }
)
READ_ACTIONS = frozenset({"read", "analyze", "propose"})


def _action(action):
    if action not in READ_ACTIONS:
        raise GateClosed("Gate A permits analysis and proposals only; mutations are unavailable")


def _copy(message):
    return replace(message, headers=dict(message.headers))


class FakeGmailAdapter:
    """Deterministic in-memory fixture. Tests may explicitly edit messages/history.

    Edits are fixture controls, not Gmail write methods. The base fake represents
    a static snapshot with an empty history feed; race tests override read_history.
    """

    def __init__(
        self, messages: Iterable[Message], identity: Identity | None = None, *, page_size: int = 500
    ):
        if type(page_size) is not int or not 1 <= page_size <= 500:
            raise ValueError("Page size must be between 1 and 500")
        self.messages = {m.id: _copy(m) for m in messages}
        self.identity = identity or Identity("fixture@example.invalid", "fake-client")
        self.page_size = page_size

    def resolve_identity(self) -> Identity:
        return self.identity

    def validate_capability(self, action):
        _action(action)

    def history_boundary(self) -> str:
        rows = [
            dict(
                id=m.id,
                thread=m.thread_id,
                date=m.internal_date,
                size=m.size_estimate,
                labels=sorted(m.labels),
                sender=m.raw_from,
                subject=m.subject,
                headers=m.headers,
                valid=m.valid,
            )
            for m in sorted(self.messages.values(), key=lambda m: m.id)
        ]
        return "fake-" + canonical_digest({"messages": rows})

    def list_message_ids(self, page_token=None) -> dict:
        try:
            offset = 0 if page_token is None else int(page_token)
            if offset < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise ReadFailure("Invalid fixture page token") from None
        ids = sorted(self.messages)
        end = offset + self.page_size
        return {"ids": ids[offset:end], "next_page_token": str(end) if end < len(ids) else None}

    def get_metadata(self, message_id) -> Message:
        if message_id not in self.messages:
            raise MissingMessage("Message is absent in fixture")
        return _copy(self.messages[message_id])

    def get_thread(self, thread_id) -> list[Message]:
        return [
            _copy(m) for m in sorted(self.messages.values(), key=lambda m: m.id) if m.thread_id == thread_id
        ]

    def read_history(self, start_history_id, page_token=None) -> dict:
        if page_token is not None:
            raise ReadFailure("Static fixture history has no further pages")
        return dict(
            affected_ids=[],
            deleted_ids=[],
            thread_ids=[],
            unknown_threads=False,
            next_page_token=None,
            history_id=self.history_boundary(),
        )


class GoogleReadAdapter:
    def __init__(
        self,
        profile_root: Path,
        quota=None,
        *,
        max_attempts: int = 4,
        sleep=time.sleep,
        jitter=random.uniform,
        timeout: float = 30,
        wall_clock=time.time,
    ):
        if type(max_attempts) is not int or max_attempts < 1 or timeout <= 0:
            raise ValueError("Invalid read retry or timeout configuration")
        self.profile_root = Path(profile_root).resolve()
        self.quota = quota if quota is not None else QuotaLimiter()
        self.max_attempts, self.sleep, self.jitter = max_attempts, sleep, jitter
        self.timeout, self.wall_clock = timeout, wall_clock
        self._bound: Identity | None = None
        self._verified_token = None
        self._grants = frozenset()
        self._token_email = None
        try:
            # No client-secret file or alternative-profile search. Never persist a
            # refresh. JSON errors and OS errors can contain secrets/paths.
            data = json.loads((Path(profile_root) / "google_token.json").read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or not isinstance(data.get("client_id"), str)
                or not data["client_id"].strip()
            ):
                raise ValueError
            self._client_id = data["client_id"]
            self._credentials = Credentials.from_authorized_user_info(data)
            self._service = build(
                "gmail",
                "v1",
                http=httplib2.Http(timeout=timeout),
                cache_discovery=False,
                static_discovery=True,
            )
        except Exception:
            raise ReadFailure("Cannot load this profile's Google credentials or read adapter") from None

    def validate_capability(self, action):
        _action(action)  # A denied action must never trigger even an auth request.
        self.resolve_identity()

    def _ensure_grants(self):
        creds = self._credentials
        if creds.client_id != self._client_id:
            raise IdentityMismatch("OAuth client changed during this session")
        if not creds.valid or creds.expired:
            self._verified_token = None
            self._grants = frozenset()
            self._token_email = None
            try:
                creds.refresh(AuthRequest())
            except Exception:
                raise ReadFailure("Google credential refresh failed") from None
        if not isinstance(creds.token, str) or not creds.token:
            raise GateClosed("Missing verifiable Google access token")
        if creds.token == self._verified_token:
            return
        # Clear previous grants BEFORE verification so failure cannot preserve an
        # old capability for a new token. Never use credentials.scopes here.
        self._grants = frozenset()
        self._verified_token = None
        self._token_email = None
        info = None
        for attempt in range(self.max_attempts):
            try:
                response = requests.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"access_token": creds.token},
                    timeout=self.timeout,
                    allow_redirects=False,
                )
                response.raise_for_status()
                info = response.json()
                break
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if attempt + 1 < self.max_attempts and (
                    status == 429
                    or status in (500, 502, 503, 504)
                    or isinstance(exc, (requests.Timeout, requests.ConnectionError))
                ):
                    headers = getattr(getattr(exc, "response", None), "headers", {})
                    self.sleep(max(self._retry_after(headers), self.jitter(0, min(60, 2**attempt))))
                    continue
                raise GateClosed("Cannot verify actual Google access-token grants") from None
        if not isinstance(info, dict):
            raise GateClosed("Unknown Google grant metadata")
        audiences = [info[k] for k in ("aud", "audience", "issued_to", "azp") if k in info]
        if not audiences or any(a != self._client_id for a in audiences):
            raise IdentityMismatch("Google access token has a different or unknown OAuth client")
        scopes = info.get("scope")
        if not isinstance(scopes, str) or not READ_SCOPES.intersection(scopes.split()):
            raise GateClosed("Actual granted scopes do not establish Gmail read capability")
        if "email" in info:
            if not isinstance(info["email"], str) or "@" not in info["email"]:
                raise IdentityMismatch("Ambiguous access-token account identity")
            self._token_email = info["email"]
        self._grants = frozenset(scopes.split())
        self._verified_token = creds.token

    def resolve_identity(self) -> Identity:
        data = self._read("profile", lambda: self._service.users().getProfile(userId="me"))
        if not isinstance(data, dict):
            raise IdentityMismatch("Missing Gmail profile identity")
        email = data.get("emailAddress")
        if not isinstance(email, str) or email != email.strip() or email.count("@") != 1:
            raise IdentityMismatch("Missing or ambiguous Gmail profile identity")
        identity = Identity(email, self._client_id)
        if self._token_email is not None and identity.email != self._token_email:
            raise IdentityMismatch("Google grant and Gmail profile accounts differ")
        if self._bound is not None and identity != self._bound:
            raise IdentityMismatch("Gmail account changed during this session")
        self._bound = identity
        self._last_profile = data
        return identity

    def history_boundary(self) -> str:
        self.resolve_identity()
        history_id = self._last_profile.get("historyId")
        if not isinstance(history_id, str) or not history_id:
            raise ReadFailure("Gmail profile lacks a history boundary")
        return history_id

    def _retry_after(self, headers):
        value = headers.get("retry-after") or headers.get("Retry-After")
        if value is None:
            return 0
        try:
            return max(0.0, float(value))
        except (ValueError, TypeError):
            try:
                return max(0.0, parsedate_to_datetime(value).timestamp() - self.wall_clock())
            except (ValueError, TypeError, OverflowError):
                return 0

    @staticmethod
    def _retryable(exc, status):
        if status == 429 or status in (500, 502, 503, 504):
            return True
        if status == 403:
            try:
                reasons = {
                    e.get("reason") for e in json.loads(exc.content).get("error", {}).get("errors", [])
                }
                return bool(reasons & {"rateLimitExceeded", "userRateLimitExceeded", "backendError"})
            except (ValueError, TypeError, AttributeError):
                return False
        return status is None and isinstance(
            exc, (OSError, TimeoutError, requests.RequestException, httplib2.HttpLib2Error)
        )

    def _read(self, method, request_factory):
        for attempt in range(self.max_attempts):
            # Binding is rechecked before every read AND every retry. A refreshed
            # token cannot reach metadata before tokeninfo + getProfile validation.
            if method == "profile":
                self._ensure_grants()
            else:
                self.resolve_identity()
            self.quota.acquire(method, priority=method in {"profile", "history", "thread"})
            try:
                request = request_factory()
                request.headers["authorization"] = "Bearer " + self._credentials.token
                result = request.execute(num_retries=0)
                if not isinstance(result, dict):
                    raise ReadFailure("Malformed Gmail read response")
                return result
            except Exception as exc:
                status = getattr(getattr(exc, "resp", None), "status", None)
                if status == 404 and method in {"get", "thread"}:
                    raise MissingMessage("Requested Gmail record is absent") from None
                if status == 404 and method == "history":
                    raise HistoryExpired("Gmail history expired; full resynchronization required") from None
                if attempt + 1 < self.max_attempts and self._retryable(exc, status):
                    delay = max(
                        self._retry_after(getattr(exc, "resp", {}) or {}), self.jitter(0, min(60, 2**attempt))
                    )
                    if delay > 0:
                        self.sleep(delay)
                    continue
                raise ReadFailure("Gmail read failed; no inventory cursor advanced") from None
        raise ReadFailure("Read retry budget exhausted")

    @staticmethod
    def _page_token(data):
        token = data.get("nextPageToken")
        if token is not None and (not isinstance(token, str) or not token):
            raise ReadFailure("Malformed Gmail page token")
        return token

    def list_message_ids(self, page_token=None) -> dict:
        kwargs = dict(userId="me", maxResults=500, includeSpamTrash=True)
        if page_token is not None:
            kwargs["pageToken"] = page_token
        data = self._read("list", lambda: self._service.users().messages().list(**kwargs))
        rows = data.get("messages", [])
        if not isinstance(rows, list) or any(
            not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"] for m in rows
        ):
            raise ReadFailure("Malformed Gmail message enumeration")
        return {"ids": [m["id"] for m in rows], "next_page_token": self._page_token(data)}

    @staticmethod
    def _message(data):
        if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not data["id"]:
            raise ReadFailure("Missing Gmail message identity")
        valid = True
        thread = data.get("threadId")
        if not isinstance(thread, str) or not thread:
            thread, valid = "", False

        def number(value):
            nonlocal valid
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                valid = False
                return None
            try:
                n = int(value)
                if n < 0:
                    raise ValueError
                return n
            except (ValueError, TypeError):
                valid = False
                return None

        date, size = number(data.get("internalDate")), number(data.get("sizeEstimate"))
        labels = data.get("labelIds")
        if not isinstance(labels, list) or any(not isinstance(x, str) or not x for x in labels):
            labels, valid = [], False
        payload = data.get("payload")
        rows = payload.get("headers", []) if isinstance(payload, dict) else []
        headers = {}
        if not isinstance(rows, list):
            rows, valid = [], False
        for h in rows:
            if (
                not isinstance(h, dict)
                or not isinstance(h.get("name"), str)
                or not isinstance(h.get("value"), str)
            ):
                valid = False
                continue
            key = h["name"].lower()
            if key in headers:
                valid = False  # Ambiguous important metadata fails closed.
            headers[key] = h["value"]
        sender = headers.get("from", "")
        if not sender:
            valid = False
        return Message(
            data["id"], thread, date, size, frozenset(labels), sender, headers.get("subject"), headers, valid
        )

    def get_metadata(self, message_id) -> Message:
        data = self._read(
            "get",
            lambda: self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata", metadataHeaders=list(METADATA_HEADERS)),
        )
        message = self._message(data)
        if message.id != message_id:
            raise ReadFailure("Gmail metadata response identity mismatch")
        return message

    def get_thread(self, thread_id) -> list[Message]:
        data = self._read(
            "thread",
            lambda: self._service.users()
            .threads()
            .get(userId="me", id=thread_id, format="metadata", metadataHeaders=list(METADATA_HEADERS)),
        )
        rows = data.get("messages")
        if not isinstance(rows, list) or not rows:
            raise ReadFailure("Missing Gmail thread coverage")
        messages = [self._message(m) for m in rows]
        if any(m.thread_id != thread_id for m in messages):
            raise ReadFailure("Gmail thread response identity mismatch")
        return messages

    def read_history(self, start_history_id, page_token=None) -> dict:
        kwargs = dict(userId="me", startHistoryId=start_history_id, maxResults=500)
        if page_token is not None:
            kwargs["pageToken"] = page_token
        data = self._read("history", lambda: self._service.users().history().list(**kwargs))
        cursor = data.get("historyId")
        if not isinstance(cursor, str) or not cursor:
            raise ReadFailure("Missing Gmail history cursor")
        rows = data.get("history", [])
        if not isinstance(rows, list):
            raise ReadFailure("Malformed Gmail history coverage")
        affected, deleted, threads, unknown = set(), set(), set(), False
        for row in rows:
            if not isinstance(row, dict):
                raise ReadFailure("Malformed Gmail history record")
            # Generic messages can supplement but never replace structured events.
            for field in ("messages", "messagesAdded", "messagesDeleted", "labelsAdded", "labelsRemoved"):
                events = row.get(field, [])
                if not isinstance(events, list):
                    raise ReadFailure("Malformed Gmail history events")
                for event in events:
                    if not isinstance(event, dict):
                        raise ReadFailure("Malformed Gmail history event")
                    m = event if field == "messages" else event.get("message")
                    if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"]:
                        raise ReadFailure("History event lacks message identity")
                    (deleted if field == "messagesDeleted" else affected).add(m["id"])
                    thread = m.get("threadId")
                    if isinstance(thread, str) and thread:
                        threads.add(thread)
                    else:
                        unknown = True
        return dict(
            affected_ids=sorted(affected),
            deleted_ids=sorted(deleted),
            thread_ids=sorted(threads),
            unknown_threads=unknown,
            next_page_token=self._page_token(data),
            history_id=cursor,
        )
