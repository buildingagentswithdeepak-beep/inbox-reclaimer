"""Sender CLI composition. Preview by default; no machine-supplied approval surface."""

from pathlib import Path
import sys
from typing import Optional
from uuid import uuid4

import typer

from ..models import ReclaimError
from .models import SenderPlan, exact_sender, release_status, require_live_release


def _execution_preflight(options, execute):
    if not execute:
        return
    if options.hermes:
        raise ReclaimError(
            "Sender actions require a separately launched local confirmation window, not --hermes."
        )
    if not options.demo:
        require_live_release()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ReclaimError("Run confirmation in an interactive local terminal. No approval was created.")


def _require_local_revocation(options):
    if options.hermes or not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ReclaimError("Run revocation from an interactive local terminal.")


def _require_local_control(options):
    if options.hermes or not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ReclaimError("Run recovery or rejection from an interactive local terminal.")


def _reader(adapter, demo):
    if demo:
        from .demo import DemoSenderAdapter

        return DemoSenderAdapter(adapter)
    from .gmail import GoogleSenderReader

    return GoogleSenderReader(adapter)


def _perform(paths, options, base, reader, identity, journal, plan, messages=None):
    from .confirmation import confirm_plan
    from .executor import SenderExecutor
    from .workflow import run_sender_workflow

    waiting = run_sender_workflow(paths, identity, journal, None, plan)
    if waiting.get("status") != "awaiting_approval":
        return waiting
    if journal.blocked(identity.account_id):
        raise ReclaimError(
            "Unresolved effects block execution. Inspect sender-status and reconcile; do not retry."
        )
    if messages is None:
        messages = tuple(reader.get_metadata(id) for id in plan.ids)
    decision = confirm_plan(plan, identity, messages, synthetic=options.demo)
    if decision is None:
        with journal.store.conn:
            journal.store._event(
                identity.account_id, "sender_confirmation_rejected", {"plan_id": plan.plan_id}
            )
        result = run_sender_workflow(paths, identity, journal, None, plan, decision="reject")
        return result | {"decision": "rejected", "mail_changed": False}
    approval_id = journal.approve(plan, decision)
    if options.demo:
        writer = reader
    else:
        from .gmail import GoogleSenderWriter

        writer = GoogleSenderWriter(base)
    executor = SenderExecutor(writer, journal)
    return run_sender_workflow(paths, identity, journal, executor, plan, approval_id)


def register(app):
    from ..cli import local_errors, output, session
    from ..profile import private_write

    @app.command("sender-cleanup")
    @local_errors
    def sender_cleanup(
        ctx: typer.Context,
        sender: str = typer.Option(
            ..., help="One exact sender email address; not a domain or search expression."
        ),
        max_messages: int = typer.Option(
            1000, min=1, max=1000, help="Maximum sender-query candidates inspected."
        ),
        html: Optional[Path] = None,
        execute: bool = typer.Option(
            False, help="Request separate native confirmation for live Trash; never automatic consent."
        ),
        redact_subjects: bool = typer.Option(
            True, help="Keep subjects out of this local preview by default."
        ),
    ):
        """Preview bounded sender cleanup. Live effects remain gated; no permanent deletion."""
        try:
            sender = exact_sender(sender)
        except ValueError as exc:
            raise ReclaimError(str(exc)) from None
        options = ctx.obj
        _execution_preflight(options, execute)
        if html and options.hermes:
            raise ReclaimError("HTML previews must be generated locally, not through --hermes.")
        from .selection import select_sender
        from .journal import SenderJournal
        from .render import preview_html, summary

        with session(options) as (paths, base, identity, _, journal):
            if html:
                paths.validate_export(html)
            reader = _reader(base, options.demo)
            selection = select_sender(
                reader,
                journal,
                identity,
                sender,
                max_messages,
                redact_subjects
                or options.hermes
                or options.config.get("privacy", {}).get("redact_subjects", False),
            )
            store = SenderJournal(journal)
            store.recover(identity.account_id)
            if selection.plan:
                store.save_plan(selection.plan)
            if html:
                private_write(html, preview_html(selection, identity, synthetic=options.demo))
            if not execute or selection.plan is None:
                result = summary(selection, minimized=options.hermes)
                result["fixture"] = "synthetic" if options.demo else None
                output(result)
                return
            result = _perform(
                paths, options, base, reader, identity, store, selection.plan, selection.messages
            )
            output({"fixture": "synthetic" if options.demo else None, "result": result})

    @app.command("sender-restore")
    @local_errors
    def sender_restore(
        ctx: typer.Context,
        source_plan: str = typer.Option(..., help="Source sender-trash plan with confirmed real operations."),
        execute: bool = typer.Option(
            False, help="Request separate restore confirmation; live Gate B is not released."
        ),
    ):
        """Preview restoration of a sender plan's confirmed tool-trash operations."""
        options = ctx.obj
        _execution_preflight(options, execute)
        from .journal import SenderJournal

        with session(options) as (paths, base, identity, _, journal):
            store = SenderJournal(journal)
            store.recover(identity.account_id)
            source = store.get_plan(identity.account_id, source_plan)
            if source.action != "trash":
                raise ReclaimError("Restore requires a source trash plan, not another restore.")
            rows = store.operations(identity.account_id, source_plan)
            ids = tuple(
                sorted(
                    {
                        row["message_id"]
                        for row in rows
                        if row["state"] == "confirmed" and row["step"] == "trash"
                    }
                )
            )
            if not ids:
                raise ReclaimError("No confirmed tool-trash operations are available for this plan.")
            plan = SenderPlan(identity.account_id, uuid4().hex, source.sender, ids, "restore", source.plan_id)
            reader = _reader(base, options.demo)
            messages = tuple(reader.get_metadata(id) for id in ids)
            store.save_plan(plan)
            if not execute:
                output(
                    {
                        "plan_id": plan.plan_id,
                        "source_plan": source_plan,
                        "action": "restore",
                        "candidate_count": len(ids),
                        "approval_created": False,
                        "mail_changed": False,
                        **release_status(),
                    }
                )
                return
            output(_perform(paths, options, base, reader, identity, store, plan, messages))

    @app.command("sender-resume")
    @local_errors
    def sender_resume(
        ctx: typer.Context,
        plan: str = typer.Option(
            ..., help="Existing immutable sender plan ID; never re-enumerates messages."
        ),
        execute: bool = typer.Option(
            False, help="Request fresh native approval; production gate still applies."
        ),
        reject: bool = typer.Option(False, help="Locally reject the waiting plan without any mail changes."),
    ):
        """Inspect a saved plan or resume it with fresh native approval; never replay attempts."""
        if execute and reject:
            raise ReclaimError("Cannot combine --execute and --reject.")
        options = ctx.obj
        _execution_preflight(options, execute)
        if reject:
            _require_local_control(options)
        from .journal import SenderJournal
        from .workflow import run_sender_workflow

        with session(options) as (paths, base, identity, _, journal):
            store = SenderJournal(journal)
            store.recover(identity.account_id)
            saved = store.get_plan(identity.account_id, plan)
            if not execute:
                state = run_sender_workflow(
                    paths, identity, store, None, saved, decision="reject" if reject else "list"
                )
                attempted = {o["message_id"] for o in store.operations(identity.account_id, plan)}
                output(
                    state
                    | {
                        "mail_changed": False,
                        "approval_created": False,
                        "candidate_count": len(saved.ids),
                        "attempted_count": len(attempted),
                        "remaining_count": len(set(saved.ids) - attempted),
                        "blocked": store.blocked(identity.account_id),
                    }
                )
                return
            reader = _reader(base, options.demo)
            output(
                {
                    "fixture": "synthetic" if options.demo else None,
                    "result": _perform(paths, options, base, reader, identity, store, saved),
                }
            )

    @app.command("sender-reconcile")
    @local_errors
    def sender_reconcile(
        ctx: typer.Context,
        sender: str = typer.Option(..., help="Exact sender whose externally recovered message is verified."),
        operation: Optional[str] = typer.Option(
            None, help="Explicit unresolved operation reference from sender-status."
        ),
    ):
        """Verify external recovery and append native acknowledgement. Makes no Gmail writes."""
        sender = exact_sender(sender)
        _require_local_control(ctx.obj)
        from .confirmation import confirm_plan
        from .journal import SenderJournal
        from .reconciliation import reconcile_external

        with session(ctx.obj) as (_, base, identity, _, journal):
            store = SenderJournal(journal)
            store.recover(identity.account_id)
            reader = _reader(base, ctx.obj.demo)

            def confirm(plan, account, messages, **_):
                return confirm_plan(plan, account, messages, synthetic=ctx.obj.demo)

            output(
                reconcile_external(
                    store, reader, identity, sender, confirm=confirm, operation_id=operation, validation=False
                )
            )

    @app.command("sender-approvals")
    @local_errors
    def sender_approvals(ctx: typer.Context):
        """List approval references and durably record expiry; no Gmail writes."""
        from .journal import SenderJournal

        with session(ctx.obj) as (_, _, identity, _, journal):
            output(
                {
                    "approvals": SenderJournal(journal).approval_status(identity.account_id),
                    "mail_changed": False,
                }
            )

    @app.command("sender-revoke")
    @local_errors
    def sender_revoke(ctx: typer.Context, approval: str = typer.Option(..., help="Approval ID to revoke.")):
        """Revoke future dispatch permission; does not undo effects already sent."""
        import getpass
        from .journal import SenderJournal

        _require_local_revocation(ctx.obj)
        with session(ctx.obj) as (_, _, identity, _, journal):
            changed = SenderJournal(journal).revoke_approval(identity.account_id, approval, getpass.getuser())
            output(
                {"approval_id": approval, "invalidated": True, "new_record": changed, "mail_changed": False}
            )

    @app.command("sender-status")
    @local_errors
    def sender_status(ctx: typer.Context, plan: Optional[str] = None):
        """Read sender-operation outcomes without retrying or reconciling remote writes."""
        from collections import Counter
        from .journal import SenderJournal

        with session(ctx.obj) as (_, _, identity, _, journal):
            store = SenderJournal(journal)
            store.recover(identity.account_id)
            rows = store.operations(identity.account_id, plan)
            resolved = store.resolved_operation_ids(identity.account_id)
            partial = {row[0] for row in store._partial_restores(identity.account_id)}
            output(
                {
                    "plan_id": plan,
                    "outcomes": dict(Counter(row["state"] for row in rows)),
                    **release_status(),
                    "mail_changed": False,
                    "blocked": store.blocked(identity.account_id),
                    "externally_reconciled": len(resolved),
                    "recovery_references": [
                        {key: row[key] for key in ("operation_id", "plan_id", "step", "state")}
                        for row in rows
                        if (row["state"] == "unknown" and row["operation_id"] not in resolved)
                        or row["operation_id"] in partial
                    ],
                }
            )
