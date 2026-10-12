"""Durable conservative daily reservations, separate from mutation evidence.

First-ever identity reads use a profile-local provisional bucket. Binding moves
that budget to the verified account; the journal's single-account rule applies.
Reservations survive failures/process death and may overcount undelivered reads.
"""

from __future__ import annotations

import sqlite3
import time

from .models import IdentityMismatch
from .quota import DailyBudgetExceeded
from .storage import JournalStore

_UNBOUND = "unbound-profile-preflight"


class PersistentBudgetLimiter:
    def __init__(self, base_limiter, journal_path, account_id=None, *, wall_clock=time.time):
        self.base = base_limiter
        self.wall_clock = wall_clock
        self._closed = False
        with JournalStore(journal_path):
            pass
        self.conn = sqlite3.connect(journal_path, timeout=30)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.executescript("""
          CREATE TABLE IF NOT EXISTS quota_reservations (
            reservation_id INTEGER PRIMARY KEY, account_id TEXT NOT NULL,
            reserved_at REAL NOT NULL, cost INTEGER NOT NULL CHECK(cost>0));
          CREATE INDEX IF NOT EXISTS quota_window ON quota_reservations(account_id,reserved_at);
        """)
        known = self.conn.execute("SELECT account_id FROM accounts").fetchone()
        if known and account_id is not None and known[0] != account_id:
            self.close()
            raise IdentityMismatch("Quota context differs from the bound account")
        self.account_id = known[0] if known else account_id

    @property
    def config(self):
        return self.base.config

    @property
    def units_used(self):
        return self.base.units_used

    def bind_account(self, account_id):
        if self.account_id is not None and self.account_id != account_id:
            raise IdentityMismatch("Quota reservations cannot migrate to another account")
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            known = self.conn.execute("SELECT account_id FROM accounts").fetchone()
            if not known or known[0] != account_id:
                raise IdentityMismatch("Bind the verified journal account before adopting quota reservations")
            self.conn.execute(
                "UPDATE quota_reservations SET account_id=? WHERE account_id=?", (account_id, _UNBOUND)
            )
        self.account_id = account_id

    def reserved_units(self):
        return self.conn.execute(
            "SELECT COALESCE(SUM(cost),0) FROM quota_reservations "
            "WHERE account_id IN (?,?) AND reserved_at>?",
            (self.account_id or _UNBOUND, _UNBOUND, self.wall_clock() - 86400),
        ).fetchone()[0]

    def acquire(self, method, *, priority=False):
        cost = self.config.method_costs[method]
        now = self.wall_clock()
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            used = self.conn.execute(
                "SELECT COALESCE(SUM(cost),0) FROM quota_reservations "
                "WHERE account_id IN (?,?) AND reserved_at>?",
                (self.account_id or _UNBOUND, _UNBOUND, now - 86400),
            ).fetchone()[0]
            if self.config.daily_budget is not None and used + cost > self.config.daily_budget:
                raise DailyBudgetExceeded(
                    "Durable local daily quota budget exhausted; wait or explicitly change the budget"
                )
            self.conn.execute(
                "INSERT INTO quota_reservations(account_id,reserved_at,cost) VALUES (?,?,?)",
                (self.account_id or _UNBOUND, now, cost),
            )
            # This is expendable quota accounting, never operation/audit evidence.
            self.conn.execute(
                "DELETE FROM quota_reservations WHERE account_id=? AND reserved_at<=?",
                (self.account_id or _UNBOUND, now - 86400),
            )
        # A crash between reservation and this call consumes conservative budget;
        # it cannot leave an unaccounted Google request or an open DB transaction.
        return self.base.acquire(method, priority=priority)

    def close(self):
        if not self._closed:
            self.conn.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
