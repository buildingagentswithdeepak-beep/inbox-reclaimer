"""CLI composition: local display, immutable proposals and unconditionally closed write gates."""

from __future__ import annotations

import json
import re
import sqlite3
import tomllib
from collections import Counter
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer
from rich.console import Console

from .models import ReclaimError, Rule
from .profile import account_lock, gate_check, private_write, resolve_profile
from .sender.commands import register as register_sender_commands

app = typer.Typer(
    no_args_is_help=True, help="Inbox Reclaimer · Gate A: local analysis and proposals. No Gmail writes."
)
protections_app = typer.Typer(no_args_is_help=True)
audit_app = typer.Typer(no_args_is_help=True)
cache_app = typer.Typer(no_args_is_help=True)
app.add_typer(protections_app, name="protections")
app.add_typer(audit_app, name="audit")
app.add_typer(cache_app, name="cache")
console = Console(highlight=False)
errors = Console(stderr=True, highlight=False)


@dataclass
class Options:
    workspace_scripts: Path | None
    demo: bool
    zone: str
    hermes: bool
    config: dict


def local_errors(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ReclaimError as exc:
            from .render import terminal_safe as safe_terminal

            errors.print(safe_terminal(str(exc)), markup=False)
            raise typer.Exit(2) from None
        except (OSError, sqlite3.Error):
            errors.print(
                "Local storage/configuration failure. If execution began, inspect operation status before retrying.",
                markup=False,
            )
            raise typer.Exit(2) from None
        except (KeyError, ValueError):
            errors.print(
                "Invalid request, configuration, or unavailable record. If execution began, inspect operation status.",
                markup=False,
            )
            raise typer.Exit(2) from None

    return call


@app.callback()
def main(
    ctx: typer.Context,
    workspace_scripts: Optional[Path] = typer.Option(
        None, help="Installed google-workspace scripts directory containing _hermes_home.py."
    ),
    demo: bool = typer.Option(
        False, help="Use the explicit synthetic mailbox; never load credentials or contact Gmail."
    ),
    zone: str = typer.Option("UTC", "--timezone", help="IANA timezone for frozen calendar cutoffs."),
    hermes: bool = typer.Option(
        False, help="Minimized counts/opaque references only; suppress senders, subjects, and full lists."
    ),
    config: Optional[Path] = typer.Option(None, help="Local TOML configuration; optional quota settings."),
):
    try:
        ZoneInfo(zone)
        data = tomllib.loads(config.read_text(encoding="utf-8")) if config else {}
        if not isinstance(data.get("quota", {}), dict) or not isinstance(data.get("privacy", {}), dict):
            raise ValueError("Invalid configuration sections")
        if type(data.get("privacy", {}).get("redact_subjects", False)) is not bool:
            raise ValueError("redact_subjects must be boolean")
        if data.get("quota"):
            from .quota import QuotaConfig

            QuotaConfig(**data["quota"])
    except (ZoneInfoNotFoundError, ValueError, TypeError, OSError):
        errors.print("Invalid timezone or unreadable TOML configuration.", markup=False)
        raise typer.Exit(2) from None
    ctx.obj = Options(workspace_scripts, demo, zone, hermes, data)


@contextmanager
def session(options: Options):
    # Called only after capability checks. This composition root never constructs a write adapter.
    from .gmail import FakeGmailAdapter, GoogleReadAdapter
    from .storage import CacheStore, JournalStore

    paths = resolve_profile(options.workspace_scripts)
    paths.initialize()
    with ExitStack() as resources:
        cache = resources.enter_context(CacheStore(paths.cache))
        journal = resources.enter_context(JournalStore(paths.journal))
        quota = None
        if options.demo:
            from .demo import DEMO_IDENTITY, demo_messages

            adapter = FakeGmailAdapter(demo_messages(), identity=DEMO_IDENTITY)
        else:
            from .quota import QuotaConfig, QuotaLimiter
            from .budget import PersistentBudgetLimiter

            base_quota = QuotaLimiter(QuotaConfig(**options.config.get("quota", {})))
            quota = resources.enter_context(PersistentBudgetLimiter(base_quota, paths.journal))
            adapter = GoogleReadAdapter(paths.home, quota=quota)
        adapter.validate_capability("analyze")
        identity = adapter.resolve_identity()
        from .render import terminal_safe as safe_terminal

        from .sender.models import release_status

        sender_released = release_status()["live_mutation_released"]
        if options.hermes:
            errors.print(f"Gate A | local-only | account reference {identity.account_id[:12]}", markup=False)
        else:
            for line in (
                f"Profile: {paths.home}",
                f"Account: {identity.email}",
                (
                    "Gate A metadata session · sender writes require separate native approval"
                    if sender_released
                    else "Gate A · read-only Gmail session · production sender writes disabled"
                )
                + (" · SYNTHETIC DEMO" if options.demo else " · local-only"),
            ):
                errors.print(safe_terminal(line), markup=False)
        with account_lock(paths, identity.account_id):
            journal.bind_account(identity)
            if quota is not None:
                quota.bind_account(identity.account_id)
            from .retention import cleanup

            cleanup(paths, identity.account_id)
            yield paths, adapter, identity, cache, journal


def output(value):
    console.print(json.dumps(value, ensure_ascii=True, indent=2, default=str), markup=False, soft_wrap=True)


def cutoff(options):
    if options.demo:
        from .demo import DEMO_CUTOFF

        return DEMO_CUTOFF.astimezone(ZoneInfo(options.zone))
    return datetime.now(timezone.utc).astimezone(ZoneInfo(options.zone))


def get_inventory(cache, identity):
    value = cache.load(identity.account_id)
    if value is None:
        raise ReclaimError("No published inventory. Run reclaim analyze first.")
    return value


def minimized(report):
    return {
        key: report[key] for key in ("account_id", "generation", "coverage", "totals") if key in report
    } | {
        "release_gate": "A",
        "mutation_enabled": False,
        "estimated_not_quota": True,
    }


@app.command()
@local_errors
def analyze(
    ctx: typer.Context,
    full_resync: bool = False,
    html: Optional[Path] = None,
    json_output: bool = typer.Option(False, "--json"),
    redact_subjects: bool = False,
    attachments: bool = typer.Option(
        False, help="Opt in to a separate bounded MIME-name/size inspection; no attachment content downloads."
    ),
    max_attachment_messages: int = typer.Option(1000, min=1, max=10000),
    max_messages: Optional[int] = typer.Option(
        None,
        min=1,
        help="Read at most N messages in Gmail listing order (newest not guaranteed). "
        "Partial preview only; leaves full cache unchanged.",
    ),
    cached: bool = typer.Option(
        False, help="Render the published inventory without metadata synchronization."
    ),
):
    """Synchronize metadata; print a report and optionally save private self-contained HTML."""
    from .analytics import build_report
    from .render import render_html, render_terminal
    from .sync import SyncService
    from .workflow import run_read_workflow

    options = ctx.obj
    if max_messages is not None and (cached or full_resync or attachments):
        raise ReclaimError(
            "--max-messages cannot be combined with --cached, --full-resync, or --attachments."
        )
    if html and options.hermes:
        raise ReclaimError(
            "Raw HTML export is a local workflow; omit --hermes only outside hosted conversation."
        )
    with session(options) as (paths, adapter, identity, cache, journal):
        if html:
            paths.validate_export(html)
        redact = (
            redact_subjects
            or options.hermes
            or options.config.get("privacy", {}).get("redact_subjects", False)
        )
        snapshot = {}

        def progress(event):
            if errors.is_terminal and event.get("phase") == "metadata" and event.get("fetched", 0) % 100 == 0:
                fetched = event["fetched"]
                total = (
                    max_messages
                    if max_messages is not None
                    else getattr(adapter, "_last_profile", {}).get("messagesTotal")
                )
                quota = getattr(adapter, "quota", None)
                note = ""
                if type(total) is int and quota is not None:
                    units = max(0, total - fetched) * quota.config.method_costs["get"]
                    note = f"; estimated remaining metadata cost {units:,} units (excludes pages/history/retries)"
                errors.print(f"Metadata read: {fetched:,}{note}", markup=False)

        def read():
            if max_messages is not None:
                errors.print(
                    f"Limited preview: at most {max_messages:,} messages in Gmail listing order; "
                    "newest not guaranteed. Full cache and pending scan remain unchanged.",
                    markup=False,
                )
                snapshot["inventory"] = SyncService(
                    adapter, cache, redact_subjects=redact, progress=progress
                ).limited_scan(max_messages)
            elif cached:
                snapshot["inventory"] = get_inventory(cache, identity)
            else:
                from .staging import ResumableReadAdapter

                with ResumableReadAdapter(adapter, paths.cache, redact_subjects=redact) as reader:
                    service = SyncService(reader, cache, redact_subjects=redact, progress=progress)
                    inventory = (
                        service.full_sync()
                        if full_resync or reader.has_pending_scan()
                        else service.incremental_sync()
                    )
                    reader.complete_scan()
                    snapshot["inventory"] = inventory
            return snapshot["inventory"]

        state = run_read_workflow(paths, identity, read)
        inventory = snapshot["inventory"]
        findings = None
        if attachments:
            from .mime import GoogleMimeReader, DemoMimeReader, inspect_mime

            reader = DemoMimeReader(adapter) if options.demo else GoogleMimeReader(adapter)
            findings = inspect_mime(reader, inventory, max_messages=max_attachment_messages)
        report = build_report(inventory, cutoff(options), timezone=options.zone, attachment_findings=findings)
        report["fixture"] = "synthetic" if options.demo else None
        report["workflow_id"] = state["workflow_id"]
        quota = getattr(adapter, "quota", None)
        if quota is not None:
            report["quota"] = {
                "cost_table_version": quota.config.version,
                "session_units_reserved": quota.units_used,
                "rolling_day_units_reserved": quota.reserved_units(),
                "daily_budget": quota.config.daily_budget,
            }
        if html:
            if options.hermes:
                raise ReclaimError(
                    "Raw HTML export is a local workflow; omit --hermes only outside hosted conversation."
                )
            private_write(html, render_html(report))
        if options.hermes:
            output(minimized(report))
        elif json_output:
            output(report)
        else:
            console.print(render_terminal(report), markup=False)


@app.command()
@local_errors
def propose(
    ctx: typer.Context,
    action: str = typer.Option("trash"),
    promo_age: str = "6m",
    min_batch_mb: int = typer.Option(100, min=0),
    max_batch_messages: int = typer.Option(100, min=1, max=1000),
    plan: Optional[str] = typer.Option(
        None, help="Explicit existing plan ID for a fresh immutable revision."
    ),
    source_plan: Optional[str] = None,
):
    """Seal bounded, non-overlapping trash candidates; this is not permission to execute."""
    if action != "trash" or source_plan is not None:
        gate_check("permanent_delete")
    match = re.fullmatch(r"([1-9][0-9]*)([my])", promo_age)
    if not match:
        raise ReclaimError("--promo-age must be a positive calendar interval such as 6m or 1y")
    months = int(match[1]) * (12 if match[2] == "y" else 1)
    if months > 1200:
        raise ReclaimError("--promo-age cannot exceed 100 calendar years")
    from .proposals import ProposalService
    from .workflow import run_read_workflow

    options = ctx.obj
    rules = [
        Rule("large-old", "SIZE_AGE", 10_000_000, 12),
        Rule("newsletter-old", "SENDER_NEWSLETTER", older_months=12),
        Rule("promotions-old", "CATEGORY_AGE", older_months=months, category="CATEGORY_PROMOTIONS"),
    ]
    with session(options) as (paths, adapter, identity, cache, journal):
        service = ProposalService(cache, journal, adapter)
        result = {}

        def build():
            result["plan"] = service.build_revision(
                identity,
                rules,
                cutoff(options),
                min_batch_bytes=min_batch_mb * 1_000_000,
                max_batch_messages=max_batch_messages,
                plan_id=plan,
            )
            return result["plan"]

        run_read_workflow(paths, identity, lambda: get_inventory(cache, identity), build)
        value = result["plan"]
        output(
            {
                "account_id": value.account_id,
                "plan_id": value.plan_id,
                "revision": value.revision,
                "action": value.action,
                "policy_version": value.policy_version,
                "inventory_generation": value.inventory_generation,
                "executable": False,
                "mutation_enabled": False,
                "totals": {
                    "unique_messages": sum(len(b.ids) for b in value.batches),
                    "estimated_bytes": sum(b.estimated_bytes for b in value.batches),
                },
                "skips_by_reason": dict(Counter(service.last_skips.values())),
                "batches": [
                    {
                        "batch_id": b.batch_id,
                        "kind": b.kind,
                        "message_count": len(b.ids),
                        "estimated_bytes": b.estimated_bytes,
                        "membership_digest": b.digest,
                    }
                    for b in value.batches
                ],
                "notice": "Proposal only. SENT-thread evidence is a conservative heuristic, not proof of no reply.",
            }
        )


@app.command(name="list")
@local_errors
def list_batch(
    ctx: typer.Context,
    plan: str = typer.Option(...),
    revision: int = typer.Option(..., min=1),
    batch: str = typer.Option(...),
    page: int = typer.Option(1, min=1),
):
    """Paginated immutable membership; read-only, never advances a confirmation challenge."""
    with session(ctx.obj) as (_, _, identity, cache, journal):
        if ctx.obj.hermes:
            output(
                {
                    "plan_id": plan,
                    "revision": revision,
                    "batch_id": batch,
                    "requires_local_view": True,
                    "mutation_enabled": False,
                }
            )
            return
        data = journal.list_batch(identity.account_id, plan, revision, batch, page=page)
        inventory = get_inventory(cache, identity)
        messages = {m.id: m for m in inventory.messages}
        data["messages"] = [
            {
                "id": message_id,
                "subject": messages[message_id].subject,
                "internal_date": messages[message_id].internal_date,
                "estimated_bytes": messages[message_id].size_estimate,
            }
            if message_id in messages
            else {"id": message_id, "status": "not_in_current_cache"}
            for message_id in data["ids"]
        ]
        data["action"] = "trash"
        data["executable"] = False
        output(data)


@app.command()
@local_errors
def confirm(
    ctx: typer.Context,
    plan: str = typer.Option(...),
    revision: int = typer.Option(..., min=1),
    batch: str = typer.Option(...),
    action: str = "trash",
    reject: bool = False,
):
    """Gate A can record rejection only; it cannot mint a trusted mutation approval."""
    if not reject:
        gate_check("trash")
    if action != "trash":
        raise ReclaimError("Gate A can reject trash proposals only; other action workflows are unavailable.")
    with session(ctx.obj) as (_, _, identity, _, journal):
        journal.reject_batch(identity.account_id, plan, revision, batch)
        output(
            {
                "plan_id": plan,
                "revision": revision,
                "batch_id": batch,
                "decision": "rejected",
                "reassignment": False,
                "approval_id": None,
            }
        )


@app.command()
@local_errors
def execute(approval: str = typer.Option(...), execute: bool = False):
    """Unavailable until Gate B/C: --execute never constitutes human approval."""
    gate_check("trash", execute)


@app.command()
@local_errors
def restore(source_operation: str = typer.Option(...), execute: bool = False):
    """Unavailable until independently approved restoration and Gate B tests pass."""
    gate_check("restore", execute)


@app.command()
@local_errors
def protect(ctx: typer.Context, sender: str = typer.Option(...), reason: str = ""):
    from .analytics import parse_sender

    address = parse_sender(sender)
    if address is None:
        raise ReclaimError("Supply one valid sender mailbox address")
    with session(ctx.obj) as (_, _, identity, _, journal):
        journal.protect_sender(identity.account_id, address, reason)
        output({"account_id": identity.account_id, "protected": True})


@protections_app.command(name="list")
@local_errors
def protections_list(ctx: typer.Context):
    with session(ctx.obj) as (_, _, identity, _, journal):
        values = sorted(journal.protections(identity.account_id))
        output({"count": len(values)} if ctx.obj.hermes else {"senders": values})


@protections_app.command(name="remove")
@local_errors
def protections_remove(sender: str = typer.Option(...)):
    raise ReclaimError(
        "Protection removal broadens eligibility and requires an independent human confirmation surface; unavailable in Gate A."
    )


@app.command()
@local_errors
def status(ctx: typer.Context, plan: Optional[str] = None):
    with session(ctx.obj) as (_, _, identity, cache, journal):
        value = journal.status(identity.account_id)
        value["release_gate"] = "A"
        value["mutation_enabled"] = False
        inventory = cache.load(identity.account_id)
        value["inventory"] = (
            {
                "generation": inventory.generation,
                "complete": inventory.complete,
                "cursor": inventory.cursor,
                "message_count": len(inventory.messages),
            }
            if inventory
            else None
        )
        if plan:
            value["plans"] = [
                {"plan_id": p.plan_id, "revision": p.revision, "status": p.status}
                for p in journal.plans(identity.account_id)
                if p.plan_id == plan
            ]
        output(value)


@app.command()
@local_errors
def reconcile(ctx: typer.Context):
    """Gate A has no remote writes to reconcile; show the journal's recovery backlog."""
    with session(ctx.obj) as (_, _, identity, _, journal):
        output(
            {
                "mutation_enabled": False,
                "journal_status": journal.status(identity.account_id),
                "notice": "No write recovery is enabled in Gate A. Existing unknown operations require manual review.",
            }
        )


@audit_app.command(name="export")
@local_errors
def audit_export(ctx: typer.Context, output_path: Path = typer.Option(..., "--output")):
    with session(ctx.obj) as (paths, _, identity, _, journal):
        paths.validate_export(output_path)
        if not output_path.exists():
            private_write(output_path, "")
        from .profile import make_private

        make_private(output_path)
        output(journal.export_audit(output_path))


@cache_app.command(name="rebuild")
@local_errors
def cache_rebuild(ctx: typer.Context, redact_subjects: bool = False):
    """Rebuild only metadata. Journal and workflow databases remain untouched."""
    from .sync import SyncService
    from .staging import ResumableReadAdapter

    with session(ctx.obj) as (paths, adapter, identity, cache, _):
        # Stage a new full scan instead of deleting the good generation before network success.
        redact = (
            redact_subjects
            or ctx.obj.hermes
            or ctx.obj.config.get("privacy", {}).get("redact_subjects", False)
        )
        with ResumableReadAdapter(adapter, paths.cache, redact_subjects=redact) as reader:
            reader.discard_stage()
            inventory = SyncService(reader, cache, redact_subjects=redact).full_sync()
            reader.complete_scan()
        output(
            {
                "generation": inventory.generation,
                "message_count": len(inventory.messages),
                "journal_preserved": True,
                "checkpoints_preserved": True,
            }
        )


register_sender_commands(app)
