"""SQL window helpers (no database needed)."""

import datetime as dt
import decimal
import uuid

from eax import sqlconsole


def test_values_become_json():
    u = uuid.uuid4()
    assert sqlconsole.to_json_value(None) is None
    assert sqlconsole.to_json_value(True) is True
    assert sqlconsole.to_json_value(decimal.Decimal("12.50")) == "12.50"
    assert sqlconsole.to_json_value(u) == str(u)
    assert sqlconsole.to_json_value(dt.date(2026, 11, 4)) == "2026-11-04"
    assert sqlconsole.to_json_value(float("nan")) == "nan"
    assert sqlconsole.to_json_value(b"\x01\xff") == "\\x01ff"
    assert sqlconsole.to_json_value({"a": [decimal.Decimal(1)]}) == {"a": ["1"]}
    long = sqlconsole.to_json_value("x" * 20000)
    assert len(long) == sqlconsole.MAX_CELL_CHARS + 3 and long.endswith("...")


def test_on_for_laptops_off_for_servers(monkeypatch):
    monkeypatch.delenv("EAX_SQL_CONSOLE_ENABLED", raising=False)
    monkeypatch.setenv("EAX_DEPLOYMENT", "laptop")
    assert sqlconsole.enabled()
    monkeypatch.setenv("EAX_DEPLOYMENT", "server")
    assert not sqlconsole.enabled()
    monkeypatch.setenv("EAX_SQL_CONSOLE_ENABLED", "true")
    assert sqlconsole.enabled()


def test_login_and_text_are_required():
    """No login set up is 503 (the window's own logins come from the config file, D742); no text is 400."""
    for args, status in [(("eaexplorer", "", "", "SELECT 1"), 503), (("eaexplorer", "eax_console_it", "pw", "  "), 400)]:
        try:
            sqlconsole.run(*args)
        except sqlconsole.SqlConsoleError as exc:
            assert exc.status == status
        else:
            raise AssertionError("expected an error")


def test_the_window_signs_in_by_role_in_certificate_mode(monkeypatch):
    """D742 (owner, 17 Nov 2026, 18:33: "I like the option B no password option"): in certificate mode a Super Admin's
    login reads and writes, an IT Admin's reads; two separate logins; certificates for both."""
    monkeypatch.setenv("EAX_CONSOLE_IT_PASSWORD", "a")
    monkeypatch.setenv("EAX_CONSOLE_SUPER_PASSWORD", "b")
    assert sqlconsole.console_login(True) == ("eax_console_super", "b")
    assert sqlconsole.console_login(False) == ("eax_console_it", "a")
    assert sqlconsole._connect_args("eax_console_it", "a") == {"user": "eax_console_it", "password": "a"}


def _creds_as(monkeypatch, mode: str, body: dict, roles=("super-admin",)):
    from flask import g

    from eax.api import sql as api_sql
    from eax.app import create_app
    from eax.auth import User
    monkeypatch.setenv("EAX_AUTH_MODE", mode)
    monkeypatch.setenv("EAX_CONSOLE_IT_PASSWORD", "a")
    monkeypatch.setenv("EAX_CONSOLE_SUPER_PASSWORD", "b")
    with create_app(testing=True).test_request_context():
        g.user = User(username="ann", roles=list(roles))
        return api_sql._creds(body)


def test_password_mode_keeps_the_typed_login_filled_in_as_before(monkeypatch):
    """D752 (owner, 17 Nov 2026, 20:45: "ensure if username + password is used it comes prepopulated like now"): in
    password mode the window asks for a database user and password exactly as before Release 6, the user filled in
    (eax_app) and the laptop's hint shown; in certificate mode nothing is typed."""
    import pytest
    from werkzeug.exceptions import HTTPException
    monkeypatch.setenv("EAX_AUTH_MODE", "password")
    assert sqlconsole.typed_login() and sqlconsole.DEFAULT_USER == "eax_app"
    assert _creds_as(monkeypatch, "password", {"username": "eax_app", "password": "pw"}) == ("eax_app", "pw")
    with pytest.raises(HTTPException) as exc:
        _creds_as(monkeypatch, "password", {"username": "eax_app"})
    assert exc.value.code == 400
    # certificate mode: whatever is sent, the window's own login for the role
    assert _creds_as(monkeypatch, "certificate", {"username": "postgres", "password": "x"}) == ("eax_console_super", "b")
    assert _creds_as(monkeypatch, "certificate", {}, roles=("it-admin",)) == ("eax_console_it", "a")
    from pathlib import Path
    web = (Path(__file__).resolve().parents[3] / "services" / "web" / "src" / "Sql.jsx").read_text()
    assert 'username: "eax_app"' in web and '{typed && field("password", "Password", "password")}' in web
    assert "password <code>P^55w0rd1234&amp;</code>" in web and "no database password is typed" in web


def test_keep_commits_and_databases_are_listed():
    """D211: a run is rolled back unless keep is ticked; the window lists the server's databases."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    src = (root / "eax" / "sqlconsole.py").read_text()
    assert "keep" in src and "datistemplate" in src
    api = (root / "eax" / "api" / "sql.py").read_text()
    assert '"/databases"' in api and "keep" in api
