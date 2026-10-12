"""Conservative, shared-session Gmail read quota accounting.

A limiter must be shared by readers using the same user/project. It is thread safe,
not a cross-process/project-wide meter. Effective limits are operator supplied;
we never infer them from account type. The optional daily cap is a conservative
rolling 24-hour *session* cap, not a claim to measure Google's billing counters.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

from .models import ReadFailure


class DailyBudgetExceeded(ReadFailure):
    """The configured local daily budget is exhausted; do not dispatch."""


@dataclass(frozen=True)
class QuotaConfig:
    version: str = "gmail-spec-v2"
    planning_per_minute: float = 4800
    user_per_minute: float = 6000
    project_per_minute: float = 1200000
    effective_user_per_minute: float | None = None
    effective_project_per_minute: float | None = None
    daily_budget: int | None = None
    reserve_units: float = 100
    method_costs: Mapping[str, int] = field(
        default_factory=lambda: {
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
    )

    def __post_init__(self):
        rates = [self.planning_per_minute, self.user_per_minute, self.project_per_minute]
        rates += [
            v for v in (self.effective_user_per_minute, self.effective_project_per_minute) if v is not None
        ]
        if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in rates):
            raise ValueError("Quota rates must be finite and positive")
        if not math.isfinite(self.reserve_units) or not 0 <= self.reserve_units < min(rates):
            raise ValueError("Reserved quota must be below the effective rate")
        if self.daily_budget is not None and (type(self.daily_budget) is not int or self.daily_budget <= 0):
            raise ValueError("Daily budget must be a positive integer")
        if not self.method_costs or any(type(v) is not int or v <= 0 for v in self.method_costs.values()):
            raise ValueError("Method costs must be positive integers")
        if not set(self.method_costs) <= {
            "profile",
            "list",
            "get",
            "thread",
            "history",
            "attachments",
            "trash",
            "untrash",
            "modify",
        }:
            raise ValueError("Unknown quota method; permanent deletion is unsupported")
        object.__setattr__(self, "method_costs", MappingProxyType(dict(self.method_costs)))


class QuotaLimiter:
    def __init__(
        self,
        config: QuotaConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.config = config or QuotaConfig()
        self.clock, self.sleep = clock, sleep
        self.effective_per_minute = min(
            v
            for v in (
                self.config.planning_per_minute,
                self.config.user_per_minute,
                self.config.project_per_minute,
                self.config.effective_user_per_minute,
                self.config.effective_project_per_minute,
            )
            if v is not None
        )
        self._ordinary_limit = self.effective_per_minute - self.config.reserve_units
        self._minute: deque[tuple[float, int, bool]] = deque()
        self._day: deque[tuple[float, int]] = deque()
        self._next = self._next_ordinary = 0.0
        self._lock = threading.Lock()
        self.units_used = 0

    def acquire(self, method: str, *, priority: bool = False) -> int:
        """Reserve one attempted call, including retries; sleep before dispatch.

        priority=True uses the reserved slice (identity/history/safety reads).
        There is no burst allowance that can evade the rolling-minute ceiling.
        An impossible single call or exhausted daily budget fails immediately.
        """
        if method not in self.config.method_costs:
            raise ValueError("Unknown read method")
        cost = self.config.method_costs[method]
        limit = self.effective_per_minute if priority else self._ordinary_limit
        if cost > limit:
            raise ValueError("Method cost exceeds available minute budget")
        with self._lock:
            while True:
                now = self.clock()
                while self._minute and self._minute[0][0] <= now - 60:
                    self._minute.popleft()
                while self._day and self._day[0][0] <= now - 86400:
                    self._day.popleft()
                if self.config.daily_budget is not None:
                    if sum(c for _, c in self._day) + cost > self.config.daily_budget:
                        raise DailyBudgetExceeded("Local rolling daily quota budget exhausted")
                target = max(now, self._next, self._next_ordinary if not priority else now)
                total = sum(c for _, c, _ in self._minute)
                ordinary = sum(c for _, c, p in self._minute if not p)
                for t, c, p in self._minute:
                    if total + cost <= self.effective_per_minute and (
                        priority or ordinary + cost <= self._ordinary_limit
                    ):
                        break
                    target = max(target, t + 60)
                    total -= c
                    if not p:
                        ordinary -= c
                delay = target - now
                if delay > 1e-9:
                    self.sleep(delay)
                    continue
                self._minute.append((now, cost, priority))
                if self.config.daily_budget is not None:
                    self._day.append((now, cost))
                self._next = now + cost * 60 / self.effective_per_minute
                if not priority:
                    self._next_ordinary = now + cost * 60 / self._ordinary_limit
                self.units_used += cost
                return cost
