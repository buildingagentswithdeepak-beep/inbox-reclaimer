"""Offline, unique-message aggregation; no mailbox writes or subject disclosure.

Every metric has count, estimated_bytes and unknown_size_count. Bytes sum only
valid nonnegative integer sizeEstimate values; none of these are quota readings.
Raw From remains on Message.raw_from; normalized keys never replace source data.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from calendar import monthrange
from datetime import datetime
from email import policy
from heapq import nsmallest
import re
from zoneinfo import ZoneInfo

from .models import Inventory

_ATOM = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
_ADDRESS = re.compile(rf"({_ATOM}(?:\.{_ATOM})*)@([A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)\Z")
_SIMPLE_DISPLAY = re.compile(
    rf"[A-Za-z0-9 _-]+ <({_ATOM}(?:\.{_ATOM})*)@([A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)>\Z"
)
_HEADER_CONTROLS = re.compile(r"[\x00-\x1f\x7f]")
_LABELS = {
    "CATEGORY_PROMOTIONS": "promotions",
    "CATEGORY_SOCIAL": "social",
    "CATEGORY_UPDATES": "updates",
    "CATEGORY_FORUMS": "forums",
}
_SIZE_KEYS = ("gt_5mb", "gt_10mb", "gt_25mb")
_AGE_KEYS = ("older_1y", "older_2y", "older_5y")
_SIZE_BANDS = ("le_5mb", "gt_5_le_10mb", "gt_10_le_25mb", "gt_25mb", "unknown")
_AGE_BANDS = ("within_1y", "older_1_to_2y", "older_2_to_5y", "older_5y", "unknown")


def parse_sender(raw: str | None) -> str | None:
    """Parse exactly one mailbox conservatively; preserve local-part case/dots/tags.

    Domain case is insensitive. Ambiguous/defective headers are unknown, not
    guessed. Deliberately unsupported exotic mailbox syntax also stays unknown.
    """
    if not isinstance(raw, str) or not raw or _HEADER_CONTROLS.search(raw):
        return None
    value = raw.strip()
    # Common, strictly delimited ASCII display names avoid constructing a full RFC parser per message.
    match = _ADDRESS.fullmatch(value) or _SIMPLE_DISPLAY.fullmatch(value)
    if match is None:
        try:
            header = policy.default.header_factory("From", value)
            if header.defects or len(header.addresses) != 1:
                return None
            match = _ADDRESS.fullmatch(header.addresses[0].addr_spec)
        except (ValueError, IndexError, TypeError, RecursionError):
            return None
    if match is None:
        return None
    local, domain = match.groups()
    # The regex already bounds the domain with alphanumerics. These are the
    # only remaining empty-label or leading/trailing-hyphen boundaries.
    if ".." in domain or ".-" in domain or "-." in domain:
        return None
    return f"{local}@{domain.lower()}"


def subtract_months(value: datetime, months: int) -> datetime:
    """Calendar subtraction with end-of-month clamping, retaining wall time/tz."""
    if type(months) is not int or months < 0:
        raise ValueError("months must be a nonnegative integer")
    year, month = divmod(value.year * 12 + value.month - 1 - months, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise ValueError("calendar result outside supported datetime range")
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def _metric() -> dict:
    return {"count": 0, "estimated_bytes": 0, "unknown_size_count": 0}


def _add(metric: dict, size: int, unknown: bool) -> None:
    metric["count"] += 1
    metric["estimated_bytes"] += size
    if unknown:
        metric["unknown_size_count"] += 1


def _cumulative(bands, keys):
    """Derive upper cohorts from ordered disjoint bands, excluding unknowns."""
    values = list(bands.values())
    result = {}
    for index, key in enumerate(keys, start=1):
        total = _metric()
        for band in values[index:4]:
            for field, value in band.items():
                total[field] += value
        result[key] = total
    return result


def build_report(
    inventory: Inventory, cutoff: datetime, timezone: str = "UTC", *, attachment_findings: dict | None = None
) -> dict:
    """Build a JSON-ready report in one message pass plus sender-group sorting.

    Duplicate IDs: first observation wins, duplicates are disclosed. Cumulative
    categories/cohorts overlap; only *_bands are disjoint and additive. Dates are
    Gmail internalDate milliseconds since epoch. Naive report cutoffs are rejected.
    Optional attachment_findings is a separately produced advisory result.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("report cutoff must be timezone-aware")
    cutoff = cutoff.astimezone(ZoneInfo(timezone))
    age_limits = [subtract_months(cutoff, months).timestamp() * 1000 for months in (60, 24, 12)]
    totals = _metric()
    totals.update(unknown_date_count=0, unknown_sender_count=0, invalid_record_count=0)
    categories = {
        key: _metric()
        for key in (
            *_LABELS.values(),
            "other_unclassified",
            "category_union",
            "category_overlap",
            "trash",
            "spam",
            "trash_spam_union",
        )
    }

    size_bands = {key: _metric() for key in _SIZE_BANDS}
    age_bands = {key: _metric() for key in _AGE_BANDS}
    newsletters = _metric()
    newsletters["signal"] = "List-Unsubscribe header presence; candidate, not disposable"
    senders: dict[str | None, dict] = {}
    parsed: dict[str, str | None] = {}
    seen: set[str] = set()
    duplicate_records = 0
    for message in inventory.messages:
        if message.id in seen:
            duplicate_records += 1
            continue
        seen.add(message.id)
        value = message.size_estimate
        unknown = type(value) is not int or value < 0
        size = 0 if unknown else value
        _add(totals, size, unknown)
        totals["invalid_record_count"] += not message.valid
        raw = message.raw_from
        # Cache only within this report; no long-lived mailbox-header retention.
        if isinstance(raw, str):
            if raw not in parsed:
                parsed[raw] = parse_sender(raw)
            sender = parsed[raw]
        else:
            sender = None
        if sender is None:
            totals["unknown_sender_count"] += 1
        if sender in senders:
            _add(senders[sender], size, unknown)
        else:
            senders[sender] = {
                "sender": sender,
                "count": 1,
                "estimated_bytes": size,
                "unknown_size_count": int(unknown),
            }
        labels = message.labels or ()
        category_count = 0
        for label, key in _LABELS.items():
            if label in labels:
                _add(categories[key], size, unknown)
                category_count += 1
        _add(categories["category_union" if category_count else "other_unclassified"], size, unknown)
        if category_count > 1:
            _add(categories["category_overlap"], size, unknown)
        trash, spam = "TRASH" in labels, "SPAM" in labels
        if trash:
            _add(categories["trash"], size, unknown)
        if spam:
            _add(categories["spam"], size, unknown)
        if trash or spam:
            _add(categories["trash_spam_union"], size, unknown)
        if any(isinstance(key, str) and key.lower() == "list-unsubscribe" for key in message.headers):
            _add(newsletters, size, unknown)
        size_band = 4 if unknown else bisect_left((5_000_000, 10_000_000, 25_000_000), size)
        _add(size_bands[_SIZE_BANDS[size_band]], size, unknown)
        date = message.internal_date
        # No per-message datetime construction; reject invalid/out-of-range dates.
        unknown_date = type(date) is not int or not 0 <= date <= 253402300799999
        totals["unknown_date_count"] += unknown_date
        age_band = 4 if unknown_date else 3 - bisect_right(age_limits, date)
        _add(age_bands[_AGE_BANDS[age_band]], size, unknown)
    warnings = [
        "Estimated message bytes (Gmail sizeEstimate) are not exact Google storage quota or bytes freed.",
        "Cumulative size and age cohorts overlap: never sum them. Disjoint bands are additive.",
        "Category labels may overlap; category union and overlap are explicit. Other/unclassified is not Primary.",
        "Trash and Spam overlap categories and each other; their union counts unique messages.",
        "Newsletter header presence is a candidate signal, not evidence that mail is disposable.",
        "Enumeration is not a point-in-time mailbox snapshot; this report makes no deletion recommendation.",
    ]
    if not inventory.complete or inventory.unresolved:
        warnings.append("Scan incomplete or unresolved: coverage is partial; do not create executable plans.")
    if duplicate_records:
        warnings.append("Duplicate message IDs were counted once using the first observation.")
    if totals["unknown_size_count"] or totals["unknown_date_count"] or totals["unknown_sender_count"]:
        warnings.append("Malformed or missing metadata is shown as unknown, not silently estimated.")
    if totals["invalid_record_count"]:
        warnings.append("Invalid metadata records are present; their usable fields are descriptive only.")
    rows = list(senders.values())
    result = {
        "account_id": inventory.account_id,
        "generation": inventory.generation,
        "coverage": {
            "complete": inventory.complete,
            "started_at": inventory.started_at,
            "completed_at": inventory.completed_at,
            "cursor": inventory.cursor,
            "unresolved_count": len(inventory.unresolved),
            "unique_messages": len(seen),
            "duplicate_records": duplicate_records,
            "cutoff": cutoff.isoformat(),
            "timezone": timezone,
        },
        "totals": totals,
        "top_senders_count": nsmallest(
            20, rows, key=lambda r: (-r["count"], -r["estimated_bytes"], r["sender"] or "")
        ),
        "top_senders_bytes": nsmallest(
            20, rows, key=lambda r: (-r["estimated_bytes"], -r["count"], r["sender"] or "")
        ),
        "categories": categories,
        "newsletters": newsletters,
        "size_cohorts": _cumulative(size_bands, _SIZE_KEYS),
        "age_cohorts": _cumulative(age_bands, _AGE_KEYS),
        "size_bands": size_bands,
        "age_bands": age_bands,
        "warnings": warnings,
    }
    from .models import LimitedInventory

    if isinstance(inventory, LimitedInventory):
        result["coverage"].update({
            "scope": "limited_preview",
            "complete": False,
            "cursor": None,
            "message_limit": inventory.message_limit,
            "selected_count": inventory.selected_count,
            "enumeration_exhausted": inventory.enumeration_exhausted,
            "persisted": False,
            "ordering": "gmail_list_order_not_guaranteed_newest",
        })
        warnings.extend([
            "Limited preview: totals describe only the selected messages, not the entire mailbox.",
            "Selection follows Gmail listing order; global newest-first ordering is not guaranteed.",
            "No history reconciliation or full-cache update. Preview cannot be used for proposals. "
            "Rerunning starts a fresh preview; missing messages consume a limit slot.",
        ])
    if attachment_findings is not None:
        result["attachment_findings"] = attachment_findings
    return result
