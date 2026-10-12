"""Private read-only sender previews. HTML is never an approval surface."""

import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html import escape
from importlib.resources import files

from ..render import terminal_safe
from .models import release_status

WARNING = (
    "Moving messages to Trash is not permanent deletion now. Gmail normally permanently deletes "
    "Trash after 30 days. Restore requires retained journal evidence and may stop on external changes. "
    "Fresh checks can only shrink this selection; no new message is added after confirmation."
)


def display_date(value):
    try:
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return "Unknown date"


def summary(selection, minimized=False):
    result = {
        "scope": "bounded_sender_selection",
        "action": "trash",
        "candidate_limit": selection.max_messages,
        "examined_count": selection.examined_count,
        "eligible_count": len(selection.messages),
        "enumeration_exhausted": selection.exhausted,
        "skips_by_reason": dict(Counter(selection.skips.values())),
        "plan_id": selection.plan.plan_id if selection.plan else None,
        "approval_created": False,
        "mail_changed": False,
        **release_status(),
        "ordering": "gmail_list_order_not_guaranteed_newest",
    }
    if not minimized:
        result["sender"] = selection.sender
        result["digest"] = selection.plan.digest if selection.plan else None
        result["messages"] = [
            {
                "id": m.id,
                "date": display_date(m.internal_date),
                "estimated_bytes": m.size_estimate,
                "subject": m.subject,
            }
            for m in selection.messages
        ]
    return result


def preview_html(selection, identity, synthetic=False):
    css = files("inbox_reclaimer").joinpath("assets/report.css").read_text(encoding="utf-8")
    digest = base64.b64encode(hashlib.sha256(css.encode()).digest()).decode()

    def safe(value):
        return escape(terminal_safe(value), quote=True)

    rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{safe(value)}</td>"
            for value in (
                m.id,
                display_date(m.internal_date),
                m.size_estimate,
                m.subject if m.subject is not None else "[redacted]",
            )
        )
        + "</tr>"
        for m in selection.messages
    )
    plan = selection.plan
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        f'<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; '
        f'style-src &#39;sha256-{digest}&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        f"<title>Sender cleanup preview</title><style>{css}</style></head><body>"
        '<header><div class="eyebrow">INBOX RECLAIMER / SENDER CLEANUP</div>'
        "<h1>Review before moving to Trash.</h1>"
        f"<p>Exact sender: {safe(selection.sender)} · Account: {safe(identity.email)}</p>"
        '<div class="header-meta"><span class="pill warning-pill">No approval · No mail changed</span>'
        + ('<span class="pill">SYNTHETIC DEMO · NO GMAIL ACCESS</span>' if synthetic else "")
        + '</div></header><main><section class="panel"><h2>Bounded selection</h2>'
        f"<p>{len(selection.messages):,} eligible messages from {selection.examined_count:,} inspected candidates; "
        f"candidate cap {selection.max_messages:,}. Selection uses Gmail listing order, not guaranteed newest-first.</p>"
        f"<p>Plan: {safe(plan.plan_id if plan else 'No eligible messages')}<br>"
        f"Digest: {safe(plan.digest if plan else 'Not applicable')}</p>"
        f"<p>{safe(WARNING)}</p>"
        "<p>Starred, important, sent, draft, Trash/Spam, protected-sender and replied-thread exclusions apply. "
        "Thread evidence is a conservative heuristic, not proof that a conversation has never been replied to.</p>"
        "<p>Live trash/restore is release-disabled pending disposable-account Gate B verification. "
        "This HTML file cannot authorize execution.</p></section>"
        '<section class="panel"><h2>Exact eligible message list</h2><div class="table-scroll"><table>'
        "<thead><tr><th>Message ID</th><th>Date (UTC)</th><th>Estimated bytes</th><th>Subject</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div></section>"
        '<section class="panel"><h2>Excluded candidates</h2>'
        + "".join(
            f"<p>{safe(reason)}: {count}</p>" for reason, count in Counter(selection.skips.values()).items()
        )
        + "</section></main><footer>Private local preview · No scripts, remote assets or tracking. "
        "No OAuth permission or cleanup approval is granted by this report.</footer></body></html>"
    )
