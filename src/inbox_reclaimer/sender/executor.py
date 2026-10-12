"""Bounded, one-message-at-a-time offline trash/restore executor.

No permanent-delete operation, automatic retry, OAuth or live release bypass.
Production orchestration must keep the OS account lock for the whole workflow
and enforce require_live_release() before constructing a live write adapter.
The adapter must reserve write quota in prepare_write() before safety reads;
write methods must not retry or perform further quota sleeps internally.
"""

from __future__ import annotations

from dataclasses import replace
import math
import time

from ..analytics import parse_sender
from ..models import GateClosed, IdentityMismatch
from ..proposals import _valid_message, check_protection
from .journal import image


class _Skip(Exception):
    """A local classification, not remotely supplied exception content."""


_WRITABLE_SYSTEM = frozenset({"INBOX", "UNREAD"})


def _supported(labels):
    return all(label in _WRITABLE_SYSTEM or label.startswith("Label_") for label in labels)


class SenderExecutor:
    def __init__(self, adapter, sender_journal, clock=time.time):
        self.adapter, self.journal, self.clock = adapter, sender_journal, clock

    def _identity(self, plan):
        if self.adapter.resolve_identity().account_id != plan.account_id:
            raise IdentityMismatch("Sender workflow account changed")

    def _capability(self, plan):
        self._identity(plan)
        validator = getattr(self.adapter, "validate_capability", None)
        if validator is None:
            validator = getattr(self.adapter, "capability", None)
        if validator is None or validator(plan.action) is False:
            raise GateClosed("Adapter has not validated the requested write capability")
        self._identity(plan)

    def _prepare(self, plan, approval_id, dry_run):
        self._identity(plan)
        self.journal.validate_approval(plan, approval_id, self.clock())
        if not dry_run:
            self._capability(plan)
            prepare = getattr(self.adapter, "prepare_write", None)
            if prepare is not None:
                self._identity(plan)
                prepare(plan.action)
                self._identity(plan)
            self.journal.validate_approval(plan, approval_id, self.clock())

    def _metadata(self, plan, message_id):
        self._identity(plan)
        message = self.adapter.get_metadata(message_id)
        self._identity(plan)
        if not _valid_message(message) or message.id != message_id:
            raise _Skip("invalid_message_read")
        if parse_sender(message.raw_from) != plan.sender:
            raise _Skip("sender_changed")
        return message

    def _protections(self, plan):
        self._identity(plan)
        result = self.journal.protections(plan.account_id)
        self._identity(plan)
        return result

    def _fresh(self, stamp):
        age = self.clock() - stamp
        if not math.isfinite(age) or not 0 <= age <= 10:
            raise _Skip("stale_safety_read")

    def _safe_read(self, plan, message_id, *, allow_trash=False):
        # Age includes read latency, not just time since responses arrived.
        stamp = self.clock()
        message = self._metadata(plan, message_id)
        self._identity(plan)
        thread = list(self.adapter.get_thread(message.thread_id))
        self._identity(plan)
        protections = self._protections(plan)
        # Restore is the only context in which the target's own TRASH is exempt.
        checked = replace(message, labels=message.labels - {"TRASH"}) if allow_trash else message
        reason = check_protection(checked, thread, protections)
        if reason:
            raise _Skip(reason)
        current = next(m for m in thread if m.id == message_id)
        checked_current = replace(current, labels=current.labels - {"TRASH"}) if allow_trash else current
        reason = check_protection(checked_current, thread, protections)
        if reason:
            raise _Skip(reason)
        if parse_sender(current.raw_from) != plan.sender:
            raise _Skip("sender_changed")
        if image(current) != image(message):
            raise _Skip("message_changed_during_reads")
        self._fresh(stamp)
        return current, stamp

    def _guard(self, plan, approval_id, stamp):
        self._capability(plan)
        self.journal.validate_approval(plan, approval_id, self.clock())
        if plan.sender in self._protections(plan):
            raise _Skip("protected_sender")
        # Last identity validation happens after all potentially blocking checks.
        self._identity(plan)
        self._fresh(stamp)

    def _final_local_check(self, plan, approval_id, stamp):
        # The transport invokes this after its last potentially blocking identity
        # check and immediately before sending. This callback performs no network I/O.
        self.journal.validate_approval(plan, approval_id, self.clock())
        if plan.sender in self.journal.protections(plan.account_id):
            raise _Skip("protected_sender")
        self._fresh(stamp)

    def _effect(self, plan, approval_id, message, stamp, step, call, confirms):
        # Never catch/ignore this failure: COMMIT and audit must succeed before dispatch.
        operation_id = self.journal.begin(plan, approval_id, message.id, step, message)
        try:
            self._guard(plan, approval_id, stamp)
        except Exception as exc:
            reason = str(exc) if isinstance(exc, _Skip) else "pre_dispatch_rejected"
            self.journal.finish(operation_id, "skipped", reason=reason)
            return "skipped", None, operation_id
        try:
            install_guard = getattr(self.adapter, "set_dispatch_guard", None)
            if install_guard is not None:
                install_guard(lambda: self._final_local_check(plan, approval_id, stamp))
            else:
                self._final_local_check(plan, approval_id, stamp)
            response = call()
            self._identity(plan)
            # A successful adapter return is the acknowledgement. Explicit failures
            # are not acknowledgements, even if the following read might look right.
            if response is False or (isinstance(response, dict) and "error" in response):
                raise ValueError("Unacknowledged write")
            post = self._metadata(plan, message.id)
            if post.thread_id != message.thread_id or not confirms(post):
                raise ValueError("Unexpected postimage")
            self.journal.finish(operation_id, "confirmed", postimage=post)
            return "confirmed", post, operation_id
        except Exception:
            # Includes response timeout, identity changes, ack followed by failed read,
            # and contradictory labels. No network retry or speculative attribution.
            self.journal.finish(operation_id, "unknown", reason="effect_not_confirmed")
            return "unknown", None, operation_id

    @staticmethod
    def _summary(plan, dry_run):
        return dict(
            account_id=plan.account_id,
            plan_id=plan.plan_id,
            action=plan.action,
            dry_run=dry_run,
            confirmed=0,
            skipped=0,
            unknown=0,
            would_change=0,
            blocked=False,
            results=[],
        )

    def execute(self, plan, approval_id, dry_run=True):
        """Trash only. Summary counts refer to messages, not individual write steps."""
        return self._run(plan, approval_id, dry_run, "trash")

    def restore(self, plan, approval_id, dry_run=True):
        """Restore only confirmed source trash, preserving labels or stopping unknown."""
        return self._run(plan, approval_id, dry_run, "restore")

    def _run(self, plan, approval_id, dry_run, action):
        if type(dry_run) is not bool or plan.action != action:
            raise ValueError("Invalid sender action or dry-run flag")
        self._identity(plan)
        self.journal.validate_approval(plan, approval_id, self.clock())
        result = self._summary(plan, dry_run)
        if self.journal.blocked(plan.account_id):
            result["blocked"] = True
            return result
        for message_id in plan.ids:
            if self.journal.blocked(plan.account_id):
                result["blocked"] = True
                break
            attempted = any(
                o["message_id"] == message_id for o in self.journal.operations(plan.account_id, plan.plan_id)
            )
            if attempted:
                state, reason = "skipped", "already_attempted"
            else:
                try:
                    state, reason = self._one(plan, approval_id, message_id, dry_run)
                except _Skip as exc:
                    state, reason = "skipped", str(exc)
            result[state] += 1
            result["results"].append(dict(message_id=message_id, state=state, reason=reason))
            if state == "unknown":
                result["blocked"] = True
                break
        return result

    def _one(self, plan, approval_id, message_id, dry_run):
        source = None
        if plan.action == "restore":
            source = self.journal.source_operation(plan, message_id)
            if any(
                o["source_operation_id"] == source["operation_id"]
                for o in self.journal.operations(plan.account_id)
            ):
                raise _Skip("source_already_attempted")
        self._prepare(plan, approval_id, dry_run)
        try:
            message, stamp = self._safe_read(plan, message_id, allow_trash=source is not None)
        except (IdentityMismatch, GateClosed, _Skip):
            raise
        except Exception:
            raise _Skip("safety_read_failed") from None
        if source is not None:
            if (
                message.thread_id != source["postimage"]["thread_id"]
                or sorted(message.labels) != source["postimage"]["labels"]
            ):
                raise _Skip("external_label_conflict")
            if not _supported(set(source["preimage"]["labels"]) - message.labels):
                raise _Skip("unsupported_label_repair")
        if dry_run:
            self.journal.validate_approval(plan, approval_id, self.clock())
            self._fresh(stamp)
            return "would_change", None
        if source is None:

            def confirms(post):
                return (
                    "TRASH" in post.labels
                    and not (post.labels - message.labels - {"TRASH"})
                    and _supported(message.labels - post.labels)
                )

            state, _, _ = self._effect(
                plan,
                approval_id,
                message,
                stamp,
                "trash",
                lambda: self.adapter.trash_ids([message_id]),
                confirms,
            )
            return state, None
        return self._restore_one(plan, approval_id, message, stamp, source)

    def _restore_one(self, plan, approval_id, message, stamp, source):
        target = frozenset(source["preimage"]["labels"])
        expected = message.labels - {"TRASH"}
        # Gmail may restore INBOX itself; this is the only permitted added label.
        state, post, untrash_id = self._effect(
            plan,
            approval_id,
            message,
            stamp,
            "untrash",
            lambda: self.adapter.untrash_message(message.id),
            lambda m: m.labels in (expected, expected | {"INBOX"}),
        )
        if state != "confirmed":
            return state, None
        if post.labels == target:
            return "confirmed", None
        try:
            self._prepare(plan, approval_id, False)
            current, stamp = self._safe_read(plan, message.id)
            if current.thread_id != post.thread_id or current.labels != post.labels:
                raise _Skip("external_label_conflict")
            add = target - current.labels
            remove = current.labels - target
            if not _supported(add) or not remove <= {"INBOX"}:
                raise _Skip("unsupported_label_repair")
            state, _, _ = self._effect(
                plan,
                approval_id,
                current,
                stamp,
                "repair",
                lambda: self.adapter.modify_message(message.id, sorted(add), sorted(remove)),
                lambda m: m.labels == target,
            )
            if state == "confirmed":
                return "confirmed", None
            if state == "unknown":
                return "unknown", "partial_restore"
        except Exception:
            # A confirmed untrash followed by a failed preflight/intent is still an
            # incomplete restore. Downgrade conservatively; never start over.
            pass
        self.journal.finish(untrash_id, "unknown", reason="partial_restore")
        return "unknown", "partial_restore"
