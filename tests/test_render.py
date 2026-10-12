from datetime import datetime, timezone
from html.parser import HTMLParser

import pytest

from inbox_reclaimer.analytics import build_report
from inbox_reclaimer.models import Inventory, Message
from inbox_reclaimer.render import csv_safe, render_html, render_terminal, terminal_safe


def report():
    m = Message("1", "t1", 0, 6_000_001, frozenset({"TRASH"}), "a@example.com", "NEVER INCLUDE")
    r = build_report(
        Inventory("account", "g", "cursor", "start", "end", True, (), (m,)),
        datetime(2024, 2, 29, tzinfo=timezone.utc),
    )
    hostile = '<img src="https://evil.test" onerror="alert(1)">\x1b[31m[bold]mail[/bold]'
    r["account_id"] = hostile
    r["top_senders_count"][0]["sender"] = hostile
    r["warnings"].append(hostile)
    return r


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_html_is_self_contained_escaped_accessible():
    html = render_html(report())
    parsed = Tags()
    parsed.feed(html)
    assert not any(t in ("script", "img", "iframe", "link") for t, _ in parsed.tags)
    assert not any(k.startswith("on") for _, attrs in parsed.tags for k in attrs)
    csp = next(
        attrs["content"]
        for tag, attrs in parsed.tags
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy"
    )
    assert "default-src 'none'" in csp and "script-src 'none'" in csp
    assert "style-src 'sha256-" in csp
    assert "&lt;img" in html and "NEVER INCLUDE" not in html
    assert "<main" in html and "<caption" in html and 'scope="col"' in html
    assert "Scan coverage" in html and "Estimated" in html and "Cumulative" in html


def test_terminal_controls_and_rich_markup_are_not_interpreted():
    text = render_terminal(report())
    assert "\x1b" not in text and "\x07" not in text
    assert "[bold]mail[/bold]" in text  # literal data, never parsed as Rich markup
    assert "NEVER INCLUDE" not in text
    assert terminal_safe("a\x1b]8;;https://evil\x07b\x1b]8;;\x07\r\n\u202ec") == "abc"
    assert terminal_safe("a\x9b31mb\x9b0m") == "ab"


@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1)", "-1+2", "@cmd", " \t=1", "\r=1", "\x1b[31m=1"])
def test_csv_formula_neutralization(value):
    assert csv_safe(value).startswith("'")


def test_csv_plain():
    assert csv_safe("normal@example.com") == "normal@example.com"


def test_css_hash_matches_and_attachment_names_are_escaped():
    import base64
    import hashlib
    import re
    from inbox_reclaimer.attachments import AttachmentObservation, attachment_findings

    r = report()
    name = "</style><script>alert(1)</script>=bad.csv"
    r["attachment_findings"] = attachment_findings(
        [AttachmentObservation("m1", "p1", name, 12), AttachmentObservation("m2", "p1", name, 12)]
    )
    html = render_html(r)
    parsed = Tags()
    parsed.feed(html)
    assert not any(tag == "script" for tag, _ in parsed.tags)
    assert "&lt;script&gt;" in html
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(css.encode()).digest()).decode()
    csp = next(
        attrs["content"] for tag, attrs in parsed.tags if attrs.get("http-equiv") == "Content-Security-Policy"
    )
    assert f"'sha256-{digest}'" in csp
    assert "ADVISORY ONLY" in render_terminal(r)
