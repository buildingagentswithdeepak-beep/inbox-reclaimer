"""Reproducible synthetic 100k-mail benchmark; never reads tokens or contacts Gmail."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from inbox_reclaimer.analytics import build_report
from inbox_reclaimer.models import Batch, Identity, Inventory, Message, Plan
from inbox_reclaimer.storage import CacheStore, JournalStore, membership_digest


def measure(count=100_000):
    identity = Identity("benchmark@example.test", "offline-benchmark")
    cutoff = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = tuple(
        Message(
            str(i),
            f"thread-{i}",
            1_580_000_000_000,
            (i % 30 + 1) * 1_000_000,
            frozenset({"CATEGORY_PROMOTIONS" if i % 2 else "INBOX"}),
            f"sender-{i % 1000}@example.test",
            None,
            {"list-unsubscribe": "<mailto:leave@example.test>"} if i % 3 == 0 else {},
        )
        for i in range(count)
    )
    inventory = Inventory(
        identity.account_id,
        "benchmark-generation",
        "opaque-history",
        cutoff.isoformat(),
        cutoff.isoformat(),
        True,
        (),
        rows,
    )
    with tempfile.TemporaryDirectory(prefix="reclaim-benchmark-") as temp:
        cache = CacheStore(Path(temp) / "cache.db")
        journal = JournalStore(Path(temp) / "journal.db")
        try:
            cache.publish(inventory)
            journal.bind_account(identity)
            batches = []
            for start in range(0, count, 100):
                ids = tuple(sorted(str(i) for i in range(start, min(start + 100, count))))
                digest = membership_digest(
                    identity.account_id, "benchmark-plan", 1, "trash", "benchmark", ids
                )
                batches.append(
                    Batch(
                        f"batch-{start}",
                        "SIZE_AGE",
                        ids,
                        sum(rows[i].size_estimate for i in range(start, min(start + 100, count))),
                        digest,
                    )
                )
            journal.save_plan(
                Plan(
                    identity.account_id,
                    "benchmark-plan",
                    1,
                    "trash",
                    "benchmark",
                    inventory.generation,
                    cutoff.isoformat(),
                    tuple(batches),
                )
            )
            load_start = time.perf_counter()
            loaded = cache.load(identity.account_id)
            load_seconds = time.perf_counter() - load_start
            report_times = []
            for _ in range(5):
                start = time.perf_counter()
                report = build_report(loaded, cutoff)
                report_times.append(time.perf_counter() - start)
                assert report["totals"]["count"] == count
            page_times = []
            for _ in range(30):
                start = time.perf_counter()
                page = journal.list_batch(identity.account_id, "benchmark-plan", 1, "batch-0", page=1)
                page_times.append(time.perf_counter() - start)
                assert len(page["ids"]) == min(50, count)
            report_p95 = statistics.quantiles(report_times, n=100, method="inclusive")[94]
            page_p95 = statistics.quantiles(page_times, n=100, method="inclusive")[94]
            return {
                "fixture": "synthetic; 1000 senders; unique messages and threads; no live API",
                "messages": count,
                "platform": platform.platform(),
                "cpu": platform.processor(),
                "python": platform.python_version(),
                "cache_load_seconds": load_seconds,
                "cached_summary_p95_seconds": report_p95,
                "load_plus_summary_seconds": load_seconds + report_p95,
                "batch_view_p95_seconds": page_p95,
                "targets": {
                    "cached_summary_under_2s": report_p95 < 2,
                    "batch_view_under_500ms": page_p95 < 0.5,
                },
            }
        finally:
            cache.close()
            journal.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", type=int, default=100_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure(args.messages)
    content = json.dumps(result, indent=2)
    print(content)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
    if not all(result["targets"].values()):
        raise SystemExit(1)
