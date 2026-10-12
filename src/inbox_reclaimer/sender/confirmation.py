"""Native, local-only action confirmation. No stdin/flag/JSON approval input."""

import getpass
import time
from uuid import uuid4

from ..analytics import parse_sender
from ..render import terminal_safe
from .models import Approval
from .render import WARNING, display_date


def validate_preview(plan, identity, messages):
    if identity.account_id != plan.account_id or tuple(sorted(m.id for m in messages)) != plan.ids:
        raise ValueError("Confirmation view does not match the exact account and plan membership")
    if any(parse_sender(m.raw_from) != plan.sender for m in messages):
        raise ValueError("Confirmation messages do not match the plan sender")


class ConfirmationWindow:
    def __init__(self, root, plan, identity, messages, synthetic=False, validation=False):
        import tkinter as tk
        from tkinter import ttk

        validate_preview(plan, identity, messages)
        reconciliation = plan.action == "reconcile_external"
        self.root, self.plan, self.identity = root, plan, identity
        self.decision = None
        self.challenge = uuid4().hex
        root.title("Inbox Reclaimer — Review sender cleanup" + (" — SYNTHETIC DEMO" if synthetic else ""))
        root.geometry("1060x740")
        root.minsize(800, 600)
        root.protocol("WM_DELETE_WINDOW", self.cancel)
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)
        title = (
            "Move selected messages to Trash" if plan.action == "trash" else "Restore tool-trashed messages"
        )
        if reconciliation:
            title = "Acknowledge manual recovery — no Gmail changes"
        ttk.Label(frame, text=title, font=("Segoe UI", 19, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text=(
                f"Account: {terminal_safe(identity.email)}\nSender: {terminal_safe(plan.sender)}\n"
                f"Action: {plan.action.upper()} | Exact messages: {len(plan.ids):,} | "
                + (
                    "SYNTHETIC — NO GMAIL ACCESS"
                    if synthetic
                    else "DISPOSABLE-ACCOUNT VALIDATION — LIVE MAILBOX"
                    if validation
                    else "LIVE MAILBOX"
                )
            ),
            font=("Segoe UI", 11),
        ).grid(row=1, column=0, sticky="w", pady=10)
        ttk.Label(frame, text=f"Plan {plan.plan_id}\nMembership digest {plan.digest}", wraplength=970).grid(
            row=2, column=0, sticky="w"
        )
        warning = WARNING
        if reconciliation:
            warning = (
                "The message currently matches its original pre-trash state. This records your acknowledgement "
                "of external recovery; it does not prove an earlier write succeeded. Original operation "
                "records, including UNKNOWN outcomes, are preserved. No Gmail changes are made. "
                "New actions still require separate approval. Verified original labels: "
                + ", ".join(terminal_safe(label) for label in sorted(messages[0].labels))
            )
        ttk.Label(frame, text=warning, wraplength=970).grid(row=3, column=0, sticky="w", pady=10)
        ttk.Label(
            frame, text="Review the exact list below. Cancel is the default; Enter does not approve."
        ).grid(row=4, column=0, sticky="w", pady=(0, 8))
        table_frame = ttk.Frame(frame)
        table_frame.grid(row=5, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("id", "date", "bytes", "subject")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings")
        for col, label, width in zip(
            columns, ("Message ID", "Date (UTC)", "Estimated bytes", "Subject"), (170, 210, 120, 440)
        ):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, minwidth=100)
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        for message in messages:
            self.table.insert(
                "",
                "end",
                values=tuple(
                    terminal_safe(v)
                    for v in (
                        message.id,
                        display_date(message.internal_date),
                        message.size_estimate,
                        message.subject if message.subject is not None else "[redacted]",
                    )
                ),
            )
        self.email = tk.StringVar(master=root)
        self.acknowledged = tk.BooleanVar(master=root, value=False)
        ttk.Checkbutton(
            frame,
            text=(
                "I acknowledge the manual recovery and understand the original outcome remains unknown."
                if reconciliation
                else "I reviewed this exact selection and understand the action and retention warning."
            ),
            variable=self.acknowledged,
            command=self.update_enabled,
        ).grid(row=6, column=0, sticky="w", pady=(12, 4))
        ttk.Label(frame, text="Type the exact account email shown above to enable confirmation:").grid(
            row=7, column=0, sticky="w"
        )
        ttk.Entry(frame, textvariable=self.email).grid(row=8, column=0, sticky="ew", pady=4)
        self.email.trace_add("write", lambda *_: self.update_enabled())
        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel — change nothing", command=self.cancel).pack(side="left", padx=8)
        self.confirm_button = ttk.Button(
            buttons,
            text=(
                "Record external recovery"
                if reconciliation
                else f"Confirm {plan.action} for {len(plan.ids):,} messages"
            ),
            command=self.accept,
            state="disabled",
        )
        self.confirm_button.pack(side="left")

    def update_enabled(self):
        allowed = self.email.get() == self.identity.email and self.acknowledged.get()
        self.confirm_button.state(["!disabled"] if allowed else ["disabled"])

    def accept(self):
        if self.email.get() != self.identity.email or not self.acknowledged.get():
            return
        now = time.time()
        self.decision = Approval(
            self.plan.account_id,
            self.plan.plan_id,
            self.plan.digest,
            self.plan.action,
            getpass.getuser(),
            uuid4().hex,
            self.challenge,
            now,
            now + 900,
        )
        self.root.quit()

    def cancel(self):
        self.decision = None
        self.root.quit()


def confirm_plan(plan, identity, messages, synthetic=False, validation=False):
    import tkinter as tk

    root = tk.Tk()
    try:
        view = ConfirmationWindow(root, plan, identity, messages, synthetic, validation)
        root.mainloop()
        return view.decision
    finally:
        root.destroy()
