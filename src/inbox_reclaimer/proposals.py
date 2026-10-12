"""Deterministic read-only proposal construction; no approval or mutation surface."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from .analytics import parse_sender, subtract_months
from .models import Batch, IdentityMismatch, IncompleteInventory, Message, Plan, canonical_digest
from .storage import membership_digest

POLICY_VERSION = "gate-a-v1"
PROTECTED_LABELS = frozenset({"STARRED", "IMPORTANT", "SENT", "DRAFT", "TRASH", "SPAM"})
PRIORITY = {"SIZE_AGE": 0, "SENDER_NEWSLETTER": 1, "CATEGORY_AGE": 2}


def _valid_message(m):
    """Unsupported/malformed records cannot establish eligibility or thread safety."""
    return (
        isinstance(m, Message)
        and m.valid is True
        and isinstance(m.id, str)
        and bool(m.id)
        and isinstance(m.thread_id, str)
        and bool(m.thread_id)
        and type(m.internal_date) is int
        and m.internal_date >= 0
        and type(m.size_estimate) is int
        and m.size_estimate >= 0
        and isinstance(m.labels, (set, frozenset))
        and all(isinstance(label, str) and bool(label) for label in m.labels)
        and isinstance(m.headers, dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in m.headers.items())
        and isinstance(m.raw_from, str)
        and bool(parse_sender(m.raw_from))
    )


def check_protection(message, thread_messages, protected_senders):
    """Return an exclusion classification, or None; SENT-thread evidence is a heuristic."""
    if not _valid_message(message):
        return "malformed_metadata"
    if message.labels & PROTECTED_LABELS:
        return "protected_label"
    if parse_sender(message.raw_from) in protected_senders:
        return "protected_sender"
    if not thread_messages or any(
        not _valid_message(m) or m.thread_id != message.thread_id for m in thread_messages
    ):
        return "invalid_thread_read"
    if len({m.id for m in thread_messages}) != len(thread_messages):
        return "ambiguous_thread_read"
    if not any(m.id == message.id for m in thread_messages):
        return "missing_thread_member"
    if any("SENT" in m.labels for m in thread_messages):
        return "sent_thread_heuristic"
    return None


class ProposalService:
    def __init__(self, cache, journal, adapter):
        self.cache = cache
        self.journal = journal
        self.adapter = adapter
        # Local diagnostic IDs/classifications only, never email subjects.
        self.last_skips = {}

    def _identity(self, expected):
        actual = self.adapter.resolve_identity()
        if actual != expected:
            raise IdentityMismatch("Adapter account changed while constructing proposal")

    @staticmethod
    def _rules(rules, cutoff):
        if not isinstance(cutoff, datetime) or cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("Proposal cutoff must have an explicit timezone")
        rules = list(rules)
        if len({r.rule_id for r in rules}) != len(rules):
            raise ValueError("Rule IDs must be unique")
        for r in rules:
            if not isinstance(r.rule_id, str) or not r.rule_id or r.kind not in PRIORITY:
                raise ValueError("Unsupported rule kind or empty rule ID")
            if type(r.min_bytes) is not int or r.min_bytes < 0:
                raise ValueError("min_bytes must be a nonnegative integer")
            if type(r.older_months) is not int or r.older_months < 0:
                raise ValueError("older_months must be a nonnegative integer")
            if r.kind == "CATEGORY_AGE" and (not r.category or not r.category.startswith("CATEGORY_")):
                raise ValueError("Category rules require a Gmail CATEGORY_ label")
            if r.sender is not None and not parse_sender(r.sender):
                raise ValueError("Rule sender must parse unambiguously")
        return sorted(rules, key=lambda r: (PRIORITY[r.kind], r.rule_id))

    @staticmethod
    def _matches(message, rule, cutoff):
        if message.size_estimate <= rule.min_bytes:
            return False
        if rule.older_months:
            boundary_ms = int(subtract_months(cutoff, rule.older_months).timestamp() * 1000)
            if message.internal_date >= boundary_ms:
                return False
        elif message.internal_date > int(cutoff.timestamp() * 1000):
            return False
        if rule.sender and parse_sender(message.raw_from) != parse_sender(rule.sender):
            return False
        if rule.kind == "SENDER_NEWSLETTER":
            return bool(message.headers.get("list-unsubscribe", "").strip())
        if rule.kind == "CATEGORY_AGE":
            return rule.category in message.labels
        return True

    def build_revision(
        self, identity, rules, cutoff, min_batch_bytes=100_000_000, max_batch_messages=100, plan_id=None
    ):
        rules = self._rules(rules, cutoff)
        if type(min_batch_bytes) is not int or min_batch_bytes < 0:
            raise ValueError("min_batch_bytes must be a nonnegative integer")
        if type(max_batch_messages) is not int or not 1 <= max_batch_messages <= 1000:
            raise ValueError("max_batch_messages must be in 1..1000")
        self.last_skips = {}
        self._identity(identity)
        self.journal.bind_account(identity)
        inv = self.cache.load(identity.account_id)
        if inv is None or not inv.complete or inv.unresolved:
            raise IncompleteInventory("A complete, resolved published inventory is required")
        if plan_id is not None:
            prior = [p for p in self.journal.plans(identity.account_id) if p.plan_id == plan_id]
            if not prior:
                raise KeyError("New revision requires an existing plan ID")
            revision = max(p.revision for p in prior) + 1
        else:
            plan_id = uuid4().hex
            revision = 1
        protected = self.journal.protections(identity.account_id)
        threads = {}
        assigned = defaultdict(list)
        reasons = {}
        for cached in sorted(inv.messages, key=lambda m: m.id):
            if not _valid_message(cached):
                self.last_skips[cached.id] = "malformed_metadata"
                continue
            if cached.labels & PROTECTED_LABELS or parse_sender(cached.raw_from) in protected:
                self.last_skips[cached.id] = "cached_protection"
                continue
            if not any(self._matches(cached, rule, cutoff) for rule in rules):
                continue
            if cached.thread_id not in threads:
                try:
                    self._identity(identity)
                    threads[cached.thread_id] = list(self.adapter.get_thread(cached.thread_id))
                except IdentityMismatch:
                    raise
                except Exception:
                    # Only a successful, complete safety read can create candidates.
                    threads[cached.thread_id] = []
            thread = threads[cached.thread_id]
            current = next((m for m in thread if isinstance(m, Message) and m.id == cached.id), None)
            # Re-read protections to incorporate additions while the build is in progress.
            protected = self.journal.protections(identity.account_id)
            exclusion = check_protection(current, thread, protected)
            if exclusion is not None:
                self.last_skips[cached.id] = exclusion
                continue
            if current.thread_id != cached.thread_id:
                self.last_skips[cached.id] = "changed_thread"
                continue
            matches = [r for r in rules if self._matches(current, r, cutoff)]
            if not matches:
                self.last_skips[cached.id] = "no_longer_matches"
                continue
            owner = matches[0]
            # Newsletter proposals remain sender-bounded even for a wildcard rule.
            group = (
                PRIORITY[owner.kind],
                owner.rule_id,
                owner.kind,
                parse_sender(current.raw_from) if owner.kind == "SENDER_NEWSLETTER" else "",
            )
            assigned[group].append(current)
            reasons[current.id] = [r.rule_id for r in matches]
        self._identity(identity)
        # The final protection read narrows already-assigned IDs; it never reassigns them.
        protected = self.journal.protections(identity.account_id)
        batches = []
        for group, members in sorted(assigned.items()):
            members = [m for m in members if parse_sender(m.raw_from) not in protected]
            for start in range(0, len(members), max_batch_messages):
                chunk = members[start : start + max_batch_messages]
                estimated = sum(m.size_estimate for m in chunk)
                if estimated < min_batch_bytes:
                    for m in chunk:
                        self.last_skips[m.id] = "below_min_batch_bytes"
                    continue
                ids = tuple(m.id for m in chunk)
                digest = membership_digest(
                    identity.account_id, plan_id, revision, "trash", POLICY_VERSION, ids
                )
                batch_id = canonical_digest({"group": group, "ids": ids})[:24]
                batches.append(
                    Batch(batch_id, group[2], ids, estimated, digest, {i: reasons[i] for i in ids})
                )
        result = Plan(
            identity.account_id,
            plan_id,
            revision,
            "trash",
            POLICY_VERSION,
            inv.generation,
            datetime.now(timezone.utc).isoformat(),
            tuple(batches),
        )
        self.journal.save_plan(result)
        return result
