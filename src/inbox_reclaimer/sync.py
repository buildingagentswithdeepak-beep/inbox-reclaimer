"""Staged read-only metadata synchronization; publication is the commit point.

The working generation lives in memory; publication leaves the old cursor intact
on failure. The CLI composes ResumableReadAdapter for a durable full-scan baseline
and original H0, while incremental restarts replay the committed cursor. Callers
hold the profile's OS account lock for cross-process serialization.
Thread invalidations precede publication: a crash can over-invalidate, never leave
an old positive protection observation trusted for a new generation.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from .models import HistoryExpired, IdentityMismatch, Inventory, Message, MissingMessage, ReadFailure


class SyncCancelled(ReadFailure):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


class SyncService:
    def __init__(
        self,
        adapter,
        cache,
        redact_subjects: bool = False,
        *,
        max_history_restarts: int = 1,
        cancelled: Callable[[], bool] | None = None,
        progress: Callable[[dict], None] | None = None,
    ):
        if type(max_history_restarts) is not int or max_history_restarts < 0:
            raise ValueError("History restart bound must be a nonnegative integer")
        self.adapter, self.cache = adapter, cache
        self.redact_subjects = redact_subjects
        self.max_history_restarts = max_history_restarts
        self.cancelled = cancelled or (lambda: False)
        self.progress = progress or (lambda event: None)

    def _check(self):
        if self.cancelled():
            raise SyncCancelled("Analysis cancelled; committed inventory is unchanged")

    def _emit(self, phase, **counts):
        self.progress({"phase": phase, **counts})
        self._check()

    def _identity(self, expected=None):
        self._check()
        identity = self.adapter.resolve_identity()
        if expected is not None and identity != expected:
            raise IdentityMismatch("Account changed during synchronization")
        return identity

    def _clean(self, message):
        if self.redact_subjects:
            return replace(
                message,
                subject=None,
                headers={k: v for k, v in message.headers.items() if k.lower() != "subject"},
            )
        return replace(message, headers=dict(message.headers))

    def _fetch(self, id, staged, unresolved):
        self._check()
        try:
            message = self.adapter.get_metadata(id)
        except MissingMessage:
            staged.pop(id, None)
            unresolved.add(id)
            return None
        if not isinstance(message, Message) or message.id != id:
            raise ReadFailure("Metadata response did not match requested message")
        staged[id] = self._clean(message)
        if not message.valid:
            unresolved.add(id)
        else:
            unresolved.discard(id)
        return message

    @staticmethod
    def _cursor(value):
        if not isinstance(value, str) or not value:
            raise ReadFailure("Missing history cursor; inventory not published")
        return value

    def limited_scan(self, max_messages: int) -> Inventory:
        """Read a bounded listing-order preview without touching cache or history.

        Gmail exposes no sort contract. Selection follows list order, not a
        guaranteed global newest-N ordering. Missing records consume a slot.
        """
        from .models import LimitedInventory

        if type(max_messages) is not int or max_messages < 1:
            raise ValueError("Message limit must be a positive integer")
        identity = self._identity()
        self.adapter.validate_capability("analyze")
        started = _now()
        staged, unresolved, selected = {}, set(), set()
        token, tokens = None, set()
        exhausted = False
        self._emit("start", fetched=0, limit=max_messages)
        while len(selected) < max_messages:
            self._identity(identity)
            page = self.adapter.list_message_ids(page_token=token)
            self._identity(identity)
            if not isinstance(page, dict):
                raise ReadFailure("Malformed enumeration page")
            ids = page.get("ids")
            if not isinstance(ids, list) or any(not isinstance(id, str) or not id for id in ids):
                raise ReadFailure("Malformed enumeration page")
            next_token = page.get("next_page_token")
            if next_token is not None and (
                not isinstance(next_token, str) or not next_token or next_token in tokens
            ):
                raise ReadFailure("Repeated or invalid enumeration page token")
            for id in ids:
                if id in selected:
                    continue
                if len(selected) == max_messages:
                    break
                self._identity(identity)
                selected.add(id)
                self._fetch(id, staged, unresolved)
                self._identity(identity)
                self._emit(
                    "metadata", fetched=len(selected), unresolved=len(unresolved), limit=max_messages
                )
            exhausted = next_token is None and all(id in selected for id in ids)
            if next_token is None or len(selected) == max_messages:
                break
            tokens.add(next_token)
            token = next_token
        self._identity(identity)
        # Sorting only the selected records does not establish global recency.
        messages = sorted(
            staged.values(),
            key=lambda m: (-(m.internal_date if type(m.internal_date) is int else -1), m.id),
        )
        return LimitedInventory(
            account_id=identity.account_id,
            generation=uuid4().hex,
            cursor="",
            started_at=started,
            completed_at=_now(),
            complete=False,
            unresolved=tuple(sorted(unresolved)),
            messages=tuple(messages),
            message_limit=max_messages,
            selected_count=len(selected),
            enumeration_exhausted=exhausted,
        )

    def full_sync(self) -> Inventory:
        identity = self._identity()
        self.adapter.validate_capability("analyze")
        return self._full_with_restarts(identity)

    def _full_with_restarts(self, identity):
        for attempt in range(self.max_history_restarts + 1):
            try:
                self._identity(identity)
                started = _now()
                h0 = self._cursor(self.adapter.history_boundary())
                started = getattr(self.adapter, "scan_started_at", None) or started
                staged, unresolved, seen_ids = {}, set(), set()
                self._emit("start", fetched=0)
                token, tokens = None, set()
                while True:
                    self._check()
                    page = self.adapter.list_message_ids(page_token=token)
                    ids = page.get("ids")
                    if not isinstance(ids, list) or any(not isinstance(id, str) or not id for id in ids):
                        raise ReadFailure("Malformed enumeration page")
                    for id in ids:
                        if id not in seen_ids:
                            seen_ids.add(id)
                            self._fetch(id, staged, unresolved)
                            self._emit("metadata", fetched=len(seen_ids), unresolved=len(unresolved))
                    token = page.get("next_page_token")
                    if not token:
                        break
                    if not isinstance(token, str) or token in tokens:
                        raise ReadFailure("Repeated or invalid enumeration page token")
                    tokens.add(token)
                return self._replay_publish(identity, started, h0, staged, unresolved, full=True)
            except HistoryExpired:
                if attempt == self.max_history_restarts:
                    raise
                self._emit("history_restart", attempt=attempt + 1)
        raise AssertionError("unreachable")

    def incremental_sync(self) -> Inventory:
        identity = self._identity()
        self.adapter.validate_capability("analyze")
        previous = self.cache.load(identity.account_id)
        if previous is None or not previous.complete:
            return self._full_with_restarts(identity)
        if previous.account_id != identity.account_id:
            raise IdentityMismatch("Cache belongs to a different account")
        try:
            return self._replay_publish(
                identity,
                _now(),
                self._cursor(previous.cursor),
                {m.id: self._clean(m) for m in previous.messages},
                set(previous.unresolved),
                full=False,
            )
        except HistoryExpired:
            return self._full_with_restarts(identity)

    def _replay_publish(self, identity, started, h0, staged, unresolved, *, full):
        affected, deleted, threads = set(), set(), set()
        unknown = full  # A full rebuild can remove rows absent from both scan and history.
        token, tokens, pages = None, set(), 0
        while True:
            self._check()
            page = self.adapter.read_history(h0, page_token=token)
            for key, target in [
                ("affected_ids", affected),
                ("deleted_ids", deleted),
                ("thread_ids", threads),
            ]:
                values = page.get(key)
                if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                    raise ReadFailure("Malformed history page")
                target.update(values)
            if not isinstance(page.get("unknown_threads"), bool):
                raise ReadFailure("Missing history coverage information")
            unknown |= page["unknown_threads"]
            h1 = self._cursor(page.get("history_id"))
            pages += 1
            self._emit("history", pages=pages, affected=len(affected), deleted=len(deleted))
            token = page.get("next_page_token")
            if not token:
                break
            if not isinstance(token, str) or token in tokens:
                raise ReadFailure("Repeated or invalid history page token")
            tokens.add(token)
        # Replay all pages before refresh so each affected ID is fetched only once.
        for id in sorted(affected | deleted):
            old = staged.get(id)
            if old and old.thread_id:
                threads.add(old.thread_id)
            if id in deleted:
                staged.pop(id, None)
                unresolved.discard(id)  # History confirms absence, never tool attribution.
                if not old:
                    unknown = True
                continue
            message = self._fetch(id, staged, unresolved)
            if message and message.thread_id:
                threads.add(message.thread_id)
            else:
                unknown = True
        self._identity(identity)
        self._emit("publishing", messages=len(staged), unresolved=len(unresolved))
        # Required before commit. Separate invalidation calls are intentionally
        # conservative; CacheStore's publish atomically swaps rows and cursor.
        if unknown:
            self.cache.invalidate_thread(identity.account_id)
        for thread in sorted(threads):
            self.cache.invalidate_thread(identity.account_id, thread)
        self._identity(identity)
        inventory = Inventory(
            identity.account_id,
            uuid4().hex,
            h1,
            started,
            _now(),
            not unresolved,
            tuple(sorted(unresolved)),
            tuple(self._clean(staged[id]) for id in sorted(staged)),
        )
        self._check()
        self.cache.publish(inventory)
        return inventory
