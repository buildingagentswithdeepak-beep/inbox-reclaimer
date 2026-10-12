"""Bounded targeted selection; Gmail search is never an eligibility decision."""

from dataclasses import dataclass, replace
from uuid import uuid4

from ..analytics import parse_sender
from ..models import IdentityMismatch, Message, MissingMessage, ReadFailure
from ..proposals import PROTECTED_LABELS, _valid_message, check_protection
from .models import SenderPlan, exact_sender


@dataclass(frozen=True)
class SenderSelection:
    sender: str
    max_messages: int
    examined_count: int
    exhausted: bool
    plan: SenderPlan | None
    messages: tuple[Message, ...]
    skips: dict[str, str]


def select_sender(adapter, journal, identity, sender, max_messages=1000, redact_subjects=True):
    sender = exact_sender(sender)
    if type(max_messages) is not int or not 1 <= max_messages <= 1000:
        raise ValueError("Sender candidate limit must be in 1..1000")

    def check_identity():
        if adapter.resolve_identity() != identity:
            raise IdentityMismatch("Account changed during sender selection")

    check_identity()
    adapter.validate_capability("analyze")
    seen, messages, skips, tokens = set(), {}, {}, set()
    token = None
    exhausted = False
    while len(seen) < max_messages:
        check_identity()
        page = adapter.list_sender_ids(
            sender, page_token=token, max_results=min(500, max_messages - len(seen))
        )
        check_identity()
        if not isinstance(page, dict) or not isinstance(page.get("ids"), list):
            raise ReadFailure("Malformed sender enumeration")
        ids = page["ids"]
        if any(not isinstance(id, str) or not id for id in ids):
            raise ReadFailure("Malformed sender enumeration")
        next_token = page.get("next_page_token")
        if next_token is not None and (
            not isinstance(next_token, str) or not next_token or next_token in tokens
        ):
            raise ReadFailure("Repeated or invalid sender page token")
        for id in ids:
            if id in seen:
                continue
            if len(seen) == max_messages:
                break
            seen.add(id)
            check_identity()
            try:
                message = adapter.get_metadata(id)
                check_identity()
                if not _valid_message(message) or message.id != id:
                    skips[id] = "malformed_metadata"
                    continue
                if parse_sender(message.raw_from) != sender:
                    skips[id] = "sender_mismatch"
                    continue
                if message.labels & PROTECTED_LABELS:
                    skips[id] = "protected_label"
                    continue
                protected = journal.protections(identity.account_id)
                if sender in protected:
                    skips[id] = "protected_sender"
                    continue
                thread = adapter.get_thread(message.thread_id)
                check_identity()
                if not isinstance(thread, (list, tuple)):
                    skips[id] = "invalid_thread_read"
                    continue
                reason = check_protection(message, thread, journal.protections(identity.account_id))
                current = next((m for m in thread if isinstance(m, Message) and m.id == id), None)
                reason = reason or check_protection(current, thread, journal.protections(identity.account_id))
                if reason:
                    skips[id] = reason
                    continue
                if parse_sender(current.raw_from) != sender or current.thread_id != message.thread_id:
                    skips[id] = "sender_or_thread_changed"
                    continue
                if redact_subjects:
                    current = replace(
                        current,
                        subject=None,
                        headers={k: v for k, v in current.headers.items() if k.lower() != "subject"},
                    )
                messages[id] = current
            except IdentityMismatch:
                raise
            except MissingMessage:
                skips[id] = "missing"
            except ReadFailure:
                skips[id] = "required_read_failed"
            check_identity()
        exhausted = next_token is None and all(id in seen for id in ids)
        if next_token is None or len(seen) == max_messages:
            break
        tokens.add(next_token)
        token = next_token
    check_identity()
    if sender in journal.protections(identity.account_id):
        skips.update({id: "protected_sender" for id in messages})
        messages.clear()
    ordered = tuple(messages[id] for id in sorted(messages))
    plan = SenderPlan(identity.account_id, uuid4().hex, sender, tuple(sorted(messages))) if messages else None
    return SenderSelection(sender, max_messages, len(seen), exhausted, plan, ordered, skips)
