"""Optional, local-only Gmail-modify consent; gated until disposable-account Gate B.

Run with ``python -m inbox_reclaimer.sender.authorization --workspace-scripts PATH``.
``--check`` is local validation only and never authorizes or contacts Google.
Original credentials stay byte-for-byte intact until verified same-account consent,
exact local email confirmation and a locked, race-checked atomic replacement.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import stat
import sys
import tempfile

import portalocker

from ..authorization import check_bound_account
from ..models import ReclaimError
from ..profile import account_lock, make_private, private_write, resolve_profile
from ..render import terminal_safe
from .models import require_live_release

READONLY = "https://www.googleapis.com/auth/gmail.readonly"
MODIFY = "https://www.googleapis.com/auth/gmail.modify"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_AUTH_URIS = {"https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth"}
_FAILURE = (
    "Modify authorization failed; existing credentials were not replaced. "
    "Do not share token files, authorization URLs or callback codes."
)


class _AuthorizationError(ReclaimError):
    """Only our own fixed messages may escape the consent/error boundary."""


def _local_file(path):
    """Bounded regular-file snapshot, rejecting links and mid-read changes."""
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 262144:
        raise _AuthorizationError("A private regular Google configuration file is required")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        data = stream.read(262145)
        after = os.fstat(stream.fileno())

    def signature(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    marker = signature(before)
    if len(data) > 262144 or marker != signature(opened) or marker != signature(after):
        raise _AuthorizationError("Google configuration changed while being read")
    if marker != signature(path.lstat()):
        raise _AuthorizationError("Google configuration changed while being read")
    return data, marker


def load_client(paths):
    """Validate the selected profile only; an existing token is expected, not rejected."""
    try:
        raw, _ = _local_file(paths.home / "google_client_secret.json")
        installed = json.loads(raw.decode("utf-8-sig"))["installed"]
        if not isinstance(installed, dict) or any(
            not isinstance(installed.get(key), str) or not installed[key].strip()
            for key in ("client_id", "client_secret")
        ):
            raise ValueError
        if installed.get("auth_uri") not in _AUTH_URIS or installed.get("token_uri") != _TOKEN_URI:
            raise ValueError
        # Never pass downloaded redirect, certificate or alternate endpoint fields.
        return {
            "installed": {
                key: installed[key] for key in ("client_id", "client_secret", "auth_uri", "token_uri")
            }
        }
    except Exception:
        raise _AuthorizationError(
            "A valid Google Desktop-app client JSON is required in this profile"
        ) from None


def _token_data(raw, client):
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("client_id") != client["client_id"]:
            raise ValueError
        if data.get("client_secret") != client["client_secret"]:
            raise ValueError
        if data.get("token_uri", _TOKEN_URI) != _TOKEN_URI:
            raise ValueError
        if data.get("universe_domain", "googleapis.com") != "googleapis.com":
            raise ValueError
        for key in ("token", "refresh_token"):
            if data.get(key) is not None and (not isinstance(data[key], str) or not data[key]):
                raise ValueError
        return data
    except Exception:
        raise _AuthorizationError("Token and selected Google client configuration do not match") from None


def _interactive():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise _AuthorizationError(
            "Run modify sign-in directly in an interactive local terminal, not an agent"
        )


def browser_consent(config, *, manual_browser=False, validation=None):
    if validation is None:
        require_live_release()
    else:
        require_live_release(validation)
    _interactive()
    print("PRIVILEGE INCREASE: Gmail modify permits reading, moving mail to Trash and changing labels.")
    print("This requests gmail.modify only, with no Drive or full-mail scope.")
    print("The permission also permits sending, although Inbox Reclaimer exposes no send operation.")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise _AuthorizationError("Install sign-in support with: uv sync --frozen --extra auth") from None
    for name in (
        "google_auth_oauthlib",
        "google_auth_oauthlib.flow",
        "oauthlib",
        "requests_oauthlib",
        "urllib3",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL + 1)
        logging.getLogger(name).disabled = True
    flow = None
    try:
        flow = InstalledAppFlow.from_client_config(config, [MODIFY], autogenerate_code_verifier=True)
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
    except (KeyboardInterrupt, EOFError):
        raise _AuthorizationError("Authorization cancelled locally; existing credentials retained") from None
    except Exception:
        raise _AuthorizationError(_FAILURE) from None
    finally:
        if flow is not None:
            try:
                flow.oauth2session.close()
            except Exception:
                pass


def verify_staged(directory, client_id, *, require_modify=True):
    """Verify actual grants and Gmail identity, not token-file requested scopes.

    The old snapshot may have readonly or modify. The new snapshot must include
    modify and may additionally include readonly; all unrelated scopes are refused.
    GoogleReadAdapter refreshes only explicitly, then tokeninfo-validates grants
    and rebinds identity before any Gmail request; transport auto-refresh is absent.
    """
    from ..gmail import GoogleReadAdapter

    try:
        adapter = GoogleReadAdapter(directory, max_attempts=1)
        identity = adapter.resolve_identity()
        grants = adapter._grants
        if not grants or not grants <= {READONLY, MODIFY} or (require_modify and MODIFY not in grants):
            raise _AuthorizationError("Google did not grant the required narrow Gmail capability")
        if identity.oauth_client_id != client_id:
            raise _AuthorizationError("Verified OAuth client differs from the selected configuration")
        return identity
    except _AuthorizationError:
        raise
    except Exception:
        raise _AuthorizationError(
            "Cannot verify Google grants and account; existing credentials retained"
        ) from None


def confirm_account(identity):
    _interactive()
    print("Verified same Gmail account: " + terminal_safe(identity.email))
    print(
        "Gmail modify is a privilege increase; it permits mail and label changes. No messages changed here."
    )
    return input("Type that exact email address to replace credentials (Enter cancels): ") == identity.email


def authorize_modify(paths, *, consent=None, verify=None, confirm=None, validation=None):
    if validation is None:
        require_live_release()  # No credentials touched before this gate.
    else:
        require_live_release(validation)
        validation.check_home(paths.home)
    if consent is None or verify is None or confirm is None:
        _interactive()  # Real/default validation cannot touch credentials from an agent session.
    consent = consent or (lambda config: browser_consent(config, validation=validation))
    verify = verify or verify_staged
    confirm = confirm or confirm_account
    try:
        config = load_client(paths)
        paths.initialize()
        # Share the readonly bootstrap's OAuth lock rather than creating a second
        # authorization lane capable of racing other cooperating profile sessions.
        with portalocker.Lock(
            str(paths.locks / "oauth-bootstrap.lock"),
            mode="a",
            timeout=0,
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
        ):
            make_private(paths.locks / "oauth-bootstrap.lock")
            if load_client(paths) != config:
                raise _AuthorizationError("Google client changed during authorization")
            client = config["installed"]
            client_id = client["client_id"]
            target = paths.home / "google_token.json"
            original, marker = _local_file(target)
            old = _token_data(original, client)
            if not old.get("refresh_token"):
                raise _AuthorizationError("An existing verified offline token is required for modify sign-in")
            with tempfile.TemporaryDirectory(prefix=".oauth-modify-", dir=paths.root) as temporary:
                staging = Path(temporary)
                make_private(staging, directory=True)
                staged_token = staging / "google_token.json"
                # Bound refresh requests to readonly during existing-account validation;
                # malicious/unrelated requested scopes in token JSON are never forwarded.
                old["scopes"] = [READONLY]
                private_write(staged_token, json.dumps(old))
                existing = verify(staging, client_id, require_modify=False)
                if validation is not None:
                    validation.check_account(existing)
                if existing.oauth_client_id != client_id:
                    raise _AuthorizationError("Existing token belongs to another OAuth client")
                with account_lock(paths, existing.account_id):
                    check_bound_account(paths, existing)
                _assert_unchanged(target, original, marker)
                credentials = consent(config)
                if credentials is None or credentials.client_id != client_id:
                    raise _AuthorizationError("Authorization denied or returned another OAuth client")
                candidate = _token_data(credentials.to_json(), client)
                # Keep the old refresh token OUT of this first new-account check.
                candidate.setdefault("refresh_token", None)
                candidate["scopes"] = [MODIFY]
                private_write(staged_token, json.dumps(candidate))
                identity = verify(staging, client_id, require_modify=True)
                if validation is not None:
                    validation.check_account(identity)
                if identity != existing:
                    raise _AuthorizationError(
                        "Authorized account or OAuth client differs from the existing token"
                    )
                check_bound_account(paths, identity)
                if not candidate.get("refresh_token"):
                    # Safe only after the provider token proved the exact same account
                    # and client; never use the old refresh to mask a switched account.
                    candidate["refresh_token"] = old["refresh_token"]
                    private_write(staged_token, json.dumps(candidate))
                    if verify(staging, client_id, require_modify=True) != existing:
                        raise _AuthorizationError("Final staged credentials changed account identity")
                if not confirm(identity):
                    raise _AuthorizationError(
                        "Authorization cancelled locally; existing credentials retained"
                    )
                with account_lock(paths, identity.account_id):
                    check_bound_account(paths, identity)
                    if load_client(paths) != config:
                        raise _AuthorizationError("Google client changed during authorization")
                    _assert_unchanged(target, original, marker)
                    # Stage is on the same filesystem, private and fsynced. Replacement
                    # occurs only under both locks after byte AND file-identity checking.
                    os.replace(staged_token, target)
                return identity
    except _AuthorizationError:
        raise
    except (KeyboardInterrupt, EOFError):
        raise _AuthorizationError("Authorization cancelled locally; existing credentials retained") from None
    except Exception:
        raise _AuthorizationError(_FAILURE) from None


def _assert_unchanged(target, original, marker):
    current, current_marker = _local_file(target)
    if current != original or current_marker != marker:
        raise _AuthorizationError("Google token changed during authorization; concurrent token was preserved")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Optional local Gmail-modify authorization (release gated).")
    parser.add_argument("--workspace-scripts", type=Path, required=True)
    parser.add_argument(
        "--manual-browser", action="store_true", help="Show the private loopback sign-in URL locally."
    )
    parser.add_argument(
        "--check", action="store_true", help="Validate client JSON locally; no Google request or grant."
    )
    args = parser.parse_args(argv)
    try:
        if not args.check:
            _interactive()
            require_live_release()
        paths = resolve_profile(args.workspace_scripts)
        load_client(paths)
        if args.check:
            print(
                "Desktop client configuration valid. No Google request was made; no grants were checked or changed."
            )
            return 0
        authorize_modify(
            paths, consent=lambda config: browser_consent(config, manual_browser=args.manual_browser)
        )
        print("Saved private same-account Gmail-modify credentials. No messages were read or changed.")
        return 0
    except _AuthorizationError as error:
        print(terminal_safe(str(error)), file=sys.stderr)
        return 2
    except ReclaimError:
        print(
            "Live Gmail-modify consent is unavailable or profile validation failed; no credentials replaced.",
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(_FAILURE, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
