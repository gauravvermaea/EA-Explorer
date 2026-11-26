"""D932: Documents' sign-in page showed its administrator's password (owner, 26 Nov 2026, 08:26: "docs.localhost shows
the admin password"; 08:28: "go for the fix"). Mayan shows the administrator it made at first start, with its password,
until that administrator changes it, which nobody does (people sign in through Keycloak). The API now takes that notice
away each time it reads Documents' token, and the self-test's security suite fails if a password is on the page."""

import sys
import types
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax import mayan  # noqa: E402
from eax.testing import security  # noqa: E402


class _Cur:
    def __init__(self, row=None, rowcount=0):
        self.row, self.rowcount = row, rowcount

    def fetchone(self):
        return self.row


class _Conn:
    """Mayan's database as far as the token and the notice go."""
    def __init__(self, table=True, notice=1, admin=True, token="abc"):
        self.table, self.notice, self.admin, self.token, self.sql = table, notice, admin, token, []

    def execute(self, sql, params=()):
        self.sql.append(sql)
        if sql.startswith("SELECT to_regclass"):
            return _Cur(("public.autoadmin_autoadminsingleton" if self.table else None,))
        if sql.startswith("DELETE FROM public.autoadmin_autoadminsingleton"):
            n, self.notice = self.notice, 0
            return _Cur(rowcount=n)
        if "FROM auth_user" in sql:
            return _Cur((7,) if self.admin else None)
        if "FROM authtoken_token" in sql:
            return _Cur((self.token,) if self.token else None)
        return _Cur()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_notice_is_taken_away_when_it_is_there():
    c = _Conn()
    assert mayan.hide_admin_notice(c) is True and c.notice == 0
    assert mayan.hide_admin_notice(c) is False            # once gone, nothing more to do


def test_nothing_is_done_where_mayan_has_no_such_table():
    c = _Conn(table=False)
    assert mayan.hide_admin_notice(c) is False
    assert not any(s.startswith("DELETE") for s in c.sql)


def test_reading_the_token_takes_the_notice_away(monkeypatch):
    c = _Conn()
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda *a, **k: c))
    assert mayan._db_token() == "abc"
    assert c.notice == 0 and any(s.startswith("DELETE") for s in c.sql)


def test_no_administrator_yet_leaves_it_for_the_next_read(monkeypatch):
    c = _Conn(admin=False)
    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(connect=lambda *a, **k: c))
    try:
        mayan._db_token()
        raise AssertionError("expected MayanError")
    except mayan.MayanError as exc:
        assert "still setting itself up" in str(exc)
    assert c.notice == 1                                  # taken away at the next read, once the administrator is there


PW = "s3cret-Admin-pw"
LOGIN = "/authentication/login/?next=/"


def _site(login_text: str, first_where: str = LOGIN):
    def page(url, host):
        assert host.startswith("docs.")
        if url.endswith("/proxy/") or url.endswith("proxy/"):
            return 302, "", first_where
        return 200, login_text, ""
    return page


def _run(page, password=PW, on=True, monkeypatch=None):
    got = []
    from eax import services
    monkeypatch.setattr(services, "enabled", lambda k: on)
    security.documents_sign_in(lambda n, o, w, d: got.append((n, o, w)), page=page, password=password)
    return got


def test_a_password_on_the_sign_in_page_fails(monkeypatch):
    monkeypatch.setenv("EAX_TEST_PROXY", "https://proxy")
    got = _run(_site(f"<p>Username: admin</p><p>Password: {PW}</p>"), monkeypatch=monkeypatch)
    assert got[0][1] == "failed" and LOGIN.split("?")[0] in got[0][2]
    assert PW not in got[0][2]                            # the report never repeats the password


def test_no_password_passes_and_says_what_was_looked_at(monkeypatch):
    monkeypatch.setenv("EAX_TEST_PROXY", "https://proxy")
    got = _run(_site("<form>Sign in with EA Explorer</form>"), monkeypatch=monkeypatch)
    assert got == [("Documents' sign-in page shows no password", "passed", f"no password on / (302), {LOGIN} (200)")]


def test_a_redirect_off_documents_is_not_followed(monkeypatch):
    monkeypatch.setenv("EAX_TEST_PROXY", "https://proxy")
    seen = []

    def page(url, host):
        seen.append(url)
        return 302, "", "https://localhost/auth/realms/eaexplorer/protocol/openid-connect/auth"
    got = _run(page, monkeypatch=monkeypatch)
    assert len(seen) == 1 and got[0][1] == "passed"


def test_skipped_when_documents_is_off_or_the_password_unknown(monkeypatch):
    assert _run(_site(PW), on=False, monkeypatch=monkeypatch)[0][1] == "skipped"
    assert _run(_site(PW), password="", monkeypatch=monkeypatch)[0][1] == "skipped"


def test_the_security_suite_runs_it():
    src = (API / "eax/testing/run.py").read_text(encoding="utf-8")
    assert "security.documents_sign_in(rec)" in src
    compose = (API.parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
    assert "MAYAN_AUTOADMIN_PASSWORD" in compose        # Mayan still makes its administrator; only the notice goes
