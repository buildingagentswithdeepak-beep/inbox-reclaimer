import pytest
from inbox_reclaimer.models import GateClosed


def test_sender_scope_digest_and_validation():
    from inbox_reclaimer.sender.models import SenderPlan
    from dataclasses import replace

    p = SenderPlan("a" * 64, "plan", "sender@example.test", ("1", "2"), created_at=1)
    assert p.digest == replace(p, created_at=1.0).digest
    assert p.digest != replace(p, sender="other@example.test").digest
    assert p.digest != replace(p, account_id="b" * 64).digest
    assert p.digest != replace(p, ids=("1",)).digest
    with pytest.raises(ValueError):
        replace(p, ids=("1", "1"))
    with pytest.raises(ValueError):
        replace(p, sender="from:a OR newer:2020")
    with pytest.raises(ValueError):
        replace(p, action="permanent_delete")


def test_sender_scope_rejects_ambiguous_ids_timestamps_and_restore_source():
    from dataclasses import replace
    from inbox_reclaimer.sender.models import SenderPlan

    plan = SenderPlan("a" * 64, "plan", "news@example.test", ("id",))
    for values in (
        {"created_at": True},
        {"created_at": float("nan")},
        {"plan_id": 1},
        {"ids": ()},
        {"ids": tuple(str(i) for i in range(1001))},
        {"action": "restore"},
        {"source_plan_id": "unrelated"},
    ):
        with pytest.raises(ValueError):
            replace(plan, **values)


def test_live_release_cannot_be_enabled_by_environment(monkeypatch):
    from inbox_reclaimer.sender.models import require_live_release

    monkeypatch.setattr(
        "inbox_reclaimer.sender.models.release_status", lambda: {"live_mutation_released": False}
    )

    monkeypatch.setenv("RECLAIM_GATE_B", "true")
    with pytest.raises(GateClosed, match="disposable-account"):
        require_live_release()
