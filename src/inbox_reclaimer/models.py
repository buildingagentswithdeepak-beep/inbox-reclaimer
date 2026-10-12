"""Account-bound immutable contracts shared by the read-only release."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


class ReclaimError(Exception):
    """A classified error whose message is safe to display locally."""


class GateClosed(ReclaimError):
    pass


class IdentityMismatch(ReclaimError):
    pass


class IncompleteInventory(ReclaimError):
    pass


class MissingMessage(ReclaimError):
    pass


class HistoryExpired(ReclaimError):
    pass


class ReadFailure(ReclaimError):
    pass


def canonical_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Identity:
    email: str
    oauth_client_id: str
    subject: str | None = None

    def __post_init__(self):
        if not self.email or "@" not in self.email or not self.oauth_client_id:
            raise IdentityMismatch("Missing or ambiguous account identity")

    @property
    def account_id(self) -> str:
        return canonical_digest(
            {"email": self.email, "oauth_client_id": self.oauth_client_id, "subject": self.subject}
        )


@dataclass(frozen=True)
class Message:
    id: str
    thread_id: str
    internal_date: int | None
    size_estimate: int | None
    labels: frozenset[str]
    raw_from: str
    subject: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    valid: bool = True


@dataclass(frozen=True)
class Inventory:
    account_id: str
    generation: str
    cursor: str
    started_at: str
    completed_at: str
    complete: bool
    unresolved: tuple[str, ...]
    messages: tuple[Message, ...]


@dataclass(frozen=True)
class LimitedInventory(Inventory):
    """Transient, unreconciled preview; never valid for full-cache publication."""

    message_limit: int
    selected_count: int
    enumeration_exhausted: bool


@dataclass(frozen=True)
class Rule:
    rule_id: str
    kind: str
    min_bytes: int = 0
    older_months: int = 0
    category: str | None = None
    sender: str | None = None


@dataclass(frozen=True)
class Batch:
    batch_id: str
    kind: str
    ids: tuple[str, ...]
    estimated_bytes: int
    digest: str
    reasons: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    account_id: str
    plan_id: str
    revision: int
    action: str
    policy_version: str
    inventory_generation: str
    created_at: str
    batches: tuple[Batch, ...]
    status: str = "sealed"
