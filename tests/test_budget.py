import pytest

from inbox_reclaimer.budget import PersistentBudgetLimiter
from inbox_reclaimer.models import Identity, IdentityMismatch
from inbox_reclaimer.quota import DailyBudgetExceeded, QuotaConfig, QuotaLimiter
from inbox_reclaimer.storage import JournalStore


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def limiter(path, clock, budget=40):
    return PersistentBudgetLimiter(
        QuotaLimiter(QuotaConfig(daily_budget=budget), clock=clock, sleep=clock.sleep), path, wall_clock=clock
    )


def test_budget_is_reserved_before_dispatch_and_survives_restart(tmp_path):
    path = tmp_path / "journal.db"
    clock = Clock()
    with JournalStore(path):
        pass
    with limiter(path, clock) as first:
        assert first.acquire("get") == 20
    with limiter(path, clock) as second:
        assert second.acquire("get") == 20
        with pytest.raises(DailyBudgetExceeded):
            second.acquire("profile")
        assert second.reserved_units() == 40
    clock.now += 86401
    with limiter(path, clock) as third:
        assert third.acquire("get") == 20


def test_first_account_adopts_preflight_budget_and_switch_fails(tmp_path):
    path = tmp_path / "journal.db"
    clock = Clock()
    identity = Identity("owner@example.test", "client")
    with JournalStore(path) as journal, limiter(path, clock, 100) as quota:
        quota.acquire("profile")
        journal.bind_account(identity)
        quota.bind_account(identity.account_id)
        assert quota.reserved_units() == 1
        with pytest.raises(IdentityMismatch):
            quota.bind_account("different-account")
    with limiter(path, clock, 100) as quota:
        assert quota.account_id == identity.account_id
        assert quota.reserved_units() == 1


def test_quota_storage_failure_stops_before_base_dispatch(tmp_path):
    path = tmp_path / "journal.db"
    clock = Clock()
    with JournalStore(path):
        pass
    with limiter(path, clock) as quota:
        quota.conn.execute(
            "CREATE TRIGGER fail_budget BEFORE INSERT ON quota_reservations BEGIN SELECT RAISE(ABORT,'disk full'); END"
        )
        with pytest.raises(Exception, match="disk full"):
            quota.acquire("get")
        assert quota.units_used == 0


def test_clock_rollback_does_not_forget_future_reservations(tmp_path):
    path = tmp_path / "journal.db"
    clock = Clock()
    with JournalStore(path):
        pass
    with limiter(path, clock, 20) as quota:
        quota.acquire("get")
    clock.now -= 60
    with limiter(path, clock, 20) as quota:
        with pytest.raises(DailyBudgetExceeded):
            quota.acquire("get")
