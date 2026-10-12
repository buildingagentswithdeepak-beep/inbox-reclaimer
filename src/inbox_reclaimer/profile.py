"""Installed-helper profile resolution and private, process-locked local state."""

from __future__ import annotations

import importlib
import importlib.util
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import portalocker

from .models import GateClosed, ReclaimError


def gate_check(action: str, execute: bool = False) -> None:
    if action not in {"analyze", "propose", "read"}:
        raise GateClosed(
            "Gate A is read-only. Trusted approvals, trash, restore and permanent deletion are unavailable. "
            "Gates B/C require separate safety and explicitly approved isolated-account live tests; "
            "--execute, environment flags and graph resumes cannot enable them."
        )


def make_private(path: Path, directory: bool = False) -> None:
    """Protect only application-owned paths, including inheritance for new SQLite sidecars."""
    if os.name == "nt":
        import win32api
        import win32con
        import win32security

        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        finally:
            token.Close()
        acl = win32security.ACL()
        flags = (win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE) if directory else 0
        acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, flags, win32con.GENERIC_ALL, sid)
        system = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid)
        acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, flags, win32con.GENERIC_ALL, system)
        win32security.SetNamedSecurityInfo(
            str(path),
            win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            None,
            None,
            acl,
            None,
        )
    else:
        path.chmod(0o700 if directory else 0o600)


@dataclass(frozen=True)
class ProfilePaths:
    home: Path

    @property
    def root(self):
        return self.home / "inbox_reclaimer"

    @property
    def cache(self):
        return self.root / "cache.db"

    @property
    def journal(self):
        return self.root / "journal.db"

    @property
    def checkpoints(self):
        return self.root / "checkpoints.db"

    @property
    def reports(self):
        return self.root / "reports"

    @property
    def locks(self):
        return self.root / "locks"

    def initialize(self):
        if str(self.root).startswith(("\\\\", "//")):
            raise ReclaimError("Network-share state and locks are unsupported")
        for directory in (self.root, self.reports, self.locks, self.root / "audit", self.root / "logs"):
            if directory.is_symlink():
                raise ReclaimError("Application state directories cannot be symbolic links")
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            make_private(directory, directory=True)
        for file in self.root.glob("*.db*"):
            if file.is_symlink():
                raise ReclaimError("Application databases cannot be symbolic links")
            make_private(file)

    def validate_export(self, output: Path):
        output = output.expanduser().resolve()
        protected = {
            self.cache.resolve(),
            self.journal.resolve(),
            self.checkpoints.resolve(),
            (self.home / "google_token.json").resolve(),
            (self.home / "google_client_secret.json").resolve(),
        }
        if output in protected or output.suffix in {".db", ".db-wal", ".db-shm", ".lock"}:
            raise ReclaimError("Export cannot overwrite credentials, databases or locks")
        if output.is_relative_to(self.root.resolve()) and not any(
            output.is_relative_to(p.resolve()) for p in (self.reports, self.root / "audit")
        ):
            raise ReclaimError("Exports inside application state must be in reports/ or audit/")


def resolve_profile(workspace_scripts: Path | None = None) -> ProfilePaths:
    """Import the installed skill helper, never reconstruct its fallback or search credentials."""
    try:
        if workspace_scripts is None:
            module = importlib.import_module("_hermes_home")
        else:
            helper = workspace_scripts.expanduser().resolve() / "_hermes_home.py"
            if not helper.is_file():
                raise ReclaimError("Installed google-workspace helper is missing; supply --workspace-scripts")
            spec = importlib.util.spec_from_file_location("_reclaim_installed_hermes_home", helper)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        home = Path(module.get_hermes_home()).expanduser().resolve()
    except (ImportError, AttributeError, OSError) as exc:
        raise ReclaimError(
            "Cannot load the installed google-workspace helper; supply --workspace-scripts"
        ) from exc
    return ProfilePaths(home)


def private_write(path: Path, content: str) -> None:
    """Atomic export; data is never written before the temporary file is private."""
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".reclaim-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            make_private(temporary)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def account_lock(paths: ProfilePaths, account_id: str):
    if not re.fullmatch(r"[a-f0-9]{64}", account_id):
        raise ReclaimError("Invalid opaque account reference")
    lock_path = paths.locks / f"{account_id}.lock"
    try:
        with portalocker.Lock(
            str(lock_path), mode="a", timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB
        ):
            make_private(lock_path)
            yield
    except portalocker.exceptions.LockException as exc:
        raise ReclaimError("Account is locked by another local session; retry after it finishes") from exc
