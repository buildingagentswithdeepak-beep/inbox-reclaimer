"""Immutable sender-cleanup scope. Neither a digest nor a flag is human consent."""

from dataclasses import dataclass
import math
import re
import time
from dataclasses import field

from ..analytics import parse_sender
from ..models import GateClosed, canonical_digest

POLICY_VERSION = "sender-v1"


def exact_sender(value: str) -> str:
    # Intentionally a conservative mailbox syntax, not a Gmail search expression.
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value
    ):
        raise ValueError("Supply one exact sender email address, not a name, domain or search query")
    parsed = parse_sender(value)
    if not parsed:
        raise ValueError("Invalid sender email address")
    return parsed


def release_status():
    """Build-time release decision shared by the gate and local reporting.

    Deliberately not configurable by CLI flags or environment variables.
    """
    return {"live_mutation_released": True, "release_gate": "B_passed", "candidate_cap": 1000}


def require_live_release(validation=None):
    if validation is not None:
        from .validation_scope import DisposableValidation

        if type(validation) is not DisposableValidation:
            raise GateClosed("Invalid disposable validation scope; refusing production fallback")
        validation.check()
        return
    if release_status()["live_mutation_released"]:
        return
    raise GateClosed(
        "Live sender trash/restore is not released: Gate B recovery/resume and release "
        "verification must pass. The separate disposable-account validation path is not "
        "a production release. No command flag or environment variable bypasses this gate."
    )


@dataclass(frozen=True)
class SenderPlan:
    account_id: str
    plan_id: str
    sender: str
    ids: tuple[str, ...]
    action: str = "trash"
    source_plan_id: str | None = None
    created_at: float = field(default_factory=time.time)
    policy_version: str = POLICY_VERSION

    def __post_init__(self):
        if (
            not isinstance(self.account_id, str)
            or not re.fullmatch("[a-f0-9]{64}", self.account_id)
            or not isinstance(self.plan_id, str)
            or not self.plan_id
        ):
            raise ValueError("Invalid account or plan reference")
        if self.sender != exact_sender(self.sender):
            raise ValueError("Sender must use the canonical parsed mailbox address")
        if (
            not isinstance(self.ids, tuple)
            or not 1 <= len(self.ids) <= 1000
            or any(not isinstance(i, str) or not i for i in self.ids)
            or tuple(sorted(set(self.ids))) != self.ids
        ):
            raise ValueError("Sender plan requires 1..1000 sorted unique IDs")
        if self.action not in {"trash", "restore"}:
            raise ValueError("Only trash and restore are supported")
        if (self.action == "restore") != bool(self.source_plan_id):
            raise ValueError("Restore must bind its source trash plan")
        if (
            self.policy_version != POLICY_VERSION
            or type(self.created_at) not in (int, float)
            or not math.isfinite(self.created_at)
            or self.created_at < 0
        ):
            raise ValueError("Unsupported policy or timestamp")
        # SQLite REAL round-trips integers as floats; canonicalize before hashing.
        object.__setattr__(self, "created_at", float(self.created_at))

    @property
    def digest(self):
        return canonical_digest(
            {
                "account_id": self.account_id,
                "plan_id": self.plan_id,
                "sender": self.sender,
                "ids": self.ids,
                "action": self.action,
                "source_plan_id": self.source_plan_id,
                "created_at": self.created_at,
                "policy_version": self.policy_version,
            }
        )


@dataclass(frozen=True)
class Approval:
    account_id: str
    plan_id: str
    digest: str
    action: str
    principal: str
    event_id: str
    challenge_id: str
    issued_at: float
    expires_at: float
