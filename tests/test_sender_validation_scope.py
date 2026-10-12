from dataclasses import replace
from pathlib import Path
import time

import pytest

from inbox_reclaimer.models import GateClosed, Identity
from inbox_reclaimer.sender.models import require_live_release


def scope(**kwargs):
    from inbox_reclaimer.sender.validation_scope import DisposableValidation

    return DisposableValidation("owner@example.test", "news@example.test", **kwargs)


def test_arbitrary_objects_never_bypass_validation_scope():
    for value in (False, True, {}, object()):
        with pytest.raises(GateClosed):
            require_live_release(value)


def test_validation_scope_requires_fresh_finite_time():
    s = scope()
    require_live_release(s)
    for stamp in (True, float("nan"), float("inf"), time.time() - 901, time.time() + 30):
        with pytest.raises((GateClosed, ValueError)):
            require_live_release(replace(s, created_at=stamp))


def test_validation_home_and_account_are_bound(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    s = scope()
    s.check_home(tmp_path / "inbox-reclaimer-validation")
    with pytest.raises(GateClosed):
        s.check_home(tmp_path / "ordinary-profile")
    s.check_account(Identity("owner@example.test", "client"))
    with pytest.raises(GateClosed):
        s.check_account(Identity("other@example.test", "client"))
    bound = replace(s, account_id=Identity("owner@example.test", "client").account_id, ids=("id",))
    with pytest.raises(GateClosed):
        bound.check_account(Identity("owner@example.test", "different-client"))


def test_scope_rejects_symlink_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    target = tmp_path / "ordinary"
    target.mkdir()
    try:
        (tmp_path / "inbox-reclaimer-validation").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation privilege unavailable")
    with pytest.raises(GateClosed):
        scope().check_home(tmp_path / "inbox-reclaimer-validation")


def test_scope_rejects_linked_credential_file(tmp_path, monkeypatch):
    import os

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    home = tmp_path / "inbox-reclaimer-validation"
    home.mkdir()
    original = tmp_path / "synthetic-token.txt"
    original.write_text("synthetic")
    os.link(original, home / "google_token.json")
    with pytest.raises(GateClosed):
        scope().check_home(home)


def test_scope_freezes_at_most_five_message_ids():
    account = Identity("owner@example.test", "client").account_id
    s = scope(account_id=account, ids=("a", "b"))
    s.check_ids(["a"])
    for ids in ([], ["c"], ["a", "a"]):
        with pytest.raises(GateClosed):
            s.check_ids(ids)
    with pytest.raises(GateClosed):
        scope().check_ids(["a"])
    for ids in (("a",) * 2, tuple(str(i) for i in range(6)), ["a"]):
        with pytest.raises(ValueError):
            scope(account_id=account, ids=ids)
