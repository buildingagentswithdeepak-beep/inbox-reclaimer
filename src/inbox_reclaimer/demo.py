"""Explicitly synthetic offline mailbox, never a substitute for live Gmail evidence."""

from datetime import datetime, timezone

from .models import Identity, Message

DEMO_IDENTITY = Identity("receiver@example.test", "offline-fixture-client")
DEMO_CUTOFF = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def demo_messages() -> list[Message]:
    old = int(datetime(2020, 2, 29, 9, tzinfo=timezone.utc).timestamp() * 1000)
    recent = int(datetime(2026, 8, 30, 9, tzinfo=timezone.utc).timestamp() * 1000)
    rows = []
    for index in range(30):
        labels = {"INBOX", "UNREAD", "CATEGORY_PROMOTIONS"}
        if index in {2, 3}:
            labels.add("CATEGORY_UPDATES")
        if index == 0:
            labels.add("STARRED")
        if index == 1:
            labels.add("IMPORTANT")
        rows.append(
            Message(
                id=f"newsletter-{index:03d}",
                thread_id=f"thread-{index:03d}",
                internal_date=old,
                size_estimate=(index + 1) * 1_000_000,
                labels=frozenset(labels),
                raw_from="The Weekly Dispatch <newsletter@example.test>",
                subject=f"Synthetic newsletter edition {index + 1}",
                headers={
                    "list-unsubscribe": "<mailto:leave@example.test>",
                    "message-id": f"<{index}@example.test>",
                },
            )
        )
    rows.extend(
        [
            Message(
                "conversation-in",
                "replied",
                old,
                40_000_000,
                frozenset({"INBOX"}),
                "Partner <partner@example.test>",
                "Protected conversation",
            ),
            Message(
                "conversation-sent",
                "replied",
                old,
                1_000_000,
                frozenset({"SENT"}),
                "Receiver <receiver@example.test>",
                "Synthetic sent evidence",
            ),
            Message(
                "existing-trash",
                "trash-thread",
                old,
                60_000_000,
                frozenset({"TRASH"}),
                "archive@example.test",
                "Pre-existing Trash: never eligible",
            ),
            Message(
                "spam",
                "spam-thread",
                old,
                20_000_000,
                frozenset({"SPAM"}),
                "offers@example.test",
                "Spam is counted separately",
            ),
            Message(
                "draft",
                "draft-thread",
                old,
                30_000_000,
                frozenset({"DRAFT"}),
                "receiver@example.test",
                "Protected draft",
            ),
            Message(
                "recent",
                "recent-thread",
                recent,
                500_000,
                frozenset({"INBOX", "CATEGORY_SOCIAL"}),
                "Community <community@example.test>",
                "Recent social update",
            ),
            Message(
                "unknown",
                "unknown-thread",
                recent,
                100_000,
                frozenset({"CATEGORY_FORUMS"}),
                "malformed sender",
                '<script>alert("fixture")</script>\x1b[31m',
            ),
        ]
    )
    return rows
