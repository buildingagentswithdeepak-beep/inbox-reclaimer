"""First-time OAuth bootstrap safeguards; no browser or Google traffic in these tests."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from inbox_reclaimer import authorization as auth
from inbox_reclaimer.models import Identity, ReclaimError
from inbox_reclaimer.profile import ProfilePaths
from inbox_reclaimer.storage import JournalStore

CLIENT = "fixture.apps.googleusercontent.com"
OWNER = Identity("owner@example.test", CLIENT)


@pytest.fixture
def setup(tmp_path):
    paths = ProfilePaths(tmp_path)
    config = {
        "installed": {
            "client_id": CLIENT,
            "client_secret": "FAKE-CLIENT-SECRET",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    (tmp_path / "google_client_secret.json").write_text(json.dumps(config))
    credentials = SimpleNamespace(
        client_id=CLIENT,
        refresh_token="FAKE-REFRESH",
        to_json=lambda: json.dumps({"client_id": CLIENT, "refresh_token": "FAKE-REFRESH"}),
    )
    consent = Mock(return_value=credentials)
    verify = Mock(return_value=OWNER)
    confirm = Mock(return_value=True)
    return paths, consent, verify, confirm


def run(setup):
    paths, consent, verify, confirm = setup
    return auth.authorize(paths, consent=consent, verify=verify, confirm=confirm)


def test_success_confirms_verified_account_before_exclusive_adoption(setup):
    paths, consent, verify, confirm = setup

    def confirmation(identity):
        assert identity == OWNER
        assert not (paths.home / "google_token.json").exists()
        return True

    confirm.side_effect = confirmation
    assert run(setup) == OWNER
    assert json.loads((paths.home / "google_token.json").read_text())["client_id"] == CLIENT
    verify.assert_called_once()
    assert not list(paths.root.glob(".oauth-*"))
    assert not paths.journal.exists()  # Sign-in is not plan approval or journal creation.


def test_existing_token_never_read_replaced_or_reauthorized(setup):
    paths, consent, *_ = setup
    target = paths.home / "google_token.json"
    target.write_text("existing-token-preserved")
    with pytest.raises(ReclaimError, match="already exists"):
        run(setup)
    consent.assert_not_called()
    assert target.read_text() == "existing-token-preserved"


@pytest.mark.parametrize("where", ["consent", "verify", "confirm"])
def test_errors_clean_staging_and_never_disclose_secrets(setup, where):
    paths, consent, verify, confirm = setup
    {"consent": consent, "verify": verify, "confirm": confirm}[where].side_effect = RuntimeError(
        "SECRET-CODE"
    )
    with pytest.raises(ReclaimError) as caught:
        run(setup)
    assert "SECRET-CODE" not in str(caught.value)
    assert not (paths.home / "google_token.json").exists()
    assert not list(paths.root.glob(".oauth-*"))


def test_user_rejection_does_not_store_credentials(setup):
    setup[3].return_value = False
    with pytest.raises(ReclaimError, match="cancelled"):
        run(setup)
    assert not (setup[0].home / "google_token.json").exists()


def test_racing_token_creation_cannot_be_overwritten(setup):
    paths, _, _, confirm = setup

    def race(_):
        (paths.home / "google_token.json").write_text("another-session-token")
        return True

    confirm.side_effect = race
    with pytest.raises(ReclaimError):
        run(setup)
    assert (paths.home / "google_token.json").read_text() == "another-session-token"


def test_existing_journal_account_cannot_switch(setup):
    paths, *_ = setup
    paths.initialize()
    with JournalStore(paths.journal) as journal:
        journal.bind_account(Identity("different@example.test", CLIENT))
    with pytest.raises(ReclaimError, match="account"):
        run(setup)
    assert not (paths.home / "google_token.json").exists()


def test_unknown_client_or_missing_refresh_token_fails(setup):
    setup[1].return_value.refresh_token = None
    with pytest.raises(ReclaimError):
        run(setup)
    setup[1].return_value.refresh_token = "FAKE"
    setup[2].return_value = Identity(OWNER.email, "different-client")
    with pytest.raises(ReclaimError):
        run(setup)
    assert not (setup[0].home / "google_token.json").exists()


@pytest.mark.parametrize(
    "field,value",
    [("auth_uri", "https://attacker.invalid/auth"), ("token_uri", "https://attacker.invalid/token")],
)
def test_non_google_endpoints_rejected_before_consent(setup, field, value):
    path = setup[0].home / "google_client_secret.json"
    data = json.loads(path.read_text())
    data["installed"][field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ReclaimError):
        run(setup)
    setup[1].assert_not_called()


def test_verified_scope_must_be_exactly_readonly(tmp_path, monkeypatch):
    adapter = Mock()
    adapter.resolve_identity.return_value = OWNER
    monkeypatch.setattr("inbox_reclaimer.gmail.GoogleReadAdapter", Mock(return_value=adapter))
    for scopes in ({auth.READONLY, "https://www.googleapis.com/auth/gmail.modify"}, set()):
        adapter._grants = scopes
        with pytest.raises(ReclaimError):
            auth.verify_staged(tmp_path, CLIENT)
    adapter._grants = {auth.READONLY}
    assert auth.verify_staged(tmp_path, CLIENT) == OWNER


def test_browser_contract_loopback_pkce_timeout_no_url_printing(monkeypatch):
    pytest.importorskip("google_auth_oauthlib.flow")
    flow = Mock()
    factory = Mock(return_value=flow)
    monkeypatch.setattr("google_auth_oauthlib.flow.InstalledAppFlow.from_client_config", factory)
    auth.browser_consent({"installed": {}})
    assert factory.call_args.args[1] == [auth.READONLY]
    assert factory.call_args.kwargs["autogenerate_code_verifier"] is True
    options = flow.run_local_server.call_args.kwargs
    assert options["host"] == options["bind_addr"] == "127.0.0.1"
    assert options["port"] == 0 and options["timeout_seconds"] == 300
    assert options["authorization_prompt_message"] == ""
    assert options["include_granted_scopes"] == "false"


def test_manual_browser_preserves_oauth_security_without_automatic_launch(monkeypatch):
    pytest.importorskip("google_auth_oauthlib.flow")
    flow = Mock()
    factory = Mock(return_value=flow)
    monkeypatch.setattr("google_auth_oauthlib.flow.InstalledAppFlow.from_client_config", factory)
    auth.browser_consent({"installed": {}}, manual_browser=True)
    options = flow.run_local_server.call_args.kwargs
    assert options["open_browser"] is False
    assert "{url}" in options["authorization_prompt_message"]
    assert "Do not share" in options["authorization_prompt_message"]
    assert options["host"] == options["bind_addr"] == "127.0.0.1"
    assert options["timeout_seconds"] == 300
    assert factory.call_args.args[1] == [auth.READONLY]
    assert factory.call_args.kwargs["autogenerate_code_verifier"] is True
    flow.oauth2session.close.assert_called_once()


@pytest.mark.parametrize("extra", [[], ["--manual-browser"]])
def test_noninteractive_login_refused_without_reading_profile(monkeypatch, extra):
    monkeypatch.setattr(auth.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(auth, "resolve_profile", lambda *_: pytest.fail("Profile accessed"))
    assert auth.main(["--workspace-scripts", "unused", *extra]) == 2
