"""Exact-sender reads and narrowly scoped, release-gated Gmail mutations.

The wrapped GoogleReadAdapter owns the unauthenticated SDK transport, credentials,
actual grant verification, read retries and bound account. Writes NEVER enter its
retry loop. This module deliberately has no permanent-delete interface.
"""

from __future__ import annotations

from functools import wraps
import re
import threading

from ..gmail import GoogleReadAdapter, READ_ACTIONS
from ..models import GateClosed, IdentityMismatch, ReadFailure, ReclaimError
from .models import exact_sender, require_live_release

MODIFY = "https://www.googleapis.com/auth/gmail.modify"
WRITE_SCOPES = frozenset({MODIFY, "https://mail.google.com/"})
RESTORABLE_SYSTEM_LABELS = frozenset({"INBOX", "UNREAD", "STARRED", "IMPORTANT"})
_WRITE_ACTIONS = {"trash": "trash", "restore": "restore", "untrash": "untrash", "modify": "modify"}


class WriteFailure(ReclaimError):
    """Dispatch may have reached Gmail: reconcile observed state, never blindly retry."""

    ambiguous = True


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ReclaimError("Invalid Gmail record identifier")
    return value


def _write_attempt(method):
    @wraps(method)
    def attempt(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        finally:
            # An invalid call also spends its preparation; no accidental reuse.
            with self._write_lock:
                self._reservation = None
                self._dispatch_guard = None

    return attempt


class GoogleSenderReader:
    def __init__(self, base: GoogleReadAdapter):
        self.base = base

    def resolve_identity(self):
        return self.base.resolve_identity()

    def validate_capability(self, action):
        return self.base.validate_capability(action)

    def get_metadata(self, message_id):
        return self.base.get_metadata(message_id)

    def get_thread(self, thread_id):
        return self.base.get_thread(thread_id)

    def list_sender_ids(self, sender, page_token=None, max_results=500):
        canonical = exact_sender(sender)
        if type(max_results) is not int or not 1 <= max_results <= 500:
            raise ValueError("Page size must be between 1 and 500")
        if page_token is not None and (not isinstance(page_token, str) or not page_token):
            raise ValueError("Invalid Gmail page token")
        kwargs = dict(userId="me", q=f'from:"{canonical}"', includeSpamTrash=True, maxResults=max_results)
        if page_token is not None:
            kwargs["pageToken"] = page_token
        data = self.base._read("list", lambda: self.base._service.users().messages().list(**kwargs))
        rows = data.get("messages", [])
        if (
            not isinstance(rows, list)
            or len(rows) > max_results
            or any(
                not isinstance(row, dict)
                or not isinstance(row.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]+", row["id"])
                for row in rows
            )
        ):
            raise ReadFailure("Malformed sender message enumeration")
        ids = [row["id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ReadFailure("Duplicate identities in sender message enumeration")
        return {"ids": ids, "next_page_token": self.base._page_token(data)}


class GoogleSenderWriter(GoogleSenderReader):
    """One prepared reservation authorizes exactly one attempted SDK mutation.

    Call prepare_write('trash'|'untrash'|'modify'|'restore') BEFORE safety reads.
    A 'restore' reservation permits one untrash OR one label modification, not
    both. Prepare again before each repair step. Preparing abandons any unused
    reservation (without a quota refund), e.g. after a protected message is skipped.
    Account-bound plans, human approval and read-after-write reconciliation remain
    the workflow's responsibility. The closed release gate is not an approval.
    """

    def __init__(self, base: GoogleReadAdapter, *, validation=None):
        if validation is None:
            require_live_release()  # MUST precede even inspecting the supplied adapter.
        else:
            require_live_release(validation)
            validation.check_home(base.profile_root)
            validation.check_ids(validation.ids)
        self.validation = validation
        super().__init__(base)
        self._reservation = None
        self._dispatch_guard = None
        self._custom_labels = frozenset()
        self._write_lock = threading.Lock()

    @staticmethod
    def _operation(action):
        if not isinstance(action, str) or action not in _WRITE_ACTIONS:
            raise GateClosed("Only reversible sender trash and restore operations are supported")
        return _WRITE_ACTIONS[action]

    def validate_capability(self, action):
        if action in READ_ACTIONS:
            return super().validate_capability(action)
        self._operation(action)  # A denied action cannot trigger credential/network use.
        identity = self.resolve_identity()
        if self.validation is not None:
            self.validation.check_home(self.base.profile_root)
            self.validation.check_account(identity)
        # Never credentials.scopes: _grants was verified by tokeninfo for this token.
        if not WRITE_SCOPES.intersection(self.base._grants):
            raise GateClosed("Actual Google grants do not permit Gmail modify")
        if self.base._verified_token != self.base._credentials.token:
            raise GateClosed("Google access-token grants are not current")
        return identity

    def prepare_write(self, action):
        operation = self._operation(action)
        with self._write_lock:
            self._reservation = None
            self._dispatch_guard = None
            self._custom_labels = frozenset()
            try:
                costs = self.base.quota.config.method_costs
                methods = ("untrash", "modify") if operation == "restore" else (operation,)
                if any(type(costs[name]) is not int or costs[name] <= 0 for name in methods):
                    raise ValueError
                method = max(methods, key=lambda name: costs[name])
                charged = self.base.quota.acquire(method, priority=True)
                if type(charged) is not int or charged != costs[method]:
                    raise ValueError
            except Exception:
                raise ReclaimError("Cannot reserve Gmail mutation quota; no write dispatched") from None
            identity = self.validate_capability(action)
            if operation in {"modify", "restore"}:
                self._custom_labels = self._read_custom_labels()
            self._reservation = (operation, identity)

    def set_dispatch_guard(self, callback):
        """Install the executor's one-shot local safety/approval check."""
        with self._write_lock:
            self._dispatch_guard = None
            if not callable(callback):
                raise TypeError("Dispatch guard must be callable")
            self._dispatch_guard = callback

    def _take_reservation(self, operation):
        with self._write_lock:
            reservation, self._reservation = self._reservation, None
            guard, self._dispatch_guard = self._dispatch_guard, None
        if reservation is None or not (
            reservation[0] == operation
            or (reservation[0] == "restore" and operation in {"untrash", "modify"})
        ):
            raise ReclaimError("A matching, unused Gmail mutation reservation is required")
        if guard is None:
            raise ReclaimError("A fresh executor dispatch guard is required")
        return reservation[1], guard

    def _dispatch(self, operation, request_factory, *, message_id=None, labels=None):
        identity, guard = self._take_reservation(operation)  # Spent even on denial or ambiguity.
        if labels:
            self._validate_custom_labels(labels)
        current = self.validate_capability(operation)
        if current != identity:
            raise IdentityMismatch("Gmail account changed after mutation quota reservation")
        creds = self.base._credentials
        if (
            not creds.valid
            or creds.expired
            or creds.token != self.base._verified_token
            or creds.client_id != identity.oauth_client_id
        ):
            raise GateClosed("Google credentials changed before mutation dispatch")
        try:
            # Same unauthenticated transport as the reader. No implicit refresh,
            # no AuthorizedHttp and no SDK/transport retry of ambiguous mutations.
            request = request_factory()
            request.headers["authorization"] = "Bearer " + creds.token
        except Exception:
            raise ReclaimError("Cannot construct Gmail mutation; no write dispatched") from None
        # Final identity/grant reads and request construction may have taken time.
        # No network request or quota wait occurs between this check and dispatch.
        guard()
        if self.validation is not None:
            self.validation.check()
        try:
            result = request.execute(num_retries=0)
            # batchModify has no response schema: the SDK returns b'' for HTTP
            # 200 or '' for HTTP 204. Normalize its acknowledgement only; the
            # executor must still read and verify every message's resulting labels.
            if operation == "trash" and type(result) in (bytes, str) and not result:
                result = {}
            if not isinstance(result, dict) or (message_id is not None and result.get("id") != message_id):
                raise ValueError
            return result
        except Exception:
            raise WriteFailure(
                "Gmail mutation outcome is ambiguous; reconcile message state before any further write"
            ) from None

    @_write_attempt
    def trash_ids(self, ids):
        if self.validation is not None:
            self.validation.check_ids(ids)
        if not isinstance(ids, (list, tuple)) or not 1 <= len(ids) <= 20:
            raise ReclaimError("Sender trash requires between 1 and 20 message IDs")
        ids = [_id(value) for value in ids]
        if len(set(ids)) != len(ids):
            raise ReclaimError("Sender trash IDs must be unique")
        return self._dispatch(
            "trash",
            lambda: self.base._service.users()
            .messages()
            .batchModify(userId="me", body={"ids": ids, "addLabelIds": ["TRASH"]}),
        )

    @_write_attempt
    def untrash_message(self, message_id):
        if self.validation is not None:
            self.validation.check_ids([message_id])
        message_id = _id(message_id)
        return self._dispatch(
            "untrash",
            lambda: self.base._service.users().messages().untrash(userId="me", id=message_id),
            message_id=message_id,
        )

    @staticmethod
    def _label_delta(values):
        if not isinstance(values, (list, tuple, set, frozenset)) or len(values) > 100:
            raise ReclaimError("Invalid restore label delta")
        if any(
            not isinstance(label, str)
            or (label not in RESTORABLE_SYSTEM_LABELS and not re.fullmatch(r"Label_[A-Za-z0-9_-]+", label))
            for label in values
        ):
            raise ReclaimError("Restore may change only supported message and custom labels")
        if len(set(values)) != len(values):
            raise ReclaimError("Restore label delta contains duplicate labels")
        return sorted(values)

    def _read_custom_labels(self):
        # Read before the workflow's safety-read window, not while dispatching a
        # mutation. A label deleted later causes a single-attempt API failure, never
        # label recreation or a retry with the label silently dropped.
        data = self.base._read("list", lambda: self.base._service.users().labels().list(userId="me"))
        rows = data.get("labels")
        if not isinstance(rows, list) or any(
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or row.get("type") not in {"user", "system"}
            for row in rows
        ):
            raise ReclaimError("Cannot verify current Gmail custom labels; no mutation dispatched")
        return frozenset(row["id"] for row in rows if row["type"] == "user")

    def _validate_custom_labels(self, labels):
        custom = {label for label in labels if label.startswith("Label_")}
        if not custom <= self._custom_labels:
            raise ReclaimError("A restore label is missing or deleted; no mutation dispatched")

    @_write_attempt
    def modify_message(self, message_id, add_labels, remove_labels):
        if self.validation is not None:
            self.validation.check_ids([message_id])
        message_id = _id(message_id)
        add, remove = self._label_delta(add_labels), self._label_delta(remove_labels)
        if set(add) & set(remove) or not (add or remove):
            raise ReclaimError("Restore label delta must be nonempty and disjoint")
        # Category, SENT, DRAFT, SPAM and all other unsupported system labels are
        # preserved: there is no full-label-set replacement or implicit removal.
        return self._dispatch(
            "modify",
            lambda: self.base._service.users()
            .messages()
            .modify(userId="me", id=message_id, body={"addLabelIds": add, "removeLabelIds": remove}),
            message_id=message_id,
            labels=add + remove,
        )
