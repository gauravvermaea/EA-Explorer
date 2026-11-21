"""D803: the first eax test sonar (19 Nov 2026, SonarQube Community Build 26.11) scanned fine but the report stopped with
a bare "HTTP Error 400": the report asked for issues with componentKeys and for hotspots with projectKey, both deprecated
since SonarQube 10.2. It now asks with components and project, and a refusal shows the call and SonarQube's message."""

from __future__ import annotations

import io
import json
import urllib.error

from eax.testing import sonar as S

OLD = {"componentKeys", "projectKey"}


def _sonar_26(seen: list):
    """A SonarQube that refuses the old parameter names, as 26.x does."""
    def ask(method, path, params=None, auth=None, token="", timeout=30):
        seen.append((path, dict(params or {})))
        if OLD & set(params or {}):
            body = io.BytesIO(json.dumps({"errors": [{"msg": "Unknown parameter"}]}).encode())
            raise urllib.error.HTTPError("http://sonarqube:9000" + path, 400, "", {}, body)
        if path == "/api/ce/component":
            return {"queue": [], "current": {"status": "SUCCESS"}}
        if path == "/api/issues/search":
            return {"issues": [{"rule": "python:S1192", "component": "ea-explorer:a.py", "line": 1}], "paging": {"total": 1}}
        if path == "/api/hotspots/search":
            return {"hotspots": [], "paging": {"total": 0}}
        return {}
    return ask


def _keep(tmp_path):
    keep = tmp_path / "keep"
    keep.mkdir()
    for name, text in (("token", "t"), ("token-name", "n"), ("admin", "pw"), ("version", "26.11")):
        (keep / name).write_text(text, encoding="utf-8")
    return keep


def test_the_report_asks_with_the_current_parameter_names(tmp_path):
    seen: list = []
    S.report("sonar-x", ask=_sonar_26(seen), keep=_keep(tmp_path), results=tmp_path / "results")
    searches = {p: q for p, q in seen if p.endswith("/search")}
    assert searches["/api/issues/search"]["components"] == S.PROJECT
    assert searches["/api/hotspots/search"]["project"] == S.PROJECT
    assert not any(OLD & set(q) for _p, q in seen)
    assert json.loads((tmp_path / "results/sonar-x/issues.json").read_text(encoding="utf-8"))[0]["rule"] == "python:S1192"


def test_the_old_names_are_what_a_new_sonarqube_refuses():
    """Before: the old call is refused (the 400 seen on the laptop)."""
    ask = _sonar_26([])
    try:
        ask("GET", "/api/issues/search", {"componentKeys": S.PROJECT})
    except urllib.error.HTTPError as exc:
        assert exc.code == 400
    else:
        raise AssertionError("the stand-in should refuse componentKeys")


def test_a_refusal_says_which_call_and_why():
    exc = urllib.error.HTTPError("http://sonarqube:9000/api/issues/search?components=ea-explorer&ps=500", 400, "", {},
                                 io.BytesIO(b'{"errors":[{"msg":"Can return only the first 10000 results"}]}'))
    said = S.refused(exc)
    assert "/api/issues/search" in said and "400" in said and "first 10000" in said
    assert "components=" not in said      # the address only, never its query (no token or key there either)


def test_main_prints_the_refusal_not_a_bare_400(monkeypatch, capsys):
    def boom(folder):
        raise urllib.error.HTTPError("http://sonarqube:9000/api/hotspots/search", 400, "", {},
                                     io.BytesIO(b'{"errors":[{"msg":"bad project"}]}'))
    monkeypatch.setattr(S, "report", boom)
    assert S.main(["report", "sonar-x"]) == 2
    out = capsys.readouterr().out
    assert "SonarQube refused /api/hotspots/search with 400: bad project" in out
