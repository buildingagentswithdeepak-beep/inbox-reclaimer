"""Synthetic sender reader/writer; never holds credentials or contacts Gmail."""

from dataclasses import replace

from ..analytics import parse_sender
from ..gmail import FakeGmailAdapter
from ..models import GateClosed, ReadFailure
from .models import exact_sender


class DemoSenderAdapter:
    synthetic = True

    def __init__(self, base):
        if not isinstance(base, FakeGmailAdapter):
            raise ValueError("Demo sender adapter requires a synthetic mailbox")
        self.base = base
        self.list_calls = 0
        self.effects = []

    def resolve_identity(self):
        return self.base.resolve_identity()

    def validate_capability(self, action):
        if action not in {"read", "analyze", "propose", "trash", "restore"}:
            raise GateClosed("Synthetic demo supports no permanent deletion")

    def list_sender_ids(self, sender, page_token=None, max_results=500):
        sender = exact_sender(sender)
        if type(max_results) is not int or not 1 <= max_results <= 500:
            raise ValueError("Page size must be in 1..500")
        try:
            offset = 0 if page_token is None else int(page_token)
            if offset < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise ReadFailure("Invalid synthetic page token") from None
        self.list_calls += 1
        ids = sorted(m.id for m in self.base.messages.values() if parse_sender(m.raw_from) == sender)
        end = offset + max_results
        return {"ids": ids[offset:end], "next_page_token": str(end) if end < len(ids) else None}

    def get_metadata(self, message_id):
        return self.base.get_metadata(message_id)

    def get_thread(self, thread_id):
        return self.base.get_thread(thread_id)

    def prepare_write(self, action):
        self.validate_capability("restore" if action in {"untrash", "modify"} else action)

    def trash_ids(self, ids):
        for id in ids:
            m = self.get_metadata(id)
            # Deliberately model loss of INBOX to exercise restore's label repair.
            self.base.messages[id] = replace(m, labels=frozenset((m.labels | {"TRASH"}) - {"INBOX"}))
        self.effects.append(("trash", tuple(ids)))

    def untrash_message(self, message_id):
        m = self.get_metadata(message_id)
        self.base.messages[message_id] = replace(m, labels=frozenset(m.labels - {"TRASH"}))
        self.effects.append(("untrash", message_id))

    def modify_message(self, message_id, add_labels, remove_labels):
        m = self.get_metadata(message_id)
        self.base.messages[message_id] = replace(
            m, labels=frozenset((m.labels | set(add_labels)) - set(remove_labels))
        )
        self.effects.append(("modify", message_id, tuple(add_labels), tuple(remove_labels)))
