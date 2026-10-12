import pytest
from inbox_reclaimer.quota import QuotaLimiter, QuotaConfig, DailyBudgetExceeded


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, delay):
        assert delay > 0
        self.sleeps.append(delay)
        self.now += delay


def limiter(**kwargs):
    clock = Clock()
    return QuotaLimiter(QuotaConfig(**kwargs), clock=clock, sleep=clock.sleep), clock


def test_documented_costs_and_smooth_default_pacing():
    q, c = limiter(reserve_units=0)
    assert q.config.method_costs == {
        "profile": 1,
        "list": 5,
        "get": 20,
        "thread": 40,
        "history": 2,
        "attachments": 20,
        "trash": 50,
        "untrash": 5,
        "modify": 5,
    }
    q.acquire("get")
    q.acquire("get")
    assert c.now == pytest.approx(0.25)
    assert q.units_used == 40


def test_lower_effective_limit_and_rolling_window_with_mixed_costs():
    q, c = limiter(
        planning_per_minute=100,
        effective_project_per_minute=60,
        reserve_units=0,
        method_costs={"get": 40, "profile": 1},
    )
    q.acquire("get")
    q.acquire("get")
    assert c.now >= 60
    assert q.effective_per_minute == 60


def test_daily_budget_fail_closed_and_rolls_after_24_hours():
    q, c = limiter(daily_budget=40, reserve_units=0)
    q.acquire("get")
    q.acquire("get")
    with pytest.raises(DailyBudgetExceeded):
        q.acquire("profile")
    c.now += 86400
    q.acquire("get")
    assert q.units_used == 60


def test_reservation_available_only_for_required_reads():
    q, c = limiter(planning_per_minute=60, reserve_units=20, method_costs={"get": 40, "profile": 20})
    q.acquire("get")
    q.acquire("profile", priority=True)
    assert c.now < 60
    q.acquire("get")
    assert c.now >= 60


def test_invalid_config_and_unknown_methods_fail_before_sleep():
    with pytest.raises(ValueError):
        QuotaConfig(planning_per_minute=0)
    q, c = limiter()
    with pytest.raises(ValueError):
        q.acquire("delete")
    assert c.sleeps == []


def test_long_mixed_cost_sequence_never_exceeds_rolling_limit():
    q, c = limiter(
        planning_per_minute=100,
        effective_user_per_minute=90,
        reserve_units=10,
        method_costs={"get": 20, "list": 5, "profile": 1},
    )
    history = []
    for index in range(120):
        method = ["get", "list", "profile"][index % 3]
        priority = method == "profile"
        cost = q.acquire(method, priority=priority)
        history.append((c.now, cost, priority))
        recent = [(t, n, p) for t, n, p in history if t > c.now - 60]
        assert sum(n for _, n, _ in recent) <= 90
        assert sum(n for _, n, p in recent if not p) <= 80


def test_impossible_cost_fails_instead_of_waiting_forever():
    q, c = limiter(planning_per_minute=30, reserve_units=10, method_costs={"get": 21})
    with pytest.raises(ValueError):
        q.acquire("get")
    assert not c.sleeps


def test_config_costs_cannot_mutate_after_validation():
    costs = {"get": 20}
    config = QuotaConfig(method_costs=costs)
    costs["get"] = -1
    assert config.method_costs["get"] == 20
    with pytest.raises(TypeError):
        config.method_costs["get"] = 1
