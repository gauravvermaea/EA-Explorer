"""D934: run 17 left its three Keycloak test users behind ("the Keycloak test user super-admin was not deleted"): the
master realm's admin sign-in lasts about a minute, and the users are removed after the reports, twenty minutes on. A
call Keycloak refuses with 401 now signs in again, once, and is made again."""

import io
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_reports_check import FakeKeycloak  # noqa: E402

from eax.testing.reports_check import Keycloak, _remove  # noqa: E402


class _RunsOut(FakeKeycloak):
    """Keycloak whose first token has run out by the time of the first delete."""

    def __init__(self, refuse=1):
        super().__init__()
        self.tokens, self.refuse = 0, refuse

    def __call__(self, req, timeout=0):
        if req.full_url.endswith("/openid-connect/token"):
            self.tokens += 1
        if req.get_method() == "DELETE" and self.refuse:
            self.refuse -= 1
            self.calls.append(("DELETE", req.full_url.split("/auth", 1)[1]))
            raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, io.BytesIO(json.dumps({}).encode()))
        return super().__call__(req, timeout)


def test_a_run_out_sign_in_is_made_again_and_the_user_deleted():
    fake = _RunsOut()
    kc = Keycloak("http://keycloak:8080/auth", "eaexplorer", "kcadmin", "pw", opener=fake)
    kc.sign_in()
    said = []
    _remove(kc, {"super-admin": "id-1", "report-viewer": "id-2"}, said.append)
    assert said == []                                             # nothing left behind
    assert fake.tokens == 2                                       # signed in again once, not for every user
    assert [c for c in fake.calls if c[0] == "DELETE"].count(("DELETE", "/admin/realms/eaexplorer/users/id-1")) == 2


def test_a_second_refusal_is_reported_not_retried_for_ever():
    fake = _RunsOut(refuse=2)
    kc = Keycloak("http://k/auth", "r", "u", "p", opener=fake)
    kc.sign_in()
    said = []
    _remove(kc, {"it-admin": "id-3"}, said.append)
    assert said == ["reports: the Keycloak test user it-admin was not deleted"] and fake.tokens == 2


def test_signing_in_itself_is_never_retried():
    kc = Keycloak("http://k/auth", "r", "u", "p", opener=FakeKeycloak(token_status=401))
    try:
        kc.sign_in()
        raise AssertionError("expected a refusal")
    except RuntimeError as exc:
        assert "could not sign in (401)" in str(exc)
