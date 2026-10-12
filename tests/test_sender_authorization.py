"""Synthetic profiles and injected consent/verification: never real Google access."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inbox_reclaimer.models import GateClosed, Identity, ReclaimError
from inbox_reclaimer.profile import ProfilePaths
from inbox_reclaimer.sender import authorization as auth
from inbox_reclaimer.storage import JournalStore

CLIENT = "fixture.apps.googleusercontent.com"
OWNER = Identity("owner@example.test", CLIENT)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "require_live_release", lambda: None)
    paths = ProfilePaths(tmp_path)
    config = {
        "installed": {
            "client_id": CLIENT,
            "client_secret": "FAKE-CLIENT",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    (tmp_path / "google_client_secret.json").write_text(json.dumps(config))
    old = {
        "client_id": CLIENT,
        "client_secret": "FAKE-CLIENT",
        "refresh_token": "OLD-FAKE",
        "token": "OLD-ACCESS",
        "scopes": [auth.READONLY],
    }
    (tmp_path / "google_token.json").write_bytes(json.dumps(old, indent=3).encode())
    new = {
        "client_id": CLIENT,
        "client_secret": "FAKE-CLIENT",
        "refresh_token": "NEW-FAKE",
        "token": "NEW-ACCESS",
        "scopes": [auth.MODIFY],
    }
    credentials = SimpleNamespace(client_id=CLIENT, to_json=lambda: json.dumps(new))
    consent, verify, confirm = (
        Mock(return_value=credentials),
        Mock(return_value=OWNER),
        Mock(return_value=True),
    )
    return paths, consent, verify, confirm, new


def run(setup):
    paths, consent, verify, confirm, _ = setup
    return auth.authorize_modify(paths, consent=consent, verify=verify, confirm=confirm)


def token(setup):
    return setup[0].home / "google_token.json"


def test_real_gate_before_any_profile_or_credentials_access(monkeypatch):
    monkeypatch.setattr(
        "inbox_reclaimer.sender.models.release_status", lambda: {"live_mutation_released": False}
    )

    class NoAccess:
        def __getattribute__(self, name):
            pytest.fail("profile accessed before live release gate")

    with pytest.raises(GateClosed):
        auth.authorize_modify(NoAccess())


def test_original_preserved_until_same_account_confirmation_and_atomic_commit(setup):
    original = token(setup).read_bytes()

    def confirm(identity):
        assert identity == OWNER and token(setup).read_bytes() == original
        return True

    setup[3].side_effect = confirm
    assert run(setup) == OWNER
    assert json.loads(token(setup).read_text())["token"] == "NEW-ACCESS"
    assert setup[2].call_args_list[0].kwargs == {"require_modify": False}
    assert setup[2].call_count >= 2
    assert not list(setup[0].root.glob(".oauth-modify-*"))
    assert not setup[0].journal.exists()


@pytest.mark.parametrize("where", ["consent", "verify", "confirm"])
def test_denial_and_errors_never_replace_or_disclose(setup, where):
    original = token(setup).read_bytes()
    callback = dict(consent=setup[1], verify=setup[2], confirm=setup[3])[where]
    callback.side_effect = RuntimeError("SECRET URL token")
    with pytest.raises(ReclaimError) as error:
        run(setup)
    assert "SECRET" not in str(error.value)
    assert token(setup).read_bytes() == original
    assert not list(setup[0].root.glob(".oauth-modify-*"))


def test_false_local_confirmation_preserves_exact_bytes(setup):
    original = token(setup).read_bytes()
    setup[3].return_value = False
    with pytest.raises(ReclaimError):
        run(setup)
    assert token(setup).read_bytes() == original


@pytest.mark.parametrize("field", ["auth_uri", "token_uri", "client_id"])
def test_injected_endpoint_or_client_fails_before_consent(setup, field):
    original = token(setup).read_bytes()
    path = setup[0].home / "google_client_secret.json"
    data = json.loads(path.read_text())
    data["installed"][field] = "https://attacker.invalid/SECRET"
    path.write_text(json.dumps(data))
    with pytest.raises(ReclaimError):
        run(setup)
    setup[1].assert_not_called()
    assert token(setup).read_bytes() == original


def test_missing_client_does_not_fallback_or_invoke_consent(setup):
    (setup[0].home / "google_client_secret.json").unlink()
    with pytest.raises(ReclaimError):
        run(setup)
    setup[1].assert_not_called()


def test_journal_binding_checked_before_consent(setup):
    paths = setup[0]
    paths.initialize()
    with JournalStore(paths.journal) as journal:
        journal.bind_account(Identity("other@example.test", CLIENT))
    with pytest.raises(ReclaimError):
        run(setup)
    setup[1].assert_not_called()


@pytest.mark.parametrize(
    "identity", [Identity("other@example.test", CLIENT), Identity(OWNER.email, "other-client")]
)
def test_account_and_client_switch_refused(setup, identity):
    original = token(setup).read_bytes()
    setup[2].side_effect = [OWNER, identity]
    with pytest.raises(ReclaimError):
        run(setup)
    assert token(setup).read_bytes() == original
    setup[3].assert_not_called()


def test_changed_token_race_is_preserved(setup):
    def confirm(_):
        token(setup).write_bytes(b"concurrent replacement")
        return True

    setup[3].side_effect = confirm
    with pytest.raises(ReclaimError):
        run(setup)
    assert token(setup).read_bytes() == b"concurrent replacement"


def test_missing_refresh_token_retained_only_after_same_account_verified(setup):
    setup[4].pop("refresh_token")
    observed = []

    def verify(directory, client, *, require_modify=True):
        data = json.loads((directory / "google_token.json").read_text())
        observed.append(data.get("refresh_token"))
        return OWNER

    setup[2].side_effect = verify
    run(setup)
    assert observed[:2] == ["OLD-FAKE", None]
    assert json.loads(token(setup).read_text())["refresh_token"] == "OLD-FAKE"


@pytest.mark.parametrize(
    "grants",
    [
        {auth.READONLY},
        set(),
        {auth.MODIFY, "https://mail.google.com/"},
        {auth.MODIFY, "https://www.googleapis.com/auth/drive"},
    ],
)
def test_actual_modify_grants_must_be_narrow(tmp_path, monkeypatch, grants):
    adapter = Mock()
    adapter.resolve_identity.return_value = OWNER
    adapter._grants = grants
    monkeypatch.setattr("inbox_reclaimer.gmail.GoogleReadAdapter", Mock(return_value=adapter))
    with pytest.raises(ReclaimError):
        auth.verify_staged(tmp_path, CLIENT)


@pytest.mark.parametrize("grants", [{auth.MODIFY}, {auth.MODIFY, auth.READONLY}])
def test_actual_modify_and_optional_readonly_grants_accepted(tmp_path, monkeypatch, grants):
    adapter = Mock()
    adapter.resolve_identity.return_value = OWNER
    adapter._grants = grants
    monkeypatch.setattr("inbox_reclaimer.gmail.GoogleReadAdapter", Mock(return_value=adapter))
    assert auth.verify_staged(tmp_path, CLIENT) == OWNER


@pytest.mark.parametrize("manual", [True, False])
def test_pkce_loopback_only_modify_and_manual_browser_security(setup, monkeypatch, manual, capsys):
    pytest.importorskip("google_auth_oauthlib.flow")
    monkeypatch.setattr(auth.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(auth.sys.stdout, "isatty", lambda: True)
    flow, factory = Mock(), Mock()
    factory.return_value = flow
    monkeypatch.setattr("google_auth_oauthlib.flow.InstalledAppFlow.from_client_config", factory)
    auth.browser_consent({"installed": {}}, manual_browser=manual)
    assert "also permits sending" in capsys.readouterr().out
    assert factory.call_args.args[1] == [auth.MODIFY]
    assert factory.call_args.kwargs["autogenerate_code_verifier"] is True
    options = flow.run_local_server.call_args.kwargs
    assert options["host"] == options["bind_addr"] == "127.0.0.1"
    assert options["port"] == 0 and options["timeout_seconds"] == 300
    assert options["include_granted_scopes"] == "false"
    assert options["open_browser"] is not manual
    assert ("{url}" in options["authorization_prompt_message"]) is manual
    flow.oauth2session.close.assert_called_once()


def test_check_no_network_no_consent_no_grant(setup, monkeypatch, capsys):
    monkeypatch.setattr(auth, "resolve_profile", lambda _: setup[0])
    monkeypatch.setattr(auth, "authorize_modify", lambda *a, **kw: pytest.fail("consent on check"))
    monkeypatch.setattr(auth, "require_live_release", lambda: pytest.fail("live gate on check"))
    monkeypatch.setattr("requests.sessions.Session.request", lambda *a, **kw: pytest.fail("network"))
    original = token(setup).read_bytes()
    assert auth.main(["--workspace-scripts", "fixture", "--check"]) == 0
    assert token(setup).read_bytes() == original
    assert "No Google request" in capsys.readouterr().out


def test_noninteractive_real_consent_refused_before_profile(monkeypatch):
    monkeypatch.setattr(auth.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(auth, "resolve_profile", lambda _: pytest.fail("profile accessed"))
    assert auth.main(["--workspace-scripts", "fixture"]) == 2


def test_cli_redacts_untrusted_errors(setup, monkeypatch, capsys):
    monkeypatch.setattr(auth.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(auth.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(auth, "resolve_profile", lambda _: setup[0])
    monkeypatch.setattr(auth, "authorize_modify", Mock(side_effect=RuntimeError("SECRET")))
    assert auth.main(["--workspace-scripts", "fixture"]) == 2
    output = capsys.readouterr()
    assert "SECRET" not in output.out + output.err
