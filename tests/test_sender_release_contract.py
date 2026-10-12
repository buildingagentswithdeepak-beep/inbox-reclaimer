"""Release-candidate production composition with offline SDK doubles, never live credentials."""

import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_sender_google as sdk

from inbox_reclaimer.models import GateClosed
from inbox_reclaimer.profile import ProfilePaths, account_lock
from inbox_reclaimer.sender import models, commands
from inbox_reclaimer.sender.gmail import GoogleSenderReader
from inbox_reclaimer.sender.journal import SenderJournal
from inbox_reclaimer.sender.models import Approval, SenderPlan
from inbox_reclaimer.storage import JournalStore

google = sdk.google


def test_actual_release_enables_only_bounded_sender_workflow():
    assert models.release_status() == {
        "live_mutation_released": True,
        "release_gate": "B_passed",
        "candidate_cap": 1000,
    }
    models.require_live_release()
    with pytest.raises(ValueError):
        SenderPlan("a" * 64, "plan", "x@y.test", ("a",), action="permanent_delete")


@pytest.fixture
def candidate_gate(monkeypatch):
    # Review the enabled branch without changing the release decision on disk.
    monkeypatch.setattr(
        models,
        "release_status",
        lambda: {
            "live_mutation_released": True,
            "release_gate": "B_passed",
            "candidate_cap": 1000,
        },
    )


def test_production_composition_roundtrip_and_completed_resume_without_gate_bypass(
    google, tmp_path, monkeypatch
):
    base, service, *_ = google
    message = service.responses["get"]
    service.responses["thread"] = {"id": "t", "messages": [message]}
    execute = sdk.Request.execute

    def simulated_sdk(self, *, num_retries):
        response = execute(self, num_retries=num_retries)
        if self.method == "batchModify":
            message["labelIds"] = ["TRASH"]
        elif self.method == "untrash":
            message["labelIds"] = []
        elif self.method == "modify":
            message["labelIds"] = ["INBOX"]
        return response

    monkeypatch.setattr(sdk.Request, "execute", simulated_sdk)
    approvals = []

    def approve(plan, identity, messages, **kwargs):
        assert kwargs["synthetic"] is False
        assert tuple(m.id for m in messages) == plan.ids
        assert models.release_status()["live_mutation_released"]
        approvals.append(plan.action)
        now = time.time()
        return Approval(
            plan.account_id,
            plan.plan_id,
            plan.digest,
            plan.action,
            "synthetic-native-event",
            uuid4().hex,
            uuid4().hex,
            now,
            now + 900,
        )

    monkeypatch.setattr("inbox_reclaimer.sender.confirmation.confirm_plan", approve)
    paths = ProfilePaths(tmp_path)
    paths.initialize()
    identity = base.resolve_identity()
    options = SimpleNamespace(demo=False)
    reader = GoogleSenderReader(base)
    with account_lock(paths, identity.account_id), JournalStore(paths.journal) as store:
        store.bind_account(identity)
        journal = SenderJournal(store)
        trash = SenderPlan(identity.account_id, uuid4().hex, "x@y.test", ("a",))
        journal.save_plan(trash)
        result = commands._perform(paths, options, base, reader, identity, journal, trash)
        assert result["status"] == "sender_run_finished"
        restore = SenderPlan(
            identity.account_id,
            uuid4().hex,
            trash.sender,
            trash.ids,
            action="restore",
            source_plan_id=trash.plan_id,
        )
        journal.save_plan(restore)
        result = commands._perform(paths, options, base, reader, identity, journal, restore)
        assert result["status"] == "sender_run_finished"
        assert message["labelIds"] == ["INBOX"]
        assert approvals == ["trash", "restore"]
        assert not journal.blocked(identity.account_id)
        before = list(service.executions)
        monkeypatch.setattr(
            "inbox_reclaimer.sender.gmail.GoogleSenderWriter",
            lambda *_: pytest.fail("completed run constructed writer"),
        )
        assert commands._perform(paths, options, base, reader, identity, journal, trash)["replayed_result"]
        assert service.executions == before
    assert [m for m in service.executions if m in ("batchModify", "untrash", "modify")] == [
        "batchModify",
        "untrash",
        "modify",
    ]


def test_enabled_release_does_not_allow_noninteractive_or_model_control(candidate_gate, monkeypatch):
    monkeypatch.setattr(commands.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(commands.sys.stdout, "isatty", lambda: False)
    from inbox_reclaimer.models import ReclaimError

    for hermes in (False, True):
        with pytest.raises(ReclaimError):
            commands._execution_preflight(SimpleNamespace(demo=False, hermes=hermes), True)


@pytest.mark.parametrize("invalid", [True, False, {}, object()])
def test_enabled_gate_does_not_turn_invalid_validation_scope_into_production(invalid, candidate_gate):
    with pytest.raises(GateClosed):
        models.require_live_release(invalid)


def test_closed_release_remains_fail_closed_despite_environment(monkeypatch):
    monkeypatch.setattr(models, "release_status", lambda: {"live_mutation_released": False})
    monkeypatch.setenv("RECLAIM_GATE_B", "true")
    with pytest.raises(GateClosed):
        models.require_live_release()
