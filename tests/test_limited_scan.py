"""Bounded previews must never become full-mailbox inventory authority."""

from dataclasses import replace
import json

import pytest
from typer.testing import CliRunner

from inbox_reclaimer.analytics import build_report
from inbox_reclaimer.cli import app
from inbox_reclaimer.demo import DEMO_CUTOFF, DEMO_IDENTITY, demo_messages
from inbox_reclaimer.gmail import FakeGmailAdapter
from inbox_reclaimer.models import Identity, IdentityMismatch, Message, MissingMessage, ReadFailure
from inbox_reclaimer.render import render_html, render_terminal
from inbox_reclaimer.staging import ResumableReadAdapter
from inbox_reclaimer.storage import CacheStore
from inbox_reclaimer.sync import SyncCancelled, SyncService


def message(i):
    return Message(
        f"m{i:04d}", f"t{i}", i * 1000, 100, frozenset({"INBOX"}), "sender@example.test",
        "private subject", {"Subject": "private subject"},
    )


class TrackedMailbox(FakeGmailAdapter):
    def __init__(self, count=1500, **kwargs):
        super().__init__([message(i) for i in range(count)], **kwargs)
        self.pages = []
        self.reads = []

    def list_message_ids(self, page_token=None):
        self.pages.append(page_token)
        return super().list_message_ids(page_token)

    def get_metadata(self, message_id):
        self.reads.append(message_id)
        return super().get_metadata(message_id)

    def history_boundary(self):
        pytest.fail("Preview must not capture a history cursor")

    def read_history(self, *args, **kwargs):
        pytest.fail("Preview must not replay history")

    def get_thread(self, *args, **kwargs):
        pytest.fail("Preview must not read threads")


class ForbiddenCache:
    def __getattr__(self, name):
        pytest.fail(f"Preview touched cache: {name}")


def scan(adapter, count=1000, **kwargs):
    return SyncService(adapter, ForbiddenCache(), **kwargs).limited_scan(count)


@pytest.mark.parametrize("limit,expected_pages", [(1, 1), (500, 1), (501, 2), (1000, 2)])
def test_preview_stops_at_limit_without_fetching_an_extra_page(limit, expected_pages):
    adapter = TrackedMailbox()
    inventory = scan(adapter, limit)
    assert len(inventory.messages) == len(adapter.reads) == limit
    assert len(adapter.pages) == expected_pages
    assert not inventory.complete and inventory.cursor == ""
    assert inventory.message_limit == inventory.selected_count == limit
    assert not inventory.enumeration_exhausted
    # The fake intentionally lists IDs oldest-first: no false global-newest claim.
    assert {m.id for m in inventory.messages} == {f"m{i:04d}" for i in range(limit)}
    assert [m.internal_date for m in inventory.messages] == sorted(
        [m.internal_date for m in inventory.messages], reverse=True
    )


@pytest.mark.parametrize("count", [0, 3, 1000])
def test_empty_small_or_exact_mailbox_remains_unreconciled_preview(count):
    adapter = TrackedMailbox(count)
    inventory = scan(adapter)
    assert inventory.selected_count == len(inventory.messages) == count
    assert inventory.enumeration_exhausted
    assert not inventory.complete


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "1000", None])
def test_invalid_limits_fail_before_identity_or_any_reads(limit):
    class ForbiddenAdapter:
        def __getattr__(self, name):
            pytest.fail(f"Invalid limit accessed adapter: {name}")

    with pytest.raises(ValueError, match="positive integer"):
        scan(ForbiddenAdapter(), limit)


def test_duplicate_ids_are_not_read_twice_and_missing_messages_consume_a_slot():
    adapter = TrackedMailbox(3)
    pages = iter([
        {"ids": ["m0000", "m0000"], "next_page_token": "p2"},
        {"ids": ["m0000", "gone", "m0001", "m0002"], "next_page_token": "p3"},
    ])
    adapter.list_message_ids = lambda page_token=None: next(pages)
    inventory = scan(adapter, 3)
    assert adapter.reads == ["m0000", "gone", "m0001"]
    assert inventory.selected_count == 3
    assert len(inventory.messages) == 2
    assert inventory.unresolved == ("gone",)


@pytest.mark.parametrize("page", [None, {"ids": "bad"}, {"ids": [""]},
                                  {"ids": [], "next_page_token": ""},
                                  {"ids": [], "next_page_token": 17}])
def test_malformed_pages_fail_closed(page):
    adapter = TrackedMailbox(1)
    adapter.list_message_ids = lambda page_token=None: page
    with pytest.raises(ReadFailure):
        scan(adapter)


def test_repeated_page_tokens_fail_instead_of_looping():
    adapter = TrackedMailbox(1)
    adapter.list_message_ids = lambda page_token=None: {"ids": ["m0000"], "next_page_token": "loop"}
    with pytest.raises(ReadFailure, match="page token"):
        scan(adapter)
    assert adapter.reads == ["m0000"]


def test_preview_redaction_malformed_metadata_and_cancellation():
    adapter = TrackedMailbox(1)
    adapter.messages["m0000"] = replace(adapter.messages["m0000"], valid=False, internal_date=None)
    events = []
    inventory = scan(adapter, 1, redact_subjects=True, progress=events.append)
    assert inventory.unresolved == ("m0000",)
    assert inventory.messages[0].subject is None
    assert "Subject" not in inventory.messages[0].headers
    assert "private subject" not in repr(events)
    with pytest.raises(SyncCancelled):
        scan(adapter, cancelled=lambda: True)


@pytest.mark.parametrize("switch_at", ["list", "metadata", "missing"])
def test_identity_switch_during_response_cannot_return_a_preview(switch_at):
    adapter = TrackedMailbox(1)
    other = Identity("other@example.test", "other-client")
    if switch_at == "list":
        def changed(page_token=None):
            adapter.identity = other
            return {"ids": ["m0000"], "next_page_token": None}
        adapter.list_message_ids = changed
    else:
        def changed(message_id):
            adapter.identity = other
            if switch_at == "missing":
                raise MissingMessage("gone")
            return adapter.messages[message_id]
        adapter.get_metadata = changed
    with pytest.raises(IdentityMismatch):
        scan(adapter)
    if switch_at == "list":
        assert not adapter.reads


def test_read_failure_propagates_without_returning_success():
    adapter = TrackedMailbox(1)
    def fail(message_id):
        raise ReadFailure("offline")
    adapter.get_metadata = fail
    with pytest.raises(ReadFailure, match="offline"):
        scan(adapter)


def test_preview_cannot_be_published_even_with_forged_complete_cursor(tmp_path):
    inventory = scan(TrackedMailbox(1))
    with CacheStore(tmp_path / "cache.db") as cache:
        with pytest.raises(ValueError, match="preview"):
            cache.publish(replace(inventory, complete=True, cursor="forged"))
        with pytest.raises(ValueError, match="preview"):
            cache.stage(inventory)
        assert cache.load(inventory.account_id) is None


def test_reports_explain_partial_coverage_limit_and_ordering():
    inventory = scan(TrackedMailbox(3), 2)
    report = build_report(inventory, DEMO_CUTOFF)
    coverage = report["coverage"]
    assert coverage["scope"] == "limited_preview"
    assert coverage["message_limit"] == coverage["selected_count"] == 2
    assert coverage["cursor"] is None and not coverage["complete"]
    assert coverage["persisted"] is False
    assert coverage["ordering"] == "gmail_list_order_not_guaranteed_newest"
    assert any("not guaranteed" in warning for warning in report["warnings"])
    html, terminal = render_html(report), render_terminal(report)
    assert "Limited preview" in html and "2 messages" in html
    assert ">Scan complete</span>" not in html
    assert "limited_preview" in terminal and "message_limit: 2" in terminal


@pytest.fixture
def local(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "_hermes_home.py").write_text(
        'import os\nfrom pathlib import Path\ndef get_hermes_home():\n    return Path(os.environ["HERMES_HOME"])\n'
    )
    home = tmp_path / "profile"
    monkeypatch.setenv("HERMES_HOME", str(home))
    return ["--workspace-scripts", str(scripts), "--demo"], home


def invoke(args):
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, (result.output, result.exception)
    return result


@pytest.mark.parametrize("extra", [["--cached"], ["--full-resync"], ["--attachments"]])
def test_incompatible_modes_are_rejected_before_profile_access(extra, monkeypatch):
    monkeypatch.setattr("inbox_reclaimer.cli.resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    result = CliRunner().invoke(app, ["analyze", "--max-messages", "1000"] + extra)
    assert result.exit_code == 2
    assert "cannot be combined" in result.output


def test_cli_preview_does_not_seed_cache_or_enable_proposals(local):
    args, home = local
    report = home / "inbox_reclaimer/reports/report-preview.html"
    result = invoke(args + ["analyze", "--max-messages", "3", "--redact-subjects",
                            "--json", "--html", str(report)])
    data = json.loads(result.stdout)
    assert data["totals"]["count"] == 3
    assert data["coverage"]["scope"] == "limited_preview"
    assert not data["coverage"]["complete"]
    assert "Limited preview" in report.read_text(encoding="utf-8")
    assert json.loads(invoke(args + ["status"]).stdout)["inventory"] is None
    result = CliRunner().invoke(app, args + ["propose"])
    assert result.exit_code == 2 and "No published inventory" in result.output


def test_preview_preserves_full_cache_and_pending_scan_then_full_analysis_still_works(local):
    args, home = local
    full = json.loads(invoke(args + ["analyze", "--json"]).stdout)
    cache_path = home / "inbox_reclaimer/cache.db"
    with CacheStore(cache_path) as cache:
        before = cache.load(DEMO_IDENTITY.account_id)
    adapter = FakeGmailAdapter(demo_messages(), identity=DEMO_IDENTITY)
    with ResumableReadAdapter(adapter, cache_path) as reader:
        reader.history_boundary()
        reader.list_message_ids()
        staged_before = list(reader.conn.iterdump())
    preview = json.loads(invoke(args + ["analyze", "--max-messages", "2", "--json"]).stdout)
    assert preview["totals"]["count"] == 2
    with CacheStore(cache_path) as cache:
        assert cache.load(DEMO_IDENTITY.account_id) == before
    with ResumableReadAdapter(adapter, cache_path) as reader:
        assert list(reader.conn.iterdump()) == staged_before
    again = json.loads(invoke(args + ["analyze", "--json"]).stdout)
    assert again["coverage"]["complete"]
    assert again["totals"] == full["totals"]


def test_hermes_preview_keeps_coverage_but_no_raw_mail_data(local):
    args, _ = local
    result = invoke(args + ["--hermes", "analyze", "--max-messages", "2", "--json"])
    data = json.loads(result.stdout)
    assert data["coverage"]["message_limit"] == 2
    assert data["coverage"]["scope"] == "limited_preview"
    assert data["mutation_enabled"] is False
    assert "@example.test" not in result.output
    assert "Synthetic newsletter edition" not in result.output
