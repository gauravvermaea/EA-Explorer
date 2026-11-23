"""23 Nov 2026, the owner's laptop in certificate mode: "Industry packs ... waiting for Documents to answer" never ended.
The API reads Documents' own API token from Documents' database as the login mayan (eax/mayan.py _db_token); in
certificate mode the database takes only certificates, and the API's certificate could not be mayan, so every call to
Documents was refused and looked like a slow start (D893). Now the API's certificate may be mayan, and the start-up
status says what Documents answered."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from eax import certs as C
from eax import industry_packs as IP
from eax import mayan

REPO = Path(__file__).resolve().parents[3]


def test_the_api_certificate_may_read_documents_token():
    assert "mayan" in C.CLIENTS["api"]["logins"]
    ident = (REPO / "deploy/postgres/certificate/pg_ident.conf").read_text()
    assert re.search(r"^eax\s+api\s+mayan\b", ident, re.M)
    assert "user={os.environ.get('EAX_MAYAN_DB_USER', 'mayan')}" in inspect.getsource(mayan._db_token)   # the login it uses


def test_the_status_says_why_documents_does_not_answer(monkeypatch):
    def refused(*_a, **_k):
        raise mayan.MayanError("Documents (Mayan) cannot be reached yet: certificate authentication failed for user \"mayan\"")
    monkeypatch.setattr(mayan, "_json", refused)
    assert "certificate authentication failed" in mayan.why_not_up() and mayan.ping() is False
    monkeypatch.setattr(mayan, "_json", lambda *_a, **_k: {"results": []})
    assert mayan.why_not_up() == "" and mayan.ping() is True
    assert "waiting for Documents to answer ({why[:300]})" in inspect.getsource(IP.load_shipped_each)
