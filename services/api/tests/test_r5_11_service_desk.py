"""R5.11 (owner, 14 Nov 2026: "a Jiraike ticket interface for users of the system to Request things like creating models
etc"; 15 Nov 2026, D692: the catalogue as proposed, editable, "add more defaults as needed")."""

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import permissions as P  # noqa: E402
from eax import servicedesk as sd  # noqa: E402

SQL = (REPO / "services/api/migrations/sql/0082_r5_service_desk.sql").read_text()


def seeded() -> list[dict]:
    rows = re.findall(r"\('([a-z-]+)', '([A-Za-z]+)', '((?:[^']|'')*)', '(?:[^']|'')*', '(\[.*?\])', '([a-z-]+)', '([a-z-]*)', (\d+), '([^']*)', (\d+)\)", SQL)
    return [{"key": k, "area": a, "name": n, "form": json.loads(f.replace("''", "'")), "team": t, "approval": ap,
             "target_hours": int(h), "wizard": w} for k, a, n, f, t, ap, h, w, _s in rows]


def test_the_catalogue_as_proposed_with_more_defaults():
    types = seeded()
    keys = {t["key"] for t in types}
    proposed = {"new-model", "copy-model", "model-access", "metamodel-change", "data-load", "restore-model", "archive-model",
                "new-project", "project-access", "project-template", "restore-project", "new-report", "report-change",
                "new-user", "global-role", "machine-credential", "ip-allow", "question", "problem", "other"}
    assert proposed <= keys and len(keys) > len(proposed)                         # "add more defaults as needed"
    assert {t["area"] for t in types} == {"Models", "Projects", "Reports", "Access", "Help"}
    for t in types:
        sd.clean_type(t)                                                           # every default is a valid type
        assert t["team"] in sd.TEAMS and (not t["approval"] or t["approval"] in sd.TEAMS)


def test_a_request_type_is_checked():
    with pytest.raises(sd.DeskError, match="key"):
        sd.clean_type({"name": "x"})
    # R5.27: every type goes to the Super Admins with no approval, whatever is sent
    t = sd.clean_type({"key": "x", "name": "x", "team": "it-admin", "approval": "model-admins"})
    assert t["team"] == P.SUPER_ADMIN and t["approval"] == ""
    with pytest.raises(sd.DeskError, match="kind"):
        sd.clean_type({"key": "x", "name": "x", "form": [{"name": "a", "kind": "rocket"}]})
    t = sd.clean_type({"key": "Odd Key!", "name": "X", "form": [{"name": "Why Now", "kind": "textarea", "required": True}]})
    assert t["key"] == "odd-key" and t["form"][0]["name"] == "why_now" and t["approval"] == ""


def test_a_request_s_fields_are_checked_against_its_form():
    ty = {"form": [{"name": "model", "label": "Model", "kind": "model", "required": True},
                   {"name": "role", "label": "Role", "kind": "model-role", "required": True},
                   {"name": "size", "label": "Size", "kind": "choice", "required": False, "choices": ["s", "m"]}]}
    with pytest.raises(sd.DeskError, match="Role"):
        sd.check_fields(None, ty, {"model": "m1"})
    with pytest.raises(sd.DeskError, match="one of"):
        sd.check_fields(None, ty, {"model": "m1", "role": "king"})
    with pytest.raises(sd.DeskError, match="Size"):
        sd.check_fields(None, ty, {"model": "m1", "role": "architect", "size": "xl"})
    assert sd.check_fields(None, ty, {"model": "m1", "role": "architect", "extra": "dropped"}) == {"model": "m1", "role": "architect"}


def test_teams_and_who_works_on_what():
    assert sd.in_team(None, P.IT_ADMIN, "ann", [P.IT_ADMIN], {}) and not sd.in_team(None, P.IT_ADMIN, "ann", [P.USER], {})
    assert sd.in_team(None, "model-admins", "boss", [P.SUPER_ADMIN], {})          # Super Admins work on everything
    assert set(sd.STATUSES) >= {"new", "waiting-approval", "approved", "in-progress", "waiting-requester", "done", "declined", "cancelled"}


def test_wired_in_api_jobs_screens_and_every_form_of_eax():
    assert "servicedesk_blp" in (REPO / "services/api/eax/app.py").read_text()
    assert 'name="eax.servicedesk_overdue"' in (REPO / "services/api/eax/jobs.py").read_text()
    api = (REPO / "services/api/eax/api/servicedesk.py").read_text()
    for r in ('"/catalogue"', '"/tickets"', '"/tickets/<string:ident>"', "approve", "do", '"/stats"'):
        assert r in api
    assert "|ticket|" in (REPO / "eax.sh").read_text() and '"db", "ticket",' in (REPO / "eax.ps1").read_text()
    assert "### ticket " in (REPO / "eaxcli/help.txt").read_text()
    assert '#/service-desk' in (REPO / "services/web/src/App.jsx").read_text()
    assert "CREATE FUNCTION" not in SQL and "TRIGGER" not in SQL                     # D248
