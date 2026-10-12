"""Narrow pre-release test scope; never enables ordinary production commands."""

from dataclasses import dataclass, field
import math
from pathlib import Path
import re
import time

from ..models import GateClosed
from .models import exact_sender


def validation_home():
    return Path.home() / "inbox-reclaimer-validation"


@dataclass(frozen=True)
class DisposableValidation:
    email: str
    sender: str
    account_id: str | None = None
    ids: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.email != exact_sender(self.email) or self.sender != exact_sender(self.sender):
            raise ValueError("Expected canonical disposable account and sender addresses")
        if self.account_id is not None and (
            not isinstance(self.account_id, str) or not re.fullmatch("[a-f0-9]{64}", self.account_id)
        ):
            raise ValueError("Invalid bound validation account")
        if (
            type(self.ids) is not tuple
            or len(self.ids) > 5
            or any(not isinstance(i, str) or not i for i in self.ids)
            or tuple(sorted(set(self.ids))) != self.ids
            or (self.ids and self.account_id is None)
        ):
            raise ValueError("Validation permits at most five sorted unique account-bound IDs")
        if type(self.created_at) not in (int, float) or not math.isfinite(self.created_at):
            raise ValueError("Invalid validation timestamp")

    def check(self):
        age = time.time() - self.created_at
        if not math.isfinite(age) or not 0 <= age < 900:
            raise GateClosed("Disposable-account validation session expired; restart locally")

    def check_home(self, home):
        self.check()
        expected = validation_home()
        if expected.is_symlink() or Path(home).is_symlink() or Path(home).resolve() != expected.absolute():
            raise GateClosed("Validation requires its dedicated credential home, never a normal profile")
        for name in ("google_token.json", "google_client_secret.json"):
            candidate = expected / name
            if candidate.is_symlink():
                raise GateClosed("Validation credentials cannot link to another profile")
            if candidate.exists() and candidate.stat().st_nlink != 1:
                raise GateClosed("Validation credentials must not be hard-linked to another profile")

    def check_account(self, identity):
        self.check()
        if identity.email != self.email or (
            self.account_id is not None and identity.account_id != self.account_id
        ):
            raise GateClosed("Verified Gmail account/client differs from the disposable validation scope")

    def check_ids(self, ids):
        self.check()
        if (
            not self.account_id
            or not self.ids
            or not isinstance(ids, (tuple, list))
            or not ids
            or len(ids) != len(set(ids))
            or not set(ids) <= set(self.ids)
        ):
            raise GateClosed("Write is outside the frozen disposable-account validation selection")
