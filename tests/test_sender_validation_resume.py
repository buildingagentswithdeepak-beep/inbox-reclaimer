"""Disposable validation resumes stay independently bounded and locally confirmed."""

from uuid import uuid4
import pytest
import test_sender_validation as fixtures

from inbox_reclaimer.sender import validation as v
from inbox_reclaimer.sender.models import SenderPlan

isolated = fixtures.isolated
engine = fixtures.engine


def test_validation_resume_existing_plan_uses_new_native_confirmation_without_selection(engine, monkeypatch):
    paths, scope, adapter, journal, writers = engine
    plan = SenderPlan(adapter.identity.account_id, uuid4().hex, scope.sender, ("a",))
    journal.save_plan(plan)
    monkeypatch.setattr(v, "select_sender", lambda *a, **k: pytest.fail("resume enumerated mail"))
    monkeypatch.setattr(v, "confirm_plan", fixtures.approve)
    result = v.run_action(paths, scope, "resume", resume_plan=plan.plan_id)
    assert result["plan_id"] == plan.plan_id and result["result"]["counts"]["confirmed"] == 1
    assert adapter.calls == [("trash", "a")] and len(writers) == 1
    monkeypatch.setattr(v, "confirm_plan", lambda *a, **k: pytest.fail("completed workflow prompted"))
    again = v.run_action(paths, scope, "resume", resume_plan=plan.plan_id)
    assert again["result"]["replayed_result"]
    assert adapter.calls == [("trash", "a")] and len(writers) == 1


@pytest.mark.parametrize("ids,sender", [(tuple("abcdef"), None), (("a",), "other@example.test")])
def test_validation_resume_rejects_out_of_scope_frozen_plan(engine, monkeypatch, ids, sender):
    paths, scope, adapter, journal, writers = engine
    plan = SenderPlan(adapter.identity.account_id, uuid4().hex, sender or scope.sender, ids)
    journal.save_plan(plan)
    monkeypatch.setattr(v, "confirm_plan", lambda *a, **k: pytest.fail("out-of-scope confirmation"))
    with pytest.raises(v.ReclaimError, match="bounded validation"):
        v.run_action(paths, scope, "resume", resume_plan=plan.plan_id)
    assert not writers and not adapter.calls


def test_validation_resume_cancel_persists_rejection_without_writer(engine, monkeypatch):
    paths, scope, adapter, journal, writers = engine
    plan = SenderPlan(adapter.identity.account_id, uuid4().hex, scope.sender, ("a",))
    journal.save_plan(plan)
    monkeypatch.setattr(v, "confirm_plan", lambda *a, **k: None)
    assert v.run_action(paths, scope, "resume", resume_plan=plan.plan_id)["decision"] == "rejected"
    assert not writers and not adapter.calls
