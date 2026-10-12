from datetime import datetime, timezone
import json
from time import perf_counter

import pytest

from inbox_reclaimer.analytics import build_report, parse_sender, subtract_months
from inbox_reclaimer.models import Inventory, Message

UTC = timezone.utc
CUTOFF = datetime(2024, 2, 29, 12, tzinfo=UTC)


def msg(id, size=10, date=None, sender="Alice <alice@example.com>", labels=(), headers=None):
    return Message(
        id,
        "t" + id,
        int(CUTOFF.timestamp() * 1000) if date is None else date,
        size,
        frozenset(labels),
        sender,
        "PRIVATE SUBJECT",
        headers or {},
    )


def inv(messages, complete=True):
    return Inventory("account", "g1", "opaque-cursor", "start", "end", complete, (), tuple(messages))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Alice <Alice@EXAMPLE.COM>", "Alice@example.com"),
        ("a.b+tag@gmail.com", "a.b+tag@gmail.com"),
        ("ab@gmail.com", "ab@gmail.com"),
        ("a@x.com, b@x.com", None),
        ("broken", None),
        ("<a@>", None),
        ("a@x.com\r\nBcc: b@x.com", None),
        ("a@x.com garbage", None),
        ("a..b@x.com", None),
        ("(" * 500 + "a@example.test" + ")" * 500, None),
        ("", None),
        (None, None),
    ],
)
def test_sender(raw, expected):
    assert parse_sender(raw) == expected


def test_sender_domain_label_boundaries():
    from itertools import product

    for length in range(1, 6):
        for chars in product("a-.", repeat=length):
            domain = "".join(chars)
            valid = all(
                label and not label.startswith("-") and not label.endswith("-") for label in domain.split(".")
            )
            expected = f"local@{domain}" if valid else None
            for raw in (f"local@{domain}", f"Name <local@{domain}>"):
                assert parse_sender(raw) == expected, raw


def test_calendar_clamping():
    assert subtract_months(CUTOFF, 12) == datetime(2023, 2, 28, 12, tzinfo=UTC)
    assert subtract_months(datetime(2024, 3, 31, tzinfo=UTC), 1).day == 29
    assert subtract_months(datetime(2023, 3, 31, tzinfo=UTC), 1).day == 28
    with pytest.raises(ValueError):
        subtract_months(CUTOFF, -1)


def test_union_categories_and_no_subjects():
    a = msg("1", 11_000_000, labels=("CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "TRASH"))
    report = build_report(inv([a, a, msg("2", 1, labels=("SPAM", "TRASH")), msg("3", 2)]), CUTOFF)
    assert report["totals"]["count"] == 3
    assert report["totals"]["estimated_bytes"] == 11_000_003
    cats = report["categories"]
    assert cats["promotions"]["count"] == cats["social"]["count"] == 1
    assert cats["category_overlap"]["count"] == 1
    assert cats["category_union"]["count"] == 1
    assert cats["other_unclassified"]["count"] == 2
    assert cats["trash_spam_union"]["count"] == 2
    assert "PRIVATE SUBJECT" not in json.dumps(report)
    assert report["coverage"]["duplicate_records"] == 1
    assert report["coverage"]["cursor"] == "opaque-cursor"


def test_decimal_strict_thresholds_unknowns_and_additive_bands():
    values = [0, 5_000_000, 5_000_001, 10_000_000, 10_000_001, 25_000_000, 25_000_001, -1, "bad", None, True]
    r = build_report(inv([msg(str(i), value) for i, value in enumerate(values)]), CUTOFF)
    assert [r["size_cohorts"][k]["count"] for k in ("gt_5mb", "gt_10mb", "gt_25mb")] == [5, 3, 1]
    assert r["totals"]["unknown_size_count"] == 4
    assert sum(v["count"] for v in r["size_bands"].values()) == len(values)
    assert sum(v["estimated_bytes"] for v in r["size_bands"].values()) == r["totals"]["estimated_bytes"]


def test_age_strict_calendar_cutoffs_and_timezone():
    from zoneinfo import ZoneInfo

    cutoff = datetime(2024, 3, 1, 1, tzinfo=UTC)  # February 29 in Los Angeles
    boundary = datetime(2023, 2, 28, 17, tzinfo=ZoneInfo("America/Los_Angeles"))
    epoch = int(boundary.timestamp() * 1000)
    r = build_report(
        inv(
            [
                msg("1", date=epoch - 1),
                msg("2", date=epoch),
                msg("3", date="bad"),
                msg("4", date=10**100),
                msg("5", date=-1),
            ]
        ),
        cutoff,
        "America/Los_Angeles",
    )
    assert r["age_cohorts"]["older_1y"]["count"] == 1
    assert r["totals"]["unknown_date_count"] == 3
    assert sum(v["count"] for v in r["age_bands"].values()) == 5
    assert r["coverage"]["cutoff"].startswith("2024-02-29T17:00:00")
    with pytest.raises(ValueError):
        build_report(inv([]), datetime(2024, 1, 1))


def test_newsletter_presence_and_sender_rankings():
    messages = [
        msg(str(i), 1, sender="count@example.com", headers={"lIsT-UnSuBsCrIbE": ""}) for i in range(30)
    ]
    messages += [msg("heavy", 99_000_000, sender="heavy@example.com")]
    messages += [msg("s" + str(i), 2, sender=f"s{i}@example.com") for i in range(30)]
    r = build_report(inv(messages, False), CUTOFF)
    assert r["newsletters"]["count"] == 30
    assert r["top_senders_count"][0]["sender"] == "count@example.com"
    assert r["top_senders_bytes"][0]["sender"] == "heavy@example.com"
    assert len(r["top_senders_count"]) == len(r["top_senders_bytes"]) == 20
    assert not r["coverage"]["complete"]
    assert any("incomplete" in w.lower() for w in r["warnings"])
    assert any("disposable" in w for w in r["warnings"])


def test_age_all_bands_and_raw_sender_preserved():
    original = msg("original", sender="Alice <Alice@EXAMPLE.COM>")
    messages = [original]
    for years in (1, 2, 5):
        boundary = int(subtract_months(CUTOFF, years * 12).timestamp() * 1000)
        messages += [msg(f"{years}-before", date=boundary - 1), msg(f"{years}-exact", date=boundary)]
    r = build_report(inv(messages), CUTOFF)
    assert [r["age_cohorts"][k]["count"] for k in ("older_1y", "older_2y", "older_5y")] == [5, 3, 1]
    assert sum(v["count"] for v in r["age_bands"].values()) == 7
    assert sum(v["estimated_bytes"] for v in r["age_bands"].values()) == r["totals"]["estimated_bytes"]
    assert original.raw_from == "Alice <Alice@EXAMPLE.COM>"


def test_optional_attachment_report_is_separate_from_totals():
    from inbox_reclaimer.attachments import attachment_findings

    inventory = inv([msg("1")])
    r = build_report(inventory, CUTOFF, attachment_findings=attachment_findings([]))
    assert r["totals"] == build_report(inventory, CUTOFF)["totals"]
    assert r["attachment_findings"]["advisory_only"]


def test_cumulative_metrics_match_direct_threshold_classification():
    from itertools import product

    sizes = [0, 5_000_000, 5_000_001, 10_000_000, 10_000_001, 25_000_000, 25_000_001, -1, True, None]
    boundaries = [int(subtract_months(CUTOFF, months).timestamp() * 1000) for months in (12, 24, 60)]
    dates = [0, -1, True, "bad", 253402300800000]
    dates += [boundary + delta for boundary in boundaries for delta in (-1, 0, 1)]
    messages = [msg(str(i), size, date) for i, (size, date) in enumerate(product(sizes, dates))]
    report = build_report(inv(messages + messages[:5]), CUTOFF)

    def metric(selected):
        known = [m.size_estimate for m in selected if type(m.size_estimate) is int and m.size_estimate >= 0]
        return {
            "count": len(selected),
            "estimated_bytes": sum(known),
            "unknown_size_count": len(selected) - len(known),
        }

    for key, threshold in zip(("gt_5mb", "gt_10mb", "gt_25mb"), (5_000_000, 10_000_000, 25_000_000)):
        expected = [m for m in messages if type(m.size_estimate) is int and m.size_estimate > threshold]
        assert report["size_cohorts"][key] == metric(expected)
    for key, boundary in zip(("older_1y", "older_2y", "older_5y"), boundaries):
        expected = [m for m in messages if type(m.internal_date) is int and 0 <= m.internal_date < boundary]
        assert report["age_cohorts"][key] == metric(expected)
    assert report["coverage"]["duplicate_records"] == 5


@pytest.mark.parametrize("sender_count", [0, 1, 19, 20, 21, 200])
def test_top_sender_rankings_match_full_sort_with_ties_and_unknowns(sender_count):
    messages = []
    expected = []
    for i in range(sender_count):
        sender = f"sender{i}@example.com" if i else None
        count = 1 + i % 4
        size = None if i % 7 == 0 else (i % 5) * 100
        messages.extend(msg(f"{i}-{j}", size, sender=sender) for j in range(count))
        expected.append(
            {
                "sender": sender,
                "count": count,
                "estimated_bytes": count * (size or 0),
                "unknown_size_count": count if size is None else 0,
            }
        )
    report = build_report(inv(reversed(messages)), CUTOFF)
    assert (
        report["top_senders_count"]
        == sorted(expected, key=lambda r: (-r["count"], -r["estimated_bytes"], r["sender"] or ""))[:20]
    )
    assert (
        report["top_senders_bytes"]
        == sorted(expected, key=lambda r: (-r["estimated_bytes"], -r["count"], r["sender"] or ""))[:20]
    )


@pytest.mark.parametrize("unique_display_names", [False, True])
def test_empty_and_100k_performance(unique_display_names):
    assert build_report(inv([]), CUTOFF)["totals"]["count"] == 0
    inventory = inv(
        msg(
            str(i),
            6_000_000,
            sender=f"Sender {i} <sender{i}@example.com>"
            if unique_display_names
            else f"s{i % 1000}@example.com",
            labels=("CATEGORY_UPDATES",),
        )
        for i in range(100_000)
    )
    start = perf_counter()
    r = build_report(inventory, CUTOFF)
    elapsed = perf_counter() - start
    print(f"100000-message cached aggregation: {elapsed:.3f}s")
    assert r["totals"]["count"] == 100_000
    assert elapsed < 2.0
