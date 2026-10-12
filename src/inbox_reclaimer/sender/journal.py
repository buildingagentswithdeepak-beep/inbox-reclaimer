"""Sender evidence in the bound Gate A journal, never a second database.

This is an offline engine primitive, not an approval UI or live release gate.
The caller holds the OS account lock for the entire execution workflow. This
wrapper borrows JournalStore.conn and never closes or migrates its base schema.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
import math
import re
import time
from uuid import uuid4

from ..analytics import parse_sender
from ..models import Message
from ..proposals import _valid_message
from ..storage import JournalStore
from .models import Approval, SenderPlan


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def image(value):
    """Allowlisted evidence only; never persist headers, subjects, bodies or exceptions."""
    if isinstance(value, Message):
        if not _valid_message(value):
            raise ValueError("Invalid message evidence")
        value = dict(
            id=value.id,
            thread_id=value.thread_id,
            labels=sorted(value.labels),
            sender=parse_sender(value.raw_from),
            internal_date=value.internal_date,
            size_estimate=value.size_estimate,
        )
    if not isinstance(value, dict):
        raise ValueError("Expected metadata image")
    sender = parse_sender(value.get("sender", value.get("raw_from", "")))
    labels = value.get("labels")
    if (
        not isinstance(value.get("id"), str)
        or not value["id"]
        or not isinstance(value.get("thread_id"), str)
        or not value["thread_id"]
        or not sender
        or not isinstance(labels, (list, tuple, set, frozenset))
        or any(not isinstance(x, str) or not x for x in labels)
    ):
        raise ValueError("Invalid metadata image")
    result = {k: value[k] for k in ("id", "thread_id")}
    result.update(sender=sender, labels=sorted(set(labels)))
    for key in ("internal_date", "size_estimate"):
        if key in value:
            if type(value[key]) is not int or value[key] < 0:
                raise ValueError("Invalid metadata image size/date")
            result[key] = value[key]
    return result


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sender_plans (
 account_id TEXT NOT NULL REFERENCES accounts(account_id), plan_id TEXT NOT NULL,
 sender TEXT NOT NULL, ids_json TEXT NOT NULL CHECK(json_valid(ids_json)),
 action TEXT NOT NULL CHECK(action IN ('trash','restore')), source_plan_id TEXT,
 created_at REAL NOT NULL, policy_version TEXT NOT NULL CHECK(policy_version='sender-v1'),
 digest TEXT NOT NULL, PRIMARY KEY(account_id,plan_id),
 CHECK((action='trash' AND source_plan_id IS NULL) OR (action='restore' AND source_plan_id IS NOT NULL)),
 FOREIGN KEY(account_id,source_plan_id) REFERENCES sender_plans(account_id,plan_id));
CREATE TABLE IF NOT EXISTS sender_approvals (
 approval_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, plan_id TEXT NOT NULL,
 digest TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('trash','restore')),
 principal TEXT NOT NULL CHECK(length(trim(principal))>0),
 event_id TEXT NOT NULL UNIQUE CHECK(length(trim(event_id))>0),
 challenge_id TEXT NOT NULL UNIQUE CHECK(length(trim(challenge_id))>0),
 issued_at REAL NOT NULL, expires_at REAL NOT NULL,
 CHECK(expires_at>issued_at AND expires_at-issued_at<=900),
 FOREIGN KEY(account_id,plan_id) REFERENCES sender_plans(account_id,plan_id));
CREATE TABLE IF NOT EXISTS sender_operations (
 operation_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, plan_id TEXT NOT NULL,
 approval_id TEXT NOT NULL REFERENCES sender_approvals(approval_id), message_id TEXT NOT NULL,
 action TEXT NOT NULL, step TEXT NOT NULL CHECK(step IN ('trash','untrash','repair')),
 source_operation_id TEXT REFERENCES sender_operations(operation_id),
 dry_run INTEGER NOT NULL DEFAULT 0 CHECK(dry_run=0),
 state TEXT NOT NULL CHECK(state IN ('pending','confirmed','unknown','failed','skipped')),
 preimage_json TEXT NOT NULL CHECK(json_valid(preimage_json)),
 postimage_json TEXT CHECK(postimage_json IS NULL OR json_valid(postimage_json)), reason TEXT,
 created_at REAL NOT NULL, updated_at REAL NOT NULL,
 UNIQUE(account_id,plan_id,message_id,step), UNIQUE(approval_id,message_id,step),
 UNIQUE(source_operation_id,step),
 FOREIGN KEY(account_id,plan_id) REFERENCES sender_plans(account_id,plan_id));
CREATE INDEX IF NOT EXISTS sender_operations_recovery ON sender_operations(account_id,state);
CREATE TABLE IF NOT EXISTS sender_approval_invalidations (
 approval_id TEXT PRIMARY KEY REFERENCES sender_approvals(approval_id),
 account_id TEXT NOT NULL REFERENCES accounts(account_id),
 state TEXT NOT NULL CHECK(state IN ('revoked','expired')),
 principal TEXT NOT NULL CHECK(length(trim(principal))>0), recorded_at REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS sender_invalidation_scope BEFORE INSERT ON sender_approval_invalidations BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM sender_approvals a WHERE a.approval_id=NEW.approval_id
 AND a.account_id=NEW.account_id AND (NEW.state='revoked' OR a.expires_at<=NEW.recorded_at))
 THEN RAISE(ABORT,'invalid approval invalidation') END;
END;
CREATE TABLE IF NOT EXISTS sender_resolutions (
 operation_id TEXT PRIMARY KEY REFERENCES sender_operations(operation_id),
 account_id TEXT NOT NULL REFERENCES accounts(account_id),
 disposition TEXT NOT NULL CHECK(disposition='externally_restored'),
 plan_digest TEXT NOT NULL, observation_json TEXT NOT NULL CHECK(json_valid(observation_json)),
 approval_json TEXT NOT NULL CHECK(json_valid(approval_json)),
 event_id TEXT NOT NULL UNIQUE, challenge_id TEXT NOT NULL UNIQUE,
 observed_at REAL NOT NULL, recorded_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sender_recovery_groups (
 source_operation_id TEXT PRIMARY KEY REFERENCES sender_operations(operation_id),
 account_id TEXT NOT NULL REFERENCES accounts(account_id),
 disposition TEXT NOT NULL CHECK(disposition='externally_restored'),
 plan_json TEXT NOT NULL CHECK(json_valid(plan_json)), plan_digest TEXT NOT NULL,
 observation_json TEXT NOT NULL CHECK(json_valid(observation_json)),
 approval_json TEXT NOT NULL CHECK(json_valid(approval_json)),
 event_id TEXT NOT NULL UNIQUE CHECK(length(trim(event_id))>0),
 challenge_id TEXT NOT NULL UNIQUE CHECK(length(trim(challenge_id))>0),
 observed_at REAL NOT NULL, recorded_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sender_recovery_members (
 operation_id TEXT PRIMARY KEY REFERENCES sender_operations(operation_id),
 source_operation_id TEXT NOT NULL REFERENCES sender_recovery_groups(source_operation_id),
 evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)));
DROP VIEW IF EXISTS sender_resolved_operations;
CREATE VIEW sender_resolved_operations AS
 SELECT operation_id,account_id FROM sender_resolutions
 UNION ALL
 SELECT m.operation_id,g.account_id FROM sender_recovery_members m
 JOIN sender_recovery_groups g USING(source_operation_id)
 JOIN sender_operations s ON s.operation_id=g.source_operation_id
 WHERE s.account_id=g.account_id AND s.state='confirmed'
 AND coalesce(json_array_length(json_extract(g.plan_json,'$.evidence_json'),'$.operations'),0)>0
 AND json_array_length(json_extract(g.plan_json,'$.evidence_json'),'$.operations')=
     (SELECT count(*) FROM sender_recovery_members all_m WHERE all_m.source_operation_id=g.source_operation_id)
 AND NOT EXISTS(
     SELECT 1 FROM json_each(json_extract(g.plan_json,'$.evidence_json'),'$.operations') expected
     WHERE NOT EXISTS(SELECT 1 FROM sender_recovery_members saved
         WHERE saved.source_operation_id=g.source_operation_id
         AND saved.operation_id=json_extract(expected.value,'$.operation_id')
         AND saved.evidence_json=expected.value))
 AND NOT EXISTS(
     SELECT 1 FROM sender_operations related WHERE related.source_operation_id=g.source_operation_id
     AND NOT EXISTS(SELECT 1 FROM sender_recovery_members saved WHERE saved.operation_id=related.operation_id
                    AND saved.source_operation_id=g.source_operation_id))
 AND NOT EXISTS(
     SELECT 1 FROM sender_recovery_members saved
     LEFT JOIN sender_operations current ON current.operation_id=saved.operation_id
     WHERE saved.source_operation_id=g.source_operation_id AND (
         current.operation_id IS NULL OR current.account_id IS NOT g.account_id
         OR current.source_operation_id IS NOT g.source_operation_id
         OR current.state IS NOT json_extract(saved.evidence_json,'$.state')
         OR current.updated_at IS NOT json_extract(saved.evidence_json,'$.updated_at')
         OR current.reason IS NOT json_extract(saved.evidence_json,'$.reason')
         OR current.postimage_json IS NOT json_extract(saved.evidence_json,'$.postimage')));
CREATE TRIGGER IF NOT EXISTS sender_recovery_group_scope BEFORE INSERT ON sender_recovery_groups BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM sender_operations s
 WHERE s.operation_id=NEW.source_operation_id AND s.account_id=NEW.account_id
 AND s.action='trash' AND s.step='trash' AND s.state='confirmed' AND s.dry_run=0
 AND s.preimage_json=NEW.observation_json)
 OR EXISTS(SELECT 1 FROM sender_operations s JOIN sender_operations n
 ON n.account_id=s.account_id AND n.message_id=s.message_id
 WHERE s.operation_id=NEW.source_operation_id AND n.step='trash' AND n.rowid>s.rowid)
 THEN RAISE(ABORT,'invalid external recovery source') END;
 SELECT CASE WHEN json_extract(NEW.plan_json,'$.account_id') IS NOT NEW.account_id
 OR json_extract(NEW.plan_json,'$.operation_id') IS NOT NEW.source_operation_id
 OR json_extract(NEW.plan_json,'$.observation_json') IS NOT NEW.observation_json
 OR json_extract(NEW.approval_json,'$.account_id') IS NOT NEW.account_id
 OR json_extract(NEW.approval_json,'$.plan_id') IS NOT ('reconcile-' || NEW.source_operation_id)
 OR json_extract(NEW.approval_json,'$.digest') IS NOT NEW.plan_digest
 OR json_extract(NEW.approval_json,'$.action') IS NOT 'reconcile_external'
 OR json_extract(NEW.approval_json,'$.event_id') IS NOT NEW.event_id
 OR json_extract(NEW.approval_json,'$.challenge_id') IS NOT NEW.challenge_id
 OR coalesce(length(trim(json_extract(NEW.approval_json,'$.principal'))),0)=0
 OR NOT coalesce((json_type(NEW.approval_json,'$.issued_at') IN ('integer','real')
 AND json_type(NEW.approval_json,'$.expires_at') IN ('integer','real')
 AND json_extract(NEW.approval_json,'$.issued_at')<=NEW.recorded_at
 AND NEW.recorded_at<json_extract(NEW.approval_json,'$.expires_at')
 AND json_extract(NEW.approval_json,'$.expires_at')-json_extract(NEW.approval_json,'$.issued_at')<=900),0)
 OR NOT coalesce((NEW.recorded_at-NEW.observed_at BETWEEN 0 AND 10),0)
 OR EXISTS(SELECT 1 FROM sender_approvals WHERE event_id=NEW.event_id OR challenge_id=NEW.challenge_id)
 OR EXISTS(SELECT 1 FROM sender_resolutions WHERE event_id=NEW.event_id OR challenge_id=NEW.challenge_id)
 THEN RAISE(ABORT,'invalid external recovery approval') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_recovery_member_scope BEFORE INSERT ON sender_recovery_members BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM sender_operations o JOIN sender_recovery_groups g
 ON g.source_operation_id=o.source_operation_id
 WHERE o.operation_id=NEW.operation_id AND o.source_operation_id=NEW.source_operation_id
 AND o.account_id=g.account_id AND o.action='restore' AND o.step IN ('untrash','repair')
 AND o.state!='pending' AND o.state=json_extract(NEW.evidence_json,'$.state')
 AND o.operation_id=json_extract(NEW.evidence_json,'$.operation_id')
 AND o.preimage_json=json_extract(NEW.evidence_json,'$.preimage')
 AND o.postimage_json IS json_extract(NEW.evidence_json,'$.postimage')
 AND EXISTS(SELECT 1 FROM json_each(json_extract(g.plan_json,'$.evidence_json'),'$.operations') e
 WHERE e.value=NEW.evidence_json))
 THEN RAISE(ABORT,'invalid external recovery membership') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_recovery_approval_replay BEFORE INSERT ON sender_approvals BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM sender_recovery_groups
 WHERE event_id=NEW.event_id OR challenge_id=NEW.challenge_id)
 THEN RAISE(ABORT,'recovery approval already consumed') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_recovery_resolution_replay BEFORE INSERT ON sender_resolutions BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM sender_recovery_groups
 WHERE event_id=NEW.event_id OR challenge_id=NEW.challenge_id)
 THEN RAISE(ABORT,'recovery approval already consumed') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_recovery_source_invalidation BEFORE INSERT ON sender_operations BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM sender_recovery_groups WHERE source_operation_id=NEW.source_operation_id)
 THEN RAISE(ABORT,'restore source externally recovered') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_resolution_scope BEFORE INSERT ON sender_resolutions BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM sender_operations o
 WHERE o.operation_id=NEW.operation_id AND o.account_id=NEW.account_id
 AND o.state='unknown' AND o.action='trash' AND o.step='trash'
 AND o.preimage_json=NEW.observation_json)
 THEN RAISE(ABORT,'external recovery must match original evidence') END;
 SELECT CASE WHEN json_extract(NEW.approval_json,'$.account_id') IS NOT NEW.account_id
 OR json_extract(NEW.approval_json,'$.plan_id') IS NOT ('reconcile-' || NEW.operation_id)
 OR json_extract(NEW.approval_json,'$.digest') IS NOT NEW.plan_digest
 OR json_extract(NEW.approval_json,'$.action') IS NOT 'reconcile_external'
 OR json_extract(NEW.approval_json,'$.event_id') IS NOT NEW.event_id
 OR json_extract(NEW.approval_json,'$.challenge_id') IS NOT NEW.challenge_id
 OR coalesce(length(trim(json_extract(NEW.approval_json,'$.principal'))),0)=0
 OR NOT coalesce((json_type(NEW.approval_json,'$.issued_at') IN ('integer','real')
 AND json_type(NEW.approval_json,'$.expires_at') IN ('integer','real')
 AND json_extract(NEW.approval_json,'$.issued_at')<=NEW.recorded_at
 AND NEW.recorded_at<json_extract(NEW.approval_json,'$.expires_at')
 AND json_extract(NEW.approval_json,'$.expires_at')-json_extract(NEW.approval_json,'$.issued_at')<=900),0)
 OR NOT coalesce((NEW.recorded_at-NEW.observed_at BETWEEN 0 AND 10),0)
 OR EXISTS(SELECT 1 FROM sender_approvals WHERE event_id=NEW.event_id OR challenge_id=NEW.challenge_id)
 THEN RAISE(ABORT,'invalid external recovery approval') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_plan_scope BEFORE INSERT ON sender_plans BEGIN
 SELECT CASE WHEN json_type(NEW.ids_json)!='array'
 OR json_array_length(NEW.ids_json) NOT BETWEEN 1 AND 1000
 OR EXISTS(SELECT 1 FROM json_each(NEW.ids_json) WHERE type!='text' OR length(value)=0)
 OR (SELECT count(DISTINCT value) FROM json_each(NEW.ids_json))!=json_array_length(NEW.ids_json)
 THEN RAISE(ABORT,'invalid sender membership') END;
 SELECT CASE WHEN NEW.action='restore' AND (NOT EXISTS(
 SELECT 1 FROM sender_plans p WHERE p.account_id=NEW.account_id AND p.plan_id=NEW.source_plan_id
 AND p.action='trash' AND p.sender=NEW.sender) OR EXISTS(
 SELECT 1 FROM json_each(NEW.ids_json) m WHERE NOT EXISTS(
 SELECT 1 FROM sender_operations o WHERE o.account_id=NEW.account_id AND o.plan_id=NEW.source_plan_id
 AND o.message_id=m.value AND o.step='trash' AND o.state='confirmed' AND o.dry_run=0)))
 THEN RAISE(ABORT,'restore source must be confirmed trash') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_approval_scope BEFORE INSERT ON sender_approvals BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM sender_plans p WHERE p.account_id=NEW.account_id
 AND p.plan_id=NEW.plan_id AND p.digest=NEW.digest AND p.action=NEW.action)
 THEN RAISE(ABORT,'approval scope mismatch') END;
END;
DROP TRIGGER IF EXISTS sender_operation_scope;
CREATE TRIGGER sender_operation_scope BEFORE INSERT ON sender_operations BEGIN
 SELECT CASE WHEN NEW.step IN ('untrash','repair') AND EXISTS(
 SELECT 1 FROM sender_operations source JOIN sender_operations newer
 ON newer.account_id=source.account_id AND newer.message_id=source.message_id
 WHERE source.operation_id=NEW.source_operation_id AND newer.step='trash' AND newer.rowid>source.rowid)
 THEN RAISE(ABORT,'restore source superseded by later trash intent') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM sender_approval_invalidations WHERE approval_id=NEW.approval_id)
 THEN RAISE(ABORT,'sender approval invalidated') END;
 SELECT CASE WHEN NEW.state!='pending' OR NEW.postimage_json IS NOT NULL OR NOT EXISTS(
 SELECT 1 FROM sender_approvals a JOIN sender_plans p USING(account_id,plan_id)
 WHERE a.approval_id=NEW.approval_id AND a.account_id=NEW.account_id AND a.plan_id=NEW.plan_id
 AND a.digest=p.digest AND a.action=NEW.action AND a.issued_at<=NEW.created_at AND a.expires_at>NEW.created_at
 AND EXISTS(SELECT 1 FROM json_each(p.ids_json) WHERE value=NEW.message_id)
 AND ((p.action='trash' AND NEW.step='trash' AND NEW.source_operation_id IS NULL)
 OR (p.action='restore' AND NEW.step IN ('untrash','repair') AND EXISTS(
 SELECT 1 FROM sender_operations s WHERE s.operation_id=NEW.source_operation_id
 AND s.account_id=p.account_id AND s.plan_id=p.source_plan_id AND s.message_id=NEW.message_id
 AND s.step='trash' AND s.state='confirmed' AND s.dry_run=0))))
 THEN RAISE(ABORT,'intent scope mismatch') END;
 SELECT CASE WHEN json_extract(NEW.preimage_json,'$.id') IS NOT NEW.message_id
 OR json_extract(NEW.preimage_json,'$.sender') IS NOT
 (SELECT sender FROM sender_plans WHERE account_id=NEW.account_id AND plan_id=NEW.plan_id)
 THEN RAISE(ABORT,'intent image mismatch') END;
 SELECT CASE WHEN NEW.step='repair' AND NOT EXISTS(SELECT 1 FROM sender_operations u
 WHERE u.account_id=NEW.account_id AND u.plan_id=NEW.plan_id AND u.approval_id=NEW.approval_id
 AND u.message_id=NEW.message_id AND u.step='untrash' AND u.state='confirmed'
 AND u.source_operation_id=NEW.source_operation_id)
 THEN RAISE(ABORT,'repair requires acknowledged untrash') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM sender_operations o WHERE o.account_id=NEW.account_id
 AND (o.state='pending' OR (o.state='unknown' AND NOT EXISTS(
 SELECT 1 FROM sender_resolved_operations r WHERE r.operation_id=o.operation_id AND r.account_id=o.account_id))))
 THEN RAISE(ABORT,'account outcome unresolved') END;
END;
CREATE TRIGGER IF NOT EXISTS sender_operation_update BEFORE UPDATE ON sender_operations BEGIN
 SELECT CASE WHEN NEW.operation_id IS NOT OLD.operation_id OR NEW.account_id IS NOT OLD.account_id
 OR NEW.plan_id IS NOT OLD.plan_id OR NEW.approval_id IS NOT OLD.approval_id
 OR NEW.message_id IS NOT OLD.message_id OR NEW.action IS NOT OLD.action OR NEW.step IS NOT OLD.step
 OR NEW.source_operation_id IS NOT OLD.source_operation_id OR NEW.dry_run IS NOT OLD.dry_run
 OR NEW.preimage_json IS NOT OLD.preimage_json OR NEW.created_at IS NOT OLD.created_at
 THEN RAISE(ABORT,'intent immutable') END;
 SELECT CASE WHEN NOT ((OLD.state='pending' AND NEW.state IN ('confirmed','unknown','failed','skipped'))
 OR (OLD.state='confirmed' AND NEW.state='unknown'))
 THEN RAISE(ABORT,'outcome cannot be retried or rewritten') END;
 SELECT CASE WHEN NEW.state='confirmed' AND NEW.postimage_json IS NULL
 THEN RAISE(ABORT,'confirmation needs postimage') END;
END;
"""
for _table in (
    "sender_plans",
    "sender_approvals",
    "sender_operations",
    "sender_resolutions",
    "sender_recovery_groups",
    "sender_recovery_members",
    "sender_approval_invalidations",
):
    for _action in ("UPDATE", "DELETE") if _table != "sender_operations" else ("DELETE",):
        _SCHEMA += (
            f"CREATE TRIGGER IF NOT EXISTS {_table}_no_{_action.lower()} "
            f"BEFORE {_action} ON {_table} BEGIN "
            "SELECT RAISE(ABORT,'sender evidence immutable'); END;\n"
        )


class SenderJournal:
    def __init__(self, store: JournalStore, clock=time.time):
        if not isinstance(store, JournalStore):
            raise TypeError("An existing bound JournalStore is required")
        self.store, self.conn, self.clock = store, store.conn, clock
        if not self.conn.execute("SELECT 1 FROM accounts").fetchone():
            raise ValueError("Bind JournalStore before creating SenderJournal")
        if self.conn.in_transaction:
            raise ValueError("Sender journal cannot join an uncommitted transaction")
        try:
            self.conn.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA + "\nCOMMIT;")
        except BaseException:
            self.conn.rollback()
            raise

    @contextmanager
    def _transaction(self):
        if self.conn.in_transaction:
            raise ValueError("Durable sender evidence requires its own transaction")
        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            yield

    def protections(self, account_id):
        return self.store.protections(account_id)

    def _stored(self, plan):
        if type(plan) is not SenderPlan:
            raise ValueError("Expected immutable SenderPlan")
        stored = self.get_plan(plan.account_id, plan.plan_id)
        # Compare canonical stored fields, not a caller-supplied digest alone.
        if asdict(stored) != asdict(plan):
            raise ValueError("Plan differs from stored immutable scope")
        return stored

    def save_plan(self, plan):
        if type(plan) is not SenderPlan:
            raise ValueError("Expected immutable SenderPlan")
        # Reconstruct to enforce the model validation even for tampered frozen instances.
        plan = SenderPlan(**asdict(plan))
        self.store._require_account(plan.account_id)
        with self._transaction():
            existing = self.conn.execute(
                "SELECT 1 FROM sender_plans WHERE account_id=? AND plan_id=?", (plan.account_id, plan.plan_id)
            ).fetchone()
            if existing:
                self._stored(plan)
                return
            if plan.action == "restore":
                for message_id in plan.ids:
                    self.source_operation(plan, message_id)
            self.conn.execute(
                "INSERT INTO sender_plans VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    plan.account_id,
                    plan.plan_id,
                    plan.sender,
                    _json(plan.ids),
                    plan.action,
                    plan.source_plan_id,
                    plan.created_at,
                    plan.policy_version,
                    plan.digest,
                ),
            )
            self.store._event(
                plan.account_id,
                "sender_plan_saved",
                dict(plan_id=plan.plan_id, digest=plan.digest, action=plan.action, count=len(plan.ids)),
            )

    def get_plan(self, account_id, plan_id):
        self.store._require_account(account_id)
        row = self.conn.execute(
            "SELECT * FROM sender_plans WHERE account_id=? AND plan_id=?", (account_id, plan_id)
        ).fetchone()
        if row is None:
            raise KeyError("Sender plan not found")
        result = SenderPlan(
            account_id,
            plan_id,
            row["sender"],
            tuple(json.loads(row["ids_json"])),
            row["action"],
            row["source_plan_id"],
            row["created_at"],
            row["policy_version"],
        )
        if result.digest != row["digest"]:
            raise ValueError("Stored sender plan integrity failure")
        return result

    @staticmethod
    def _check_approval(plan, approval, now):
        if (
            type(approval) is not Approval
            or type(now) not in (int, float)
            or not math.isfinite(now)
            or any(
                not isinstance(v, str) or not v.strip()
                for v in (approval.principal, approval.event_id, approval.challenge_id)
            )
            or type(approval.issued_at) not in (int, float)
            or type(approval.expires_at) not in (int, float)
            or not math.isfinite(approval.issued_at)
            or not math.isfinite(approval.expires_at)
            or not 0 < approval.expires_at - approval.issued_at <= 900
            or not approval.issued_at <= now < approval.expires_at
            or (approval.account_id, approval.plan_id, approval.digest, approval.action)
            != (plan.account_id, plan.plan_id, plan.digest, plan.action)
        ):
            raise ValueError("Invalid, expired, or mismatched sender approval")

    def approve(self, plan, approval):
        with self._transaction():
            stored = self._stored(plan)
            self._check_approval(stored, approval, self.clock())
            if self.conn.execute(
                "SELECT 1 FROM sender_resolutions WHERE event_id=? OR challenge_id=?",
                (approval.event_id, approval.challenge_id),
            ).fetchone():
                raise ValueError("Approval event already used for reconciliation")
            approval_id = uuid4().hex
            self.conn.execute(
                "INSERT INTO sender_approvals VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    approval_id,
                    approval.account_id,
                    approval.plan_id,
                    approval.digest,
                    approval.action,
                    approval.principal,
                    approval.event_id,
                    approval.challenge_id,
                    approval.issued_at,
                    approval.expires_at,
                ),
            )
            self.store._event(
                plan.account_id, "sender_approved", dict(plan_id=plan.plan_id, approval_id=approval_id)
            )
        return approval_id

    def _invalidate_approval(self, account_id, approval_id, state, principal, now):
        self.store._require_account(account_id)
        if not isinstance(principal, str) or not principal.strip() or not math.isfinite(now):
            raise ValueError("Invalid approval invalidation evidence")
        with self._transaction():
            row = self.conn.execute(
                "SELECT expires_at FROM sender_approvals WHERE account_id=? AND approval_id=?",
                (account_id, approval_id),
            ).fetchone()
            if row is None:
                raise KeyError("Sender approval not found in this account")
            if self.conn.execute(
                "SELECT 1 FROM sender_approval_invalidations WHERE approval_id=?", (approval_id,)
            ).fetchone():
                return False
            self.conn.execute(
                "INSERT INTO sender_approval_invalidations VALUES (?,?,?,?,?)",
                (approval_id, account_id, state, principal, now),
            )
            self.store._event(
                account_id, "sender_approval_" + state, dict(approval_id=approval_id, principal=principal)
            )
        return True

    def revoke_approval(self, account_id, approval_id, principal):
        """Append a denial; cannot authorize, extend, or undo any dispatched effect."""
        return self._invalidate_approval(account_id, approval_id, "revoked", principal, self.clock())

    def approval_status(self, account_id):
        self.store._require_account(account_id)
        now = self.clock()
        for row in self.conn.execute(
            "SELECT approval_id FROM sender_approvals a WHERE account_id=? AND expires_at<=? "
            "AND NOT EXISTS(SELECT 1 FROM sender_approval_invalidations i WHERE i.approval_id=a.approval_id)",
            (account_id, now),
        ).fetchall():
            self._invalidate_approval(account_id, row[0], "expired", "system:expiry", now)
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT a.approval_id,a.plan_id,a.action,a.expires_at,coalesce(i.state,'active') state "
                "FROM sender_approvals a LEFT JOIN sender_approval_invalidations i USING(approval_id) "
                "WHERE a.account_id=? ORDER BY a.issued_at",
                (account_id,),
            )
        ]

    def validate_approval(self, plan, approval_id, now):
        stored = self._stored(plan)
        row = self.conn.execute(
            "SELECT * FROM sender_approvals WHERE approval_id=?", (approval_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Sender approval not found")
        invalidation = self.conn.execute(
            "SELECT state FROM sender_approval_invalidations WHERE approval_id=?", (approval_id,)
        ).fetchone()
        if invalidation:
            raise ValueError("Sender approval " + invalidation[0])
        if row["account_id"] == plan.account_id and math.isfinite(now) and now >= row["expires_at"]:
            # Normal preflight/final guards run outside transactions. If an intent
            # transaction is open, deny now; a later status/preflight records expiry.
            if not self.conn.in_transaction:
                self._invalidate_approval(plan.account_id, approval_id, "expired", "system:expiry", now)
            raise ValueError("Sender approval expired")
        values = dict(row)
        values.pop("approval_id")
        approval = Approval(**values)
        self._check_approval(stored, approval, now)
        return approval

    @staticmethod
    def _decode(row):
        values = dict(row)
        for key in ("preimage", "postimage"):
            raw = values.pop(key + "_json")
            values[key] = json.loads(raw) if raw is not None else None
        return values

    def operations(self, account_id, plan_id=None):
        self.store._require_account(account_id)
        sql, args = "SELECT * FROM sender_operations WHERE account_id=?", [account_id]
        if plan_id is not None:
            sql += " AND plan_id=?"
            args.append(plan_id)
        return [self._decode(r) for r in self.conn.execute(sql + " ORDER BY rowid", args)]

    def source_operation(self, plan, message_id):
        self.store._require_account(plan.account_id)
        if plan.action != "restore" or message_id not in plan.ids:
            raise ValueError("Restore source outside scope")
        source = self.get_plan(plan.account_id, plan.source_plan_id)
        if source.action != "trash" or source.sender != plan.sender:
            raise ValueError("Restore source sender/action mismatch")
        row = self.conn.execute(
            "SELECT * FROM sender_operations WHERE account_id=? AND plan_id=? "
            "AND message_id=? AND step='trash' AND state='confirmed' AND dry_run=0",
            (plan.account_id, source.plan_id, message_id),
        ).fetchone()
        if row is None:
            raise ValueError("Restore requires confirmed real trash from the source plan")
        # Journal insertion order, not timestamps (which can tie or move back),
        # determines the current trash cycle. Never reuse an older preimage.
        if self.conn.execute(
            "SELECT 1 FROM sender_operations source JOIN sender_operations newer "
            "ON newer.account_id=source.account_id AND newer.message_id=source.message_id "
            "WHERE source.operation_id=? AND newer.step='trash' AND newer.rowid>source.rowid LIMIT 1",
            (row["operation_id"],),
        ).fetchone():
            raise ValueError("Restore source superseded by later trash intent")
        if self.conn.execute(
            "SELECT 1 FROM sender_recovery_groups WHERE source_operation_id=?",
            (row["operation_id"],),
        ).fetchone():
            raise ValueError("Restore source externally recovered; new provenance is required")
        return self._decode(row)

    def _partial_restores(self, account_id):
        return self.conn.execute(
            """SELECT u.operation_id FROM sender_operations u
            JOIN sender_operations s ON s.operation_id=u.source_operation_id
            WHERE u.account_id=? AND u.step='untrash' AND u.state='confirmed'
            AND json_extract(u.postimage_json,'$.labels')!=json_extract(s.preimage_json,'$.labels')
            AND NOT EXISTS(SELECT 1 FROM sender_resolved_operations resolved
                           WHERE resolved.operation_id=u.operation_id AND resolved.account_id=u.account_id)
            AND NOT EXISTS(SELECT 1 FROM sender_operations r WHERE r.source_operation_id=s.operation_id
                           AND r.step='repair' AND r.state='confirmed')""",
            (account_id,),
        ).fetchall()

    def blocked(self, account_id, *, continuing_untrash=None):
        """Unknown/pending evidence and interrupted label repairs block account effects."""
        self.store._require_account(account_id)
        pending = self.conn.execute(
            "SELECT 1 FROM sender_operations o WHERE account_id=? AND "
            "(state='pending' OR (state='unknown' AND NOT EXISTS(SELECT 1 FROM sender_resolved_operations r "
            "WHERE r.operation_id=o.operation_id AND r.account_id=o.account_id))) LIMIT 1",
            (account_id,),
        ).fetchone()
        legacy = self.conn.execute(
            "SELECT 1 FROM operations WHERE account_id=? AND dry_run=0 "
            "AND state IN ('pending','unknown') LIMIT 1",
            (account_id,),
        ).fetchone()
        return bool(
            pending or legacy or any(r[0] != continuing_untrash for r in self._partial_restores(account_id))
        )

    def resolved_operation_ids(self, account_id):
        self.store._require_account(account_id)
        return {
            r[0]
            for r in self.conn.execute(
                "SELECT operation_id FROM sender_resolved_operations WHERE account_id=?", (account_id,)
            )
        }

    def external_recovery_target(self, account_id, sender, operation_id=None):
        """Build current, journal-validated scope, without classifying/retrying effects.

        Recovery is per original trash operation, not per restore attempt: an
        untrash preimage is already in Trash and a repair preimage is incomplete.
        All restore steps for that source are included in the approval evidence.
        """
        from ..models import ReclaimError

        operations = self.operations(account_id)
        resolved = self.resolved_operation_ids(account_id)
        partial = {r[0] for r in self._partial_restores(account_id)}
        groups = {}
        for op in operations:
            if op["operation_id"] in resolved or not (
                op["state"] == "unknown" or op["operation_id"] in partial
            ):
                continue
            root = op["operation_id"] if op["step"] == "trash" else op["source_operation_id"]
            groups.setdefault(root, []).append(op)
        if operation_id is not None:
            groups = {
                root: members
                for root, members in groups.items()
                if root == operation_id
                or any(
                    o["operation_id"] == operation_id for o in operations if o["source_operation_id"] == root
                )
            }
        if len(groups) != 1:
            raise ReclaimError(
                "Reconciliation requires exactly one unresolved group or an explicit operation ID"
            )
        root, unresolved = next(iter(groups.items()))
        source = next((o for o in operations if o["operation_id"] == root), None)
        if source is None:
            raise ReclaimError("Recovery source is missing or belongs to another account")
        source_plan = self.get_plan(account_id, source["plan_id"])
        if (
            source["action"] != "trash"
            or source["step"] != "trash"
            or source["dry_run"] != 0
            or source_plan.action != "trash"
            or source_plan.sender != sender
            or source["preimage"]["sender"] != sender
            or source["message_id"] not in source_plan.ids
            or source["preimage"]["id"] != source["message_id"]
            or "TRASH" in source["preimage"]["labels"]
        ):
            raise ReclaimError("Recovery source account, sender, or original evidence mismatch")
        if any(
            o["step"] == "trash" and o["message_id"] == source["message_id"]
            for o in operations[operations.index(source) + 1 :]
        ):
            raise ReclaimError("Recovery source superseded by later trash intent")
        members = [o for o in operations if o["source_operation_id"] == root]
        if source["state"] == "unknown":
            if members or unresolved != [source]:
                raise ReclaimError("Unknown source cannot establish restore provenance")
            return {"source": source, "evidence_json": None}
        if source["state"] != "confirmed" or not members:
            raise ReclaimError("Restore recovery requires confirmed original trash")
        for op in members:
            plan = self.get_plan(account_id, op["plan_id"])
            if (
                op["action"] != "restore"
                or op["step"] not in {"untrash", "repair"}
                or op["state"] == "pending"
                or op["dry_run"] != 0
                or op["message_id"] != source["message_id"]
                or plan.source_plan_id != source["plan_id"]
                or plan.sender != sender
                or self.source_operation(plan, op["message_id"]) != source
            ):
                raise ReclaimError("Restore recovery scope changed or is not terminal")
            for snapshot in (op["preimage"], op["postimage"], source["postimage"]):
                if snapshot is not None and (
                    {k: v for k, v in snapshot.items() if k != "labels"}
                    != {k: v for k, v in source["preimage"].items() if k != "labels"}
                ):
                    raise ReclaimError("Restore recovery metadata differs from original trash")
        if len({(o["plan_id"], o["approval_id"]) for o in members}) != 1:
            raise ReclaimError("Restore recovery steps have conflicting provenance")
        return {"source": source, "evidence_json": _json({"source": source, "operations": members})}

    def record_external_recovery(self, plan, approval, observation, observed_at):
        from .reconciliation import ReconciliationPlan

        if type(plan) is not ReconciliationPlan:
            raise ValueError("Expected immutable reconciliation plan")
        plan = ReconciliationPlan(**asdict(plan))
        self.store._require_account(plan.account_id)
        current = _json(image(observation))
        with self._transaction():
            now = self.clock()
            self._check_approval(plan, approval, now)
            if (
                type(observed_at) not in (int, float)
                or not math.isfinite(observed_at)
                or not 0 <= now - observed_at <= 10
                or current != plan.observation_json
            ):
                raise ValueError("Reconciliation observation changed or expired")
            target = self.external_recovery_target(plan.account_id, plan.sender, plan.operation_id)
            if (
                target["evidence_json"] != plan.evidence_json
                or _json(target["source"]["preimage"]) != plan.observation_json
            ):
                raise ValueError("Reconciliation source or group evidence changed")
            if plan.evidence_json is not None:
                self._record_external_group(plan, approval, current, observed_at, now)
                return
            self.conn.execute(
                "INSERT INTO sender_resolutions VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    plan.operation_id,
                    plan.account_id,
                    "externally_restored",
                    plan.digest,
                    current,
                    # Preserve the original plan time, not the later safety-read
                    # timestamp, so the approved digest can be recomputed on reopen.
                    _json({**asdict(approval), "reconciliation_plan": asdict(plan)}),
                    approval.event_id,
                    approval.challenge_id,
                    observed_at,
                    now,
                ),
            )
            self.store._event(
                plan.account_id,
                "sender_external_recovery_acknowledged",
                {
                    "operation_id": plan.operation_id,
                    "digest": plan.digest,
                    "original_outcome": "unknown",
                    "disposition": "externally_restored",
                },
            )

    def _record_external_group(self, plan, approval, current, observed_at, now):
        """Caller owns the transaction: group, members and audit commit together."""
        evidence = json.loads(plan.evidence_json)
        self.conn.execute(
            "INSERT INTO sender_recovery_groups VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                plan.operation_id,
                plan.account_id,
                "externally_restored",
                _json(asdict(plan)),
                plan.digest,
                current,
                _json(asdict(approval)),
                approval.event_id,
                approval.challenge_id,
                observed_at,
                now,
            ),
        )
        self.conn.executemany(
            "INSERT INTO sender_recovery_members VALUES (?,?,?)",
            [(op["operation_id"], plan.operation_id, _json(op)) for op in evidence["operations"]],
        )
        self.store._event(
            plan.account_id,
            "sender_external_recovery_acknowledged",
            {
                "source_operation_id": plan.operation_id,
                "operation_ids": [op["operation_id"] for op in evidence["operations"]],
                "digest": plan.digest,
                "disposition": "externally_restored",
                "original_outcome": "interrupted_restore",
            },
        )

    def begin(self, plan, approval_id, message_id, step, preimage):
        pre = image(preimage)
        with self._transaction():
            now = self.clock()
            self.validate_approval(plan, approval_id, now)
            if (
                message_id not in plan.ids
                or pre["id"] != message_id
                or pre["sender"] != plan.sender
                or (plan.action == "trash" and step != "trash")
                or (plan.action == "restore" and step not in {"untrash", "repair"})
            ):
                raise ValueError("Intent outside approved message/action scope")
            source_id, continuing = None, None
            if plan.action == "restore":
                source_id = self.source_operation(plan, message_id)["operation_id"]
                if step == "repair":
                    row = self.conn.execute(
                        "SELECT operation_id FROM sender_operations WHERE account_id=? "
                        "AND plan_id=? AND approval_id=? AND message_id=? "
                        "AND step='untrash' AND state='confirmed'",
                        (plan.account_id, plan.plan_id, approval_id, message_id),
                    ).fetchone()
                    if row:
                        continuing = row[0]
            if self.blocked(plan.account_id, continuing_untrash=continuing):
                raise ValueError("Account has unresolved effects; no dispatch permitted")
            operation_id = uuid4().hex
            self.conn.execute(
                "INSERT INTO sender_operations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    operation_id,
                    plan.account_id,
                    plan.plan_id,
                    approval_id,
                    message_id,
                    plan.action,
                    step,
                    source_id,
                    0,
                    "pending",
                    _json(pre),
                    None,
                    None,
                    now,
                    now,
                ),
            )
            self.store._event(
                plan.account_id,
                "sender_intent",
                dict(
                    operation_id=operation_id,
                    plan_id=plan.plan_id,
                    message_id=message_id,
                    step=step,
                    source_operation_id=source_id,
                ),
            )
        return operation_id

    def finish(self, operation_id, state, postimage=None, reason=None):
        if state not in {"confirmed", "unknown", "failed", "skipped"}:
            raise ValueError("Invalid terminal sender state")
        if reason is not None and (
            not isinstance(reason, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", reason)
        ):
            raise ValueError("Use a safe classification, never raw remote exception text")
        post = image(postimage) if postimage is not None else None
        with self._transaction():
            row = self.conn.execute(
                "SELECT * FROM sender_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if row is None:
                raise KeyError("Sender operation not found")
            self.store._require_account(row["account_id"])
            pre = json.loads(row["preimage_json"])
            if post is not None and any(post[k] != pre[k] for k in ("id", "thread_id", "sender")):
                raise ValueError("Postimage identity changed")
            if state == "confirmed":
                if post is None or (row["step"] == "trash") != ("TRASH" in post["labels"]):
                    raise ValueError("Invalid confirmation postimage")
                if row["step"] == "repair":
                    source = self.conn.execute(
                        "SELECT preimage_json FROM sender_operations WHERE operation_id=?",
                        (row["source_operation_id"],),
                    ).fetchone()
                    if post["labels"] != json.loads(source[0])["labels"]:
                        raise ValueError("Repair must exactly recover source labels")
            self.conn.execute(
                "UPDATE sender_operations SET state=?,postimage_json=?,reason=?,updated_at=? "
                "WHERE operation_id=?",
                (
                    state,
                    _json(post) if post is not None else row["postimage_json"],
                    reason,
                    self.clock(),
                    operation_id,
                ),
            )
            self.store._event(
                row["account_id"],
                "sender_outcome",
                dict(operation_id=operation_id, state=state, reason=reason),
            )

    def recover(self, account_id):
        """Classify interrupted attempts; no network reads and absolutely no retry."""
        self.store._require_account(account_id)
        with self._transaction():
            rows = self.conn.execute(
                "SELECT operation_id FROM sender_operations WHERE account_id=? AND state='pending'",
                (account_id,),
            ).fetchall()
            ids = {r[0] for r in rows} | {r[0] for r in self._partial_restores(account_id)}
            for operation_id in sorted(ids):
                self.conn.execute(
                    "UPDATE sender_operations SET state='unknown',reason='recovery_interrupted',"
                    "updated_at=? WHERE operation_id=?",
                    (self.clock(), operation_id),
                )
                self.store._event(account_id, "sender_recovered_unknown", dict(operation_id=operation_id))
        return len(ids)
