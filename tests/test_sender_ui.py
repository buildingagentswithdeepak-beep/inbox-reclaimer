from dataclasses import replace
import time

import pytest

from inbox_reclaimer.models import Identity, Message
from inbox_reclaimer.sender.models import SenderPlan


def fixture():
    identity = Identity("owner@example.test", "client")
    plan = SenderPlan(identity.account_id, "plan", "news@example.test", ("one",))
    message = Message("one", "t", 1000, 100, frozenset(), "news@example.test", "<script>private</script>")
    return identity, plan, (message,)


def test_native_confirmation_requires_exact_account_and_checked_warning():
    from inbox_reclaimer.sender.confirmation import ConfirmationWindow
    import tkinter as tk

    identity, plan, messages = fixture()
    root = tk.Tk()
    root.withdraw()
    try:
        window = ConfirmationWindow(root, plan, identity, messages, synthetic=True)
        assert window.decision is None
        assert window.confirm_button.instate(["disabled"])
        window.email.set(identity.email)
        window.update_enabled()
        assert window.confirm_button.instate(["disabled"])
        window.acknowledged.set(True)
        window.update_enabled()
        assert not window.confirm_button.instate(["disabled"])
        assert len(window.table.get_children()) == 1
        window.accept()
        assert window.decision.digest == plan.digest
        assert window.decision.action == "trash"
        assert window.decision.expires_at - window.decision.issued_at == 900
        assert window.decision.issued_at <= time.time()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_native_window_refuses_wrong_account_or_membership():
    from inbox_reclaimer.sender.confirmation import validate_preview

    identity, plan, messages = fixture()
    with pytest.raises(ValueError):
        validate_preview(plan, identity, ())
    with pytest.raises(ValueError):
        validate_preview(plan, replace(identity, email="other@example.test"), messages)


@pytest.mark.parametrize("action", ["trash", "restore"])
@pytest.mark.parametrize("sender", ["other@example.test", "broken", None])
def test_confirmation_rejects_sender_mismatch_even_with_matching_ids(action, sender):
    from inbox_reclaimer.sender.confirmation import validate_preview

    identity, plan, messages = fixture()
    if action == "restore":
        plan = replace(plan, action="restore", source_plan_id="source")
    with pytest.raises(ValueError):
        validate_preview(plan, identity, (replace(messages[0], raw_from=sender),))


def test_confirmation_accepts_matching_canonical_sender_with_display_name():
    from inbox_reclaimer.sender.confirmation import validate_preview

    identity, plan, messages = fixture()
    validate_preview(plan, identity, (replace(messages[0], raw_from="News <news@EXAMPLE.TEST>"),))


def test_sender_html_is_escaped_and_includes_full_exact_list():
    from inbox_reclaimer.sender.render import preview_html, summary
    from inbox_reclaimer.sender.selection import SenderSelection

    identity, plan, messages = fixture()
    selection = SenderSelection(plan.sender, 1000, 1, True, plan, messages, {})
    html = preview_html(selection, identity, synthetic=True)
    assert "<script>private</script>" not in html
    assert "&lt;script&gt;private&lt;/script&gt;" in html
    assert "one" in html and "SYNTHETIC" in html
    assert "30 days" in html
    assert "No approval" in html
    assert summary(selection, minimized=True)["eligible_count"] == 1
    assert "@" not in str(summary(selection, minimized=True))
