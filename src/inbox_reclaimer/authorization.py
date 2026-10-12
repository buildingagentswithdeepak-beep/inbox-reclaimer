"""First-time, interactive Gmail-readonly OAuth bootstrap. Never replaces credentials.

Consent occurs in the operator's browser. Only token metadata and Gmail getProfile
are read for validation; no message bodies, mailbox changes or approval records.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

import portalocker

from .models import ReclaimError
from .profile import account_lock, make_private, private_write, resolve_profile
from .render import terminal_safe

READONLY = "https://www.googleapis.com/auth/gmail.readonly"


def load_client(paths):
    target = paths.home / "google_token.json"
    if os.path.lexists(target):
        raise ReclaimError("google_token.json already exists; this first-time helper will not replace it.")
    source = paths.home / "google_client_secret.json"
    try:
        if source.is_symlink() or source.stat().st_size > 262144:
            raise ValueError
        config = json.loads(source.read_text(encoding="utf-8-sig"))
        installed = config["installed"]
        if not all(
            isinstance(installed.get(k), str) and installed[k].strip() for k in ("client_id", "client_secret")
        ):
            raise ValueError
        if installed.get("auth_uri") not in {
            "https://accounts.google.com/o/oauth2/auth",
            "https://accounts.google.com/o/oauth2/v2/auth",
        }:
            raise ValueError
        if installed.get("token_uri") != "https://oauth2.googleapis.com/token":
            raise ValueError
    except Exception:
        raise ReclaimError("A valid Google Desktop-app client JSON is required in this profile.") from None
    # Do not pass arbitrary downloaded endpoint/redirect fields to the OAuth library.
    return {
        "installed": {key: installed[key] for key in ("client_id", "client_secret", "auth_uri", "token_uri")}
    }


def browser_consent(config, *, manual_browser=False):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise ReclaimError("Install sign-in support with: uv sync --frozen --extra auth") from None

    # OAuth debug logs can contain codes/tokens; this is a separate local process.
    for name in (
        "google_auth_oauthlib",
        "google_auth_oauthlib.flow",
        "oauthlib",
        "requests_oauthlib",
        "urllib3",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL + 1)
        logging.getLogger(name).disabled = True
    flow = InstalledAppFlow.from_client_config(config, [READONLY], autogenerate_code_verifier=True)
    try:
        return flow.run_local_server(
            host="127.0.0.1",
            bind_addr="127.0.0.1",
            port=0,
            timeout_seconds=300,
            open_browser=not manual_browser,
            authorization_prompt_message=(
                "Open this sign-in link in a browser on this computer within five minutes.\n"
                "Keep this terminal running. Do not share this link or the callback URL.\n{url}\n"
                if manual_browser
                else ""
            ),
            success_message="Google authorization received. Return to your local terminal to confirm the account.",
            access_type="offline",
            prompt="consent",
            include_granted_scopes="false",
        )
    finally:
        flow.oauth2session.close()


def verify_staged(directory, client_id):
    from .gmail import GoogleReadAdapter

    adapter = GoogleReadAdapter(directory, max_attempts=1)
    identity = adapter.resolve_identity()
    # resolve_identity verified these actual tokeninfo grants, not requested scopes.
    if adapter._grants != {READONLY}:
        raise ReclaimError("Google did not grant exactly Gmail readonly; credentials were not adopted.")
    if identity.oauth_client_id != client_id:
        raise ReclaimError("Authorized OAuth client differs from the selected client configuration.")
    return identity


def check_bound_account(paths, identity):
    if not paths.journal.exists():
        return
    from .storage import JournalStore

    with sqlite3.connect(f"{paths.journal.as_uri()}?mode=ro", uri=True) as connection:
        if connection.execute("PRAGMA application_id").fetchone()[0] != JournalStore.application_id:
            raise ReclaimError("Cannot verify the existing journal account; credentials were not adopted.")
        rows = connection.execute("SELECT account_id FROM accounts").fetchall()
        if rows and (len(rows) != 1 or rows[0][0] != identity.account_id):
            raise ReclaimError("This profile journal belongs to another account or OAuth client.")


def confirm_account(identity):
    print("Verified Gmail account: " + terminal_safe(identity.email))
    print("Only Gmail readonly was granted. No mail will be changed.")
    return (
        input("Type that exact email address to save credentials (Enter cancels): ").strip() == identity.email
    )


def authorize(paths, *, consent=None, verify=None, confirm=None):
    consent = consent or browser_consent
    verify = verify or verify_staged
    confirm = confirm or confirm_account
    try:
        config = load_client(paths)
        paths.initialize()
        with portalocker.Lock(
            str(paths.locks / "oauth-bootstrap.lock"),
            mode="a",
            timeout=0,
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
        ):
            config = load_client(paths)  # Recheck after the profile-level lock.
            make_private(paths.home / "google_client_secret.json")
            credentials = consent(config)
            client_id = config["installed"]["client_id"]
            if credentials.client_id != client_id or not credentials.refresh_token:
                raise ReclaimError(
                    "A matching client and an offline refresh token are required; no token saved."
                )
            with tempfile.TemporaryDirectory(prefix=".oauth-", dir=paths.root) as temporary:
                staging = Path(temporary)
                make_private(staging, directory=True)
                staged_token = staging / "google_token.json"
                private_write(staged_token, credentials.to_json())
                identity = verify(staging, client_id)
                if identity.oauth_client_id != client_id:
                    raise ReclaimError("The verified account has a different OAuth client.")
                check_bound_account(paths, identity)
                if not confirm(identity):
                    raise ReclaimError("Authorization cancelled locally; no token saved.")
                with account_lock(paths, identity.account_id):
                    check_bound_account(paths, identity)
                    # Same-filesystem hard link atomically publishes the already private,
                    # fsynced file and fails if ANY target exists. Never use os.replace here.
                    os.link(staged_token, paths.home / "google_token.json")
                return identity
    except ReclaimError:
        raise
    except (KeyboardInterrupt, EOFError):
        raise ReclaimError("Authorization cancelled locally; no token saved.") from None
    except Exception:
        raise ReclaimError(
            "Authorization failed; existing credentials were not replaced. "
            "Check consent, network, API enablement and local permissions. "
            "Do not share token files or authorization URLs."
        ) from None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="First-time local Gmail-readonly sign-in; never replaces tokens."
    )
    parser.add_argument("--workspace-scripts", type=Path, required=True)
    parser.add_argument(
        "--manual-browser",
        action="store_true",
        help="Display a private sign-in link in this local terminal instead of opening the browser.",
    )
    parser.add_argument(
        "--check", action="store_true", help="Check client-file format only; no network or sign-in."
    )
    args = parser.parse_args(argv)
    if not args.check and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        print(
            "Run sign-in directly in an interactive local terminal, not through a hosted agent.",
            file=sys.stderr,
        )
        return 2
    try:
        paths = resolve_profile(args.workspace_scripts)
        load_client(paths)
        print("Selected profile: " + terminal_safe(str(paths.home)))
        if args.check:
            print("Desktop client configuration valid; token absent. No Google request was made.")
            return 0
        if args.manual_browser:
            print("Manual browser sign-in: open the link below yourself, then confirm your email here.")
        else:
            print("Opening Google consent for Gmail readonly. Confirm your Gmail address here afterward.")
        authorize(paths, consent=lambda config: browser_consent(config, manual_browser=args.manual_browser))
        print(
            "Saved private google_token.json. You can now run reclaim analyze. No messages were read or changed."
        )
        return 0
    except ReclaimError as error:
        print(terminal_safe(str(error)), file=sys.stderr)
        return 2
    except Exception:
        print("Unable to initialize local authorization; no credentials were replaced.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
