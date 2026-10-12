"""Operator-only, five-message disposable-account validation; not a release switch."""

import argparse
from contextlib import contextmanager, ExitStack
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from .. import authorization as readonly_auth
from ..models import ReclaimError
from ..profile import account_lock, resolve_profile
from . import authorization as modify_auth
from .confirmation import confirm_plan
from .executor import SenderExecutor
from .gmail import GoogleSenderReader, GoogleSenderWriter
from .journal import SenderJournal
from .models import SenderPlan, exact_sender, release_status
from .selection import select_sender
from .validation_scope import DisposableValidation, validation_home
from .workflow import run_sender_workflow


def _release_fields():
    return {
        "production_released": release_status()["live_mutation_released"],
        "execution_scope": "disposable_validation",
        "validation_candidate_cap": 5,
    }


def _interactive():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ReclaimError("Run validation yourself in a local terminal; no agent/stdin approval is accepted")


@contextmanager
def _paths(helper, scope):
    # Still use the installed helper, but never borrow the current profile/token.
    home = validation_home()
    scope.check_home(home)
    previous = os.environ.get("HERMES_HOME")
    try:
        os.environ["HERMES_HOME"] = str(home)
        paths = resolve_profile(helper)
        scope.check_home(paths.home)
        yield paths
    finally:
        if previous is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = previous


@contextmanager
def _session(paths, scope):
    from ..budget import PersistentBudgetLimiter
    from ..gmail import GoogleReadAdapter
    from ..quota import QuotaConfig, QuotaLimiter
    from ..storage import JournalStore

    scope.check_home(paths.home)
    paths.initialize()
    with ExitStack() as stack:
        store = stack.enter_context(JournalStore(paths.journal))
        quota = stack.enter_context(PersistentBudgetLimiter(QuotaLimiter(QuotaConfig()), paths.journal))
        base = GoogleReadAdapter(paths.home, quota=quota)
        identity = base.resolve_identity()
        scope.check_account(identity)  # Before any message enumeration or metadata read.
        stack.enter_context(account_lock(paths, identity.account_id))
        store.bind_account(identity)
        quota.bind_account(identity.account_id)
        journal = SenderJournal(store)
        journal.recover(identity.account_id)
        yield base, identity, store, journal


def run_action(paths, scope, action, *, limit=5, source_plan=None, resume_plan=None, operation_id=None):
    if (
        action not in {"preview", "trash", "restore", "status", "reconcile", "resume"}
        or type(limit) is not int
        or not 1 <= limit <= 5
    ):
        raise ReclaimError(
            "Validation accepts preview/trash/restore/status/reconcile/resume and one to five candidates"
        )
    with _session(paths, scope) as (base, identity, store, journal):
        reader = GoogleSenderReader(base)
        if action == "status":
            from collections import Counter

            return {
                "outcomes": dict(Counter(o["state"] for o in journal.operations(identity.account_id))),
                "blocked": journal.blocked(identity.account_id),
                "externally_reconciled": len(journal.resolved_operation_ids(identity.account_id)),
                **_release_fields(),
            }
        if action == "reconcile":
            from .reconciliation import reconcile_external

            return reconcile_external(
                journal, reader, identity, scope.sender, guard=scope.check, operation_id=operation_id
            )
        if action != "preview" and journal.blocked(identity.account_id):
            raise ReclaimError(
                "Unresolved operation evidence blocks effects; inspect the local journal, do not retry"
            )
        if action == "resume":
            plan = journal.get_plan(identity.account_id, resume_plan)
            if plan.sender != scope.sender or len(plan.ids) > 5:
                raise ReclaimError("Resume plan differs from the bounded validation sender/account")
            messages = None
        elif action == "restore":
            try:
                source = journal.get_plan(identity.account_id, source_plan)
            except KeyError:
                raise ReclaimError(
                    "The source trash plan was not found in this account's local journal. "
                    "Restore requires the plan_id from a confirmed Trash operation in the "
                    "same disposable-account profile; a Gmail message ID is not a plan_id. "
                    "Messages manually trashed in Gmail must be restored in Gmail."
                ) from None
            if source.action != "trash" or source.sender != scope.sender or len(source.ids) > 5:
                raise ReclaimError("Restore source differs from the bounded validation sender/account")
            ids = tuple(
                sorted(
                    o["message_id"]
                    for o in journal.operations(identity.account_id, source_plan)
                    if o["step"] == "trash" and o["state"] == "confirmed"
                )
            )
            if not ids:
                raise ReclaimError("No confirmed source trash operations are available")
            plan = SenderPlan(identity.account_id, uuid4().hex, scope.sender, ids, "restore", source.plan_id)
            messages = tuple(reader.get_metadata(i) for i in ids)
        else:
            selection = select_sender(reader, store, identity, scope.sender, limit, redact_subjects=True)
            plan, messages = selection.plan, selection.messages
            if action == "preview" or plan is None:
                from .render import summary

                result = summary(selection, minimized=False)
                result.update(live_validation=True, **_release_fields())
                return result
        bound = replace(scope, account_id=identity.account_id, ids=plan.ids)
        bound.check_home(paths.home)
        if action != "resume":
            journal.save_plan(plan)
        waiting = run_sender_workflow(paths, identity, journal, None, plan)
        if waiting.get("status") != "awaiting_approval":
            return {
                "live_validation": True,
                **_release_fields(),
                "plan_id": plan.plan_id,
                "result": waiting,
            }
        if messages is None:
            messages = tuple(reader.get_metadata(i) for i in plan.ids)
        # CLI action and account setup are not mutation approval. Cancel is default.
        decision = confirm_plan(plan, identity, messages, validation=True)
        if decision is None:
            with store.conn:
                store._event(identity.account_id, "sender_confirmation_rejected", {"plan_id": plan.plan_id})
            run_sender_workflow(paths, identity, journal, None, plan, decision="reject")
            return {"decision": "rejected", "mail_changed": False, **_release_fields()}
        bound.check()
        approval_id = journal.approve(plan, decision)
        writer = GoogleSenderWriter(base, validation=bound)
        result = run_sender_workflow(
            paths, identity, journal, SenderExecutor(writer, journal), plan, approval_id
        )
        return {
            "live_validation": True,
            **_release_fields(),
            "plan_id": plan.plan_id,
            "action": plan.action,
            "approved_count": len(plan.ids),
            "result": result,
        }


def _sign_in(paths, scope, manual_browser):
    def verify(directory, client_id):
        identity = readonly_auth.verify_staged(directory, client_id)
        scope.check_account(identity)
        return identity

    return readonly_auth.authorize(
        paths,
        verify=verify,
        consent=lambda config: readonly_auth.browser_consent(config, manual_browser=manual_browser),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Local disposable-account validation only. Maximum five candidates; each mutation needs native "
            "confirmation. This path remains limited to five candidates regardless of production release."
        )
    )
    parser.add_argument(
        "action",
        choices=(
            "check",
            "sign-in",
            "authorize-modify",
            "preview",
            "trash",
            "restore",
            "status",
            "reconcile",
            "resume",
        ),
    )
    parser.add_argument("--workspace-scripts", type=Path, required=True)
    parser.add_argument(
        "--account", required=True, help="Exact disposable Gmail account; checked before message reads"
    )
    parser.add_argument("--sender", required=True, help="Exact sender of disposable test messages")
    parser.add_argument("--max-messages", type=int, default=5, choices=range(1, 6))
    parser.add_argument("--source-plan", help="Local confirmed trash plan; required for restore")
    parser.add_argument("--plan", help="Immutable sender plan to resume with fresh native approval")
    parser.add_argument("--operation", help="Unresolved operation to externally reconcile")
    parser.add_argument("--manual-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action != "check":
            _interactive()  # Before profile/credentials/network access.
        if (args.action == "restore") != bool(args.source_plan):
            raise ReclaimError("Supply --source-plan only for restore; it is required there")
        if (args.action == "resume") != bool(args.plan):
            raise ReclaimError("Supply --plan only for resume; it is required there")
        if args.operation and args.action != "reconcile":
            raise ReclaimError("Supply --operation only for reconcile")
        scope = DisposableValidation(exact_sender(args.account), exact_sender(args.sender))
        with _paths(args.workspace_scripts, scope) as paths:
            print("DISPOSABLE-ACCOUNT VALIDATION — not a production release")
            print("Separate credential home: " + str(paths.home))
            if args.action == "check":
                modify_auth.load_client(paths)  # Local format check, no grant/credential read.
                result = {
                    "client_valid": True,
                    "token_present": (paths.home / "google_token.json").is_file(),
                    "network_used": False,
                    **_release_fields(),
                }
            elif args.action == "sign-in":
                _sign_in(paths, scope, args.manual_browser)
                result = {"readonly_authorized": True, "mail_changed": False}
            elif args.action == "authorize-modify":
                modify_auth.authorize_modify(
                    paths,
                    validation=scope,
                    consent=lambda config: modify_auth.browser_consent(
                        config, manual_browser=args.manual_browser, validation=scope
                    ),
                )
                result = {"modify_authorized": True, "mail_changed": False, **_release_fields()}
            else:
                result = run_action(
                    paths,
                    scope,
                    args.action,
                    limit=args.max_messages,
                    source_plan=args.source_plan,
                    resume_plan=args.plan,
                    operation_id=args.operation,
                )
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0
    except (KeyboardInterrupt, EOFError):
        print(
            "Stopped locally. If execution had begun, inspect status before further action; do not blindly retry.",
            file=sys.stderr,
        )
        return 2
    except ReclaimError as exc:
        from ..render import terminal_safe

        print(terminal_safe(str(exc)), file=sys.stderr)
        print(
            "If execution began, inspect status before further action; do not blindly retry.", file=sys.stderr
        )
        return 2
    except Exception:
        # Storage/network errors may occur after a committed effect. Never assert no mail changed.
        print(
            "Validation did not complete. Check the dedicated account/client setup and local journal status. "
            "If execution had begun, outcomes may be uncertain: do not blindly retry. "
            "Do not share tokens, sign-in URLs or mailbox contents.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
