"""Local-only renderers. Mail data is never markup, a URL, CSS, or executable code."""

from __future__ import annotations

import base64
import hashlib
from html import escape
from importlib.resources import files
from io import StringIO
import re
import unicodedata

from rich.console import Console
from rich.table import Table
from rich.text import Text

# OSC/DCS/APC/PM/SOS strings, CSI commands, then remaining ESC commands.
_CONTROLS = re.compile(
    r"(?:\x1b\]|\x9d)[^\x07\x1b\x9c]*(?:\x07|\x1b\\|\x9c|$)"
    r"|(?:\x1b[P_X^]|[\x90\x98\x9e\x9f]).*?(?:\x1b\\|\x9c|$)"
    r"|(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]"
    r"|\x1b[ -/]*[@-~]",
    re.DOTALL,
)
_LABELS = {
    "promotions": "Promotions",
    "social": "Social",
    "updates": "Updates",
    "forums": "Forums",
    "other_unclassified": "Other / unclassified",
    "category_union": "Category union (unique)",
    "category_overlap": "Multiple category labels",
    "trash": "Trash",
    "spam": "Spam",
    "trash_spam_union": "Trash / Spam union (unique)",
    "gt_5mb": "> 5 MB",
    "gt_10mb": "> 10 MB",
    "gt_25mb": "> 25 MB",
    "le_5mb": "0–5 MB",
    "gt_5_le_10mb": "> 5–10 MB",
    "gt_10_le_25mb": "> 10–25 MB",
    "unknown": "Unknown",
    "older_1y": "Older than 1 year",
    "older_2y": "Older than 2 years",
    "older_5y": "Older than 5 years",
    "within_1y": "Within 1 year (incl. future dates)",
    "older_1_to_2y": "> 1–2 years",
    "older_2_to_5y": "> 2–5 years",
}


def terminal_safe(value: object) -> str:
    """Strip control sequences, line injection and invisible direction overrides."""
    value = _CONTROLS.sub("", str(value))
    return "".join(c for c in value if unicodedata.category(c) not in ("Cc", "Cf", "Cs", "Zl", "Zp"))


def csv_safe(value: object) -> str:
    """Neutralize formula prefixes (also hidden by whitespace/control sequences).

    Apply per cell, then use csv.writer for quoting delimiters and quotes.
    """
    text = terminal_safe(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _html(value: object) -> str:
    return escape(terminal_safe(value), quote=True)


def _number(value: object) -> str:
    return f"{value:,}" if type(value) is int else str(value)


def _bytes(value: object) -> str:
    if type(value) is not int or value < 0:
        return str(value)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f} GB"
    if value >= 1_000_000:
        return f"{value / 1_000_000:,.2f} MB"
    if value >= 1000:
        return f"{value / 1000:,.2f} kB"
    return f"{value:,} B"


def _rows(report: dict, key: str) -> list[tuple[str, dict]]:
    if key.startswith("top_senders"):
        return [(row["sender"] or "Unknown sender", row) for row in report[key]]
    return [(_LABELS.get(name, name), row) for name, row in report[key].items()]


def _table_html(rows: list, caption: str, first: str = "Group", rank_by: str | None = None) -> str:
    maximum = max((r.get(rank_by, 0) for _, r in rows), default=0) if rank_by else 0
    body = []
    for label, row in rows:
        meter = ""
        value = row.get(rank_by, 0) if rank_by else 0
        if type(maximum) is int and maximum > 0 and type(value) is int:
            meter = (
                f'<meter min="0" max="{maximum}" value="{max(0, min(maximum, value))}" '
                f'aria-label="{_html(label)} relative {_html(rank_by)}"></meter>'
            )
        body.append(
            f'<tr><td class="sender">{_html(label)}{meter}</td>'
            f'<td class="number">{_html(_number(row["count"]))}</td>'
            f'<td class="number">{_html(_bytes(row["estimated_bytes"]))}</td>'
            f'<td class="number">{_html(_number(row.get("unknown_size_count", 0)))}</td></tr>'
        )
    if not body:
        body.append('<tr><td colspan="4" class="empty">No messages in this inventory.</td></tr>')
    return (
        f'<div class="table-scroll"><table><caption>{_html(caption)}</caption><thead><tr>'
        f'<th scope="col">{_html(first)}</th><th scope="col" class="number">Messages</th>'
        '<th scope="col" class="number">Estimated size</th>'
        '<th scope="col" class="number">Size unknown</th></tr></thead><tbody>'
        + "".join(body)
        + "</tbody></table></div>"
    )


def _panel(report: dict, key: str, title: str, note: str, rank_by: str | None = None) -> str:
    return (
        f'<section class="panel"><h2>{_html(title)}</h2><p>{_html(note)}</p>'
        + _table_html(
            _rows(report, key),
            title + " · unique messages per row",
            "Sender" if rank_by else "Group",
            rank_by,
        )
        + "</section>"
    )


def _attachment_html(findings: dict | None) -> str:
    if findings is None:
        return (
            '<section class="panel"><h2>Attachment comparison</h2><p>Not run. '
            "Attachment inspection is a separate, opt-in read pass. No content was downloaded "
            "by this report.</p></section>"
        )
    parts = [
        '<section class="panel"><h2>Attachment comparison · advisory only</h2>',
        f"<p>{_html(findings.get('warning', 'Equal content does not imply duplicate messages.'))}</p>",
    ]
    for key, title in (
        ("possible_matches", "Possible filename / size matches"),
        ("equal_content", "Equal SHA-256 content"),
    ):
        parts.append(f"<h3>{title}</h3>")
        groups = findings.get(key, [])
        if not groups:
            parts.append("<p>No matching groups observed.</p>")
        for group in groups:
            parts.append(
                f"<p><strong>{_html(group.get('filename', group.get('sha256', 'Unknown')))}</strong>"
                f" · {_html(_bytes(group.get('decoded_size')))} decoded per part</p><ul>"
            )
            for member in group.get("members", []):
                parts.append(
                    f"<li>{_html(member.get('filename', 'Unnamed'))} — message "
                    f"<code>{_html(member.get('message_id', ''))}</code>, part "
                    f"<code>{_html(member.get('part_id', ''))}</code></li>"
                )
            parts.append("</ul>")
    parts.append(
        "<p>These findings do not create deletion batches or contribute to reclaimable-byte totals.</p></section>"
    )
    return "".join(parts)


def render_html(report: dict) -> str:
    """Return standalone escaped HTML with hash-authorized packaged inline CSS."""
    css = files("inbox_reclaimer").joinpath("assets/report.css").read_text(encoding="utf-8")
    digest = base64.b64encode(hashlib.sha256(css.encode("utf-8")).digest()).decode("ascii")
    csp = (
        "default-src 'none'; script-src 'none'; style-src 'sha256-" + digest + "'; "
        "img-src 'none'; connect-src 'none'; font-src 'none'; object-src 'none'; "
        "base-uri 'none'; form-action 'none'"
    )
    coverage, totals = report["coverage"], report["totals"]
    complete = coverage["complete"] and not coverage["unresolved_count"]
    status = "Scan complete" if complete else "Partial coverage · review required"
    if coverage.get("scope") == "limited_preview":
        complete = False
        status = f"Limited preview · up to {_number(coverage['message_limit'])} messages"
    metrics = [
        ("Messages inventoried", _number(totals["count"]), "Unique message IDs, including Trash / Spam"),
        (
            "Estimated message storage",
            _bytes(totals["estimated_bytes"]),
            "Not Google quota or a recovery forecast",
        ),
        (
            "Newsletter candidates",
            _number(report["newsletters"]["count"]),
            "Header-derived signal · not disposable",
        ),
        (
            "Messages over 10 MB",
            _number(report["size_cohorts"]["gt_10mb"]["count"]),
            "Decimal MB · strict greater-than threshold",
        ),
    ]
    cards = "".join(
        f'<article class="metric"><div class="metric-label">{_html(label)}</div>'
        f'<div class="metric-value">{_html(value)}</div><div class="metric-note">{_html(note)}</div></article>'
        for label, value, note in metrics
    )
    coverage_fields = [
        ("Account", report["account_id"]),
        ("Inventory generation", report["generation"]),
        ("Frozen report cutoff", coverage["cutoff"]),
        ("Scan started", coverage["started_at"]),
        ("Scan completed", coverage["completed_at"]),
        ("History cursor", coverage["cursor"]),
        ("Timezone", coverage["timezone"]),
        ("Unresolved records", coverage["unresolved_count"]),
        ("Duplicate records ignored", coverage["duplicate_records"]),
        ("Unknown sizes", totals["unknown_size_count"]),
        ("Unknown dates", totals["unknown_date_count"]),
        ("Unknown senders", totals["unknown_sender_count"]),
    ]
    if coverage.get("scope") == "limited_preview":
        coverage_fields.extend([
            ("Scope", "Limited preview; not a full-mailbox scan"),
            ("Message limit", coverage["message_limit"]),
            ("Selected IDs (including missing)", coverage["selected_count"]),
            ("Listing exhausted", coverage["enumeration_exhausted"]),
            ("Ordering", "Gmail listing order; newest not guaranteed"),
            ("Full cache", "Unchanged; preview is not persisted as an inventory"),
        ])
    coverage_html = "".join(f"<div><dt>{_html(k)}</dt><dd>{_html(v)}</dd></div>" for k, v in coverage_fields)
    panels = (
        '<h2 class="section-heading">Where your mail adds up</h2>'
        '<p class="section-intro">Independent sender rankings reveal volume and storage concentration.</p><div class="grid">'
        + _panel(
            report,
            "top_senders_count",
            "Top 20 senders · message count",
            "Ranked by unique messages; address variants remain distinct.",
            "count",
        )
        + _panel(
            report,
            "top_senders_bytes",
            "Top 20 senders · estimated size",
            "Ranked independently by summed valid size estimates.",
            "estimated_bytes",
        )
        + '</div><div class="grid">'
        + _panel(
            report,
            "categories",
            "Category & label coverage",
            "Label-derived, overlapping totals. The union is unique; other/unclassified is not Primary.",
        )
        + '<section class="panel"><h2>Newsletter candidates</h2><p>List-Unsubscribe header presence identifies a candidate, '
        "not disposable mail. No unsubscribe links are opened.</p>"
        + _table_html([("Header-derived candidates", report["newsletters"])], "Unique newsletter candidates")
        + '<div class="note">Message storage includes bodies, headers and MIME encoding. Decoded attachment size '
        "is a different quantity; neither is an exact Google quota reading.</div></section></div>"
        + '<h2 class="section-heading">Size & age distribution</h2>'
        '<p class="section-intro">Cumulative cohorts answer threshold questions. Disjoint bands can be added together.</p>'
        '<div class="grid">'
        + _panel(
            report,
            "size_cohorts",
            "Cumulative size cohorts",
            "Overlapping: do not add these rows. MB = 1,000,000 bytes.",
        )
        + _panel(
            report,
            "age_cohorts",
            "Cumulative age cohorts",
            "Overlapping calendar-year thresholds, frozen in the configured timezone.",
        )
        + _panel(
            report,
            "size_bands",
            "Disjoint size bands",
            "Additive: each inventoried message appears in exactly one row.",
        )
        + _panel(
            report,
            "age_bands",
            "Disjoint age bands",
            "Additive calendar bands. Invalid internalDate values remain unknown.",
        )
        + "</div>"
        + _attachment_html(report.get("attachment_findings"))
    )
    warnings = "".join(f"<li>{_html(w)}</li>" for w in report["warnings"])
    fixture_badge = (
        '<span class="pill">SYNTHETIC DEMO · NO GMAIL ACCESS</span>'
        if report.get("fixture") == "synthetic"
        else ""
    )
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer"><title>Inbox Reclaimer · Mailbox overview</title>'
        f'<style>{css}</style></head><body><a class="skip" href="#main">Skip to report</a>'
        '<header><div class="eyebrow">Inbox Reclaimer / Gate A</div><h1>Your mailbox, in perspective.</h1>'
        "<p>A local, read-only inventory of message volume and estimated storage. "
        'Understand the patterns before considering any cleanup.</p><div class="header-meta">'
        f'<span class="pill">ANALYSIS ONLY · NO MAIL CHANGED</span><span class="pill{chr(32) + "warning-pill" if not complete else ""}">'
        f'{_html(status)}</span>{fixture_badge}</div></header><main id="main"><section class="metrics" aria-label="Mailbox summary">'
        f'{cards}</section><section class="panel"><h2>Scan coverage</h2>'
        "<p>Timestamped inventory, not a point-in-time snapshot. Unknown metadata is visible rather than inferred.</p>"
        f'<dl class="coverage">{coverage_html}</dl></section>{panels}'
        f'<section class="panel cautions"><h2>Read these numbers with care</h2><ul>{warnings}</ul></section>'
        "<footer>Generated locally · No scripts, remote assets or tracking · Aggregate report excludes subjects. "
        "Sender addresses and identifiers are sensitive; keep this file private. No deletion authorization is implied.</footer>"
        "</main></body></html>"
    )


def render_terminal(report: dict) -> str:
    """Return plain text generated with Rich markup/highlighting explicitly off.

    Callers must print this as plain text (e.g. typer.echo or Console.print with
    markup=False), not reinterpret the returned data as markup.
    """
    out = StringIO()
    console = Console(
        file=out, force_terminal=False, color_system=None, markup=False, highlight=False, width=112
    )

    def line(value):
        console.print(Text(terminal_safe(value)))

    line("INBOX RECLAIMER | Gate A · Read-only analysis · No mail changed")
    line(f"Account: {report['account_id']} | Generation: {report['generation']}")
    line("Scan coverage")
    for key, value in report["coverage"].items():
        line(f"  {key}: {value}")
    line(
        f"Unique messages: {_number(report['totals']['count'])} | "
        f"Estimated message size: {_bytes(report['totals']['estimated_bytes'])} (not Google quota)"
    )
    line(
        f"Unknown sizes: {report['totals']['unknown_size_count']}; "
        f"unknown dates: {report['totals']['unknown_date_count']}; "
        f"unknown senders: {report['totals']['unknown_sender_count']}"
    )
    tables = [
        ("top_senders_count", "Top 20 senders by count"),
        ("top_senders_bytes", "Top 20 senders by estimated size"),
        ("categories", "Category labels (overlapping; explicit union)"),
        ("size_cohorts", "Cumulative size cohorts (overlapping)"),
        ("age_cohorts", "Cumulative age cohorts (overlapping)"),
        ("size_bands", "Disjoint size bands (additive)"),
        ("age_bands", "Disjoint age bands (additive)"),
    ]
    for key, title in tables:
        table = Table(title=Text(title), show_lines=False)
        for heading in ("Group / sender", "Messages", "Estimated size", "Size unknown"):
            table.add_column(heading, justify="left" if heading == "Group / sender" else "right")
        for label, row in _rows(report, key):
            table.add_row(
                *(
                    Text(terminal_safe(v))
                    for v in (
                        label,
                        _number(row["count"]),
                        _bytes(row["estimated_bytes"]),
                        _number(row.get("unknown_size_count", 0)),
                    )
                )
            )
        console.print(table)
    line(
        f"Newsletter candidates: {report['newsletters']['count']} | "
        f"Estimated size: {_bytes(report['newsletters']['estimated_bytes'])} | Not disposable by default"
    )
    findings = report.get("attachment_findings")
    if findings is None:
        line("Attachment comparison: not run (separate opt-in read pass).")
    else:
        line("Attachment comparison: ADVISORY ONLY")
        line(findings.get("warning", "Equal content does not imply duplicate messages."))
        for key in ("possible_matches", "equal_content"):
            line(f"{key}: {len(findings.get(key, []))} groups")
            for group in findings.get(key, []):
                line(
                    f"  {group.get('filename', group.get('sha256', 'Unknown'))} | "
                    f"{_bytes(group.get('decoded_size'))} decoded per part"
                )
                for member in group.get("members", []):
                    line(
                        f"    {member.get('filename', '')} | message {member.get('message_id', '')} "
                        f"part {member.get('part_id', '')}"
                    )
    line("Cautions")
    for warning in report["warnings"]:
        line(" - " + warning)
    return out.getvalue()
