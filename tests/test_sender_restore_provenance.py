"""Stale restore source regressions using synthetic mailbox transitions only."""

from dataclasses import replace
import sqlite3
from uuid import uuid4

import pytest
import test_sender_execution as fixtures

from inbox_reclaimer.sender.journal import _json, image

env = fixtures.env


@pytest.fixture
def retrash(env):
    adapter, store, journal, executor, clock = env
    first, approval = fixtures.plan_for(env)
    assert executor.execute(first, approval, dry_run=False)["confirmed"] == 1
    stale_restore, stale_approval = fixtures.plan_for(env, action="restore", source=first.plan_id)
    # External untrash/archive; a later Trash has the same postimage but a
    # different original Inbox state. Wall-clock timestamps remain equal.
    adapter.messages["a"] = replace(adapter.messages["a"], labels=adapter.messages["a"].labels - {"TRASH"})
    second_original = adapter.messages["a"]
    second, second_approval = fixtures.plan_for(env)
    assert executor.execute(second, second_approval, dry_run=False)["confirmed"] == 1
    assert (
        journal.operations(first.account_id, first.plan_id)[0]["postimage"]
        == journal.operations(second.account_id, second.plan_id)[0]["postimage"]
    )
    return env, first, second, second_original, stale_restore, stale_approval


def test_old_trash_cannot_restore_labels_from_before_new_trash(retrash):
    env, first, second, second_original, stale_restore, stale_approval = retrash
    adapter, _, journal, executor, _ = env
    calls = list(adapter.calls)
    with pytest.raises(ValueError, match="superseded"):
        fixtures.plan_for(env, action="restore", source=first.plan_id)
    with pytest.raises(ValueError, match="superseded"):
        executor.restore(stale_restore, stale_approval, dry_run=False)
    assert adapter.calls == calls
    current_restore, approval = fixtures.plan_for(env, action="restore", source=second.plan_id)
    assert executor.restore(current_restore, approval, dry_run=False)["confirmed"] == 1
    assert adapter.messages["a"].labels == second_original.labels
    assert "INBOX" not in adapter.messages["a"].labels


def test_sql_intent_guard_rejects_superseded_restore_source(retrash):
    env, first, _, _, stale_restore, stale_approval = retrash
    adapter, store, journal, _, clock = env
    source = journal.operations(first.account_id, first.plan_id)[0]
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO sender_operations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                uuid4().hex,
                first.account_id,
                stale_restore.plan_id,
                stale_approval,
                "a",
                "restore",
                "untrash",
                source["operation_id"],
                0,
                "pending",
                _json(image(adapter.messages["a"])),
                None,
                None,
                clock[0],
                clock[0],
            ),
        )
    store.conn.rollback()


@pytest.mark.parametrize("state", ["pending", "unknown", "failed", "skipped"])
def test_newer_trash_intent_conservatively_supersedes_old_source(env, state):
    adapter, _, journal, executor, _ = env
    first, approval = fixtures.plan_for(env)
    assert executor.execute(first, approval, dry_run=False)["confirmed"] == 1
    adapter.messages["a"] = replace(adapter.messages["a"], labels=adapter.messages["a"].labels - {"TRASH"})
    second, approval = fixtures.plan_for(env)
    operation = journal.begin(second, approval, "a", "trash", adapter.messages["a"])
    if state != "pending":
        journal.finish(operation, state, reason="synthetic_fault")
    with pytest.raises(ValueError, match="superseded"):
        fixtures.plan_for(env, action="restore", source=first.plan_id)
