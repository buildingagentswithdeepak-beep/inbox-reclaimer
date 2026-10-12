"""Acknowledge externally restored state; never send a Gmail mutation or rewrite history."""

from dataclasses import dataclass, replace
import json
import math
import re
import time

from ..models import IdentityMismatch, ReclaimError, canonical_digest
from .confirmation import confirm_plan
from .journal import image, _json
from .models import release_status


@dataclass(frozen=True)
class ReconciliationPlan:
    account_id: str
    operation_id: str
    observation_json: str
    created_at: float
    # Absent for the original four-field format: its digest must never change.
    evidence_json: str | None = None

    def __post_init__(self):
        if not re.fullmatch("[a-f0-9]{64}", self.account_id) or not re.fullmatch(
            "[a-f0-9]{32}", self.operation_id
        ):
            raise ValueError("Invalid reconciliation reference")
        if (
            type(self.created_at) not in (int, float)
            or not math.isfinite(self.created_at)
            or self.created_at < 0
        ):
            raise ValueError("Invalid reconciliation timestamp")
        if _json(image(json.loads(self.observation_json))) != self.observation_json:
            raise ValueError("Invalid reconciliation observation")
        if self.evidence_json is not None:
            evidence = json.loads(self.evidence_json)
            if (
                not isinstance(evidence, dict)
                or set(evidence) != {"source", "operations"}
                or _json(evidence) != self.evidence_json
                or not isinstance(evidence["operations"], list)
                or not evidence["operations"]
                or evidence["source"]["operation_id"] != self.operation_id
                or evidence["source"]["account_id"] != self.account_id
                or _json(image(evidence["source"]["preimage"])) != self.observation_json
            ):
                raise ValueError("Invalid reconciliation group evidence")
        object.__setattr__(self, "created_at", float(self.created_at))

    @property
    def plan_id(self):
        return "reconcile-" + self.operation_id

    @property
    def action(self):
        return "reconcile_external"

    @property
    def sender(self):
        return json.loads(self.observation_json)["sender"]

    @property
    def ids(self):
        return (json.loads(self.observation_json)["id"],)

    @property
    def digest(self):
        values = dict(
            account_id=self.account_id,
            operation_id=self.operation_id,
            action=self.action,
            observation=self.observation_json,
            created_at=self.created_at,
        )
        if self.evidence_json is not None:
            values["evidence"] = self.evidence_json
        return canonical_digest(values)


def _observe(adapter, identity, operation, clock):
    stamp = clock()
    if adapter.resolve_identity() != identity:
        raise IdentityMismatch("Reconciliation account changed")
    message = adapter.get_metadata(operation["message_id"])
    if adapter.resolve_identity() != identity:
        raise IdentityMismatch("Reconciliation account changed")
    if image(message) != operation["preimage"]:
        raise ReclaimError(
            "Message does not match its pre-trash state. Restore it in Gmail first, preserving all original labels; no reconciliation recorded."
        )
    if not 0 <= clock() - stamp <= 10:
        raise ReclaimError("Reconciliation read is stale; no reconciliation recorded")
    return replace(message, subject=None, headers={}), stamp


def reconcile_external(
    journal,
    adapter,
    identity,
    sender,
    *,
    confirm=None,
    clock=time.time,
    guard=None,
    operation_id=None,
    validation=True,
):
    """Read/acknowledge one recovery group; the operator performs all Gmail recovery.

    The caller holds the account lock. Explicit selection accepts either a source
    trash ID or a member restore ID; it never expands to other message groups.
    """
    if type(validation) is not bool:
        raise ValueError("Invalid validation disclosure")
    target = journal.external_recovery_target(identity.account_id, sender, operation_id)
    operation, evidence = target["source"], target["evidence_json"]
    message, stamp = _observe(adapter, identity, operation, clock)
    plan = ReconciliationPlan(
        identity.account_id, operation["operation_id"], _json(image(message)), stamp, evidence
    )
    decision = (confirm or confirm_plan)(plan, identity, (message,), validation=validation)
    if decision is None:
        return {
            "decision": "rejected",
            "reconciled": 0,
            "mail_changed": False,
            "production_released": release_status()["live_mutation_released"],
        }
    # Human review may be slow; re-read and verify again after confirmation.
    current, stamp = _observe(adapter, identity, operation, clock)
    if guard is not None:
        guard()
    if adapter.resolve_identity() != identity:
        raise IdentityMismatch("Reconciliation account changed")
    journal.record_external_recovery(plan, decision, current, stamp)
    return {
        "reconciled": 1,
        "original_outcome": "interrupted_restore" if evidence is not None else "unknown",
        "disposition": "externally_restored",
        "mail_changed": False,
        "blocked": journal.blocked(identity.account_id),
        "production_released": release_status()["live_mutation_released"],
    }
