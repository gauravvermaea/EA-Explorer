"""R5.1 (owner, 14 Nov 2026: "measure the platform and suggest optimizations to the user in a report"; 15 Nov 2026,
D697: unused "not opened of changed in last 180 days ... configurable"; history before a tag "Ask what to do"; nothing
applied without a yes; screen + Excel; "all suggestions are for the entire model/project")."""

import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import optimise as O  # noqa: E402
from eax import settings as st  # noqa: E402


def test_unused_is_a_setting_of_180_days():
    assert st.default_of("optimise_unused_days") == 180
    assert st.REGISTRY["optimise_unused_days"][0] == "system"


def test_a_model_changed_lately_is_not_unused_and_each_suggestion_is_a_whole_model_or_project(monkeypatch):
    from eax import mcp_operations
    monkeypatch.setattr(O, "model_people", lambda conn, m: {"created by": "ann", "Model Admins": ["bob"]})
    monkeypatch.setattr(O, "project_people", lambda p: {"created by": "cy", "Project Admins": ["dee"]})
    monkeypatch.setattr(mcp_operations, "unused", lambda conn, days: {"since": "2026-05-19", "models": [
        {"id": "m1", "name": "Old", "last_used": "2026-01-01", "last_changed": "2026-02-01", "entities": 5, "blocking": []},
        {"id": "m2", "name": "Edited", "last_used": None, "last_changed": "2026-10-01", "entities": 5, "blocking": []},
        {"id": "m3", "name": "Held", "last_used": None, "last_changed": None, "entities": 1, "blocking": ["a project uses it"]}],
        "projects": [{"id": "p1", "name": "Done project", "status": "closed", "last_changed": "2025-01-01"}]})
    out = O.unused(None, 180)
    assert [s["key"] for s in out] == ["model-m1", "model-m3", "project-p1"]          # m2 was changed: still in use
    assert out[0]["apply"] == "archive-model" and out[0]["params"] == {"model": "m1", "name": "Old"}
    assert out[1]["apply"] == "" and "cannot move" in out[1]["evidence"]                # blocked: said, not offered
    assert out[2]["apply"] == "archive-project" and all(s["undo"] for s in out)
    # owner, 15 Nov 2026: "5.1 report should have names of Admins, creators etc"
    assert out[0]["people"]["Model Admins"] == ["bob"] and out[2]["people"]["Project Admins"] == ["dee"]
    assert O.people_text(out[0]["people"]) == "created by: ann; Model Admins: bob"


def test_history_is_asked_condense_or_remove_by_the_model_admin(monkeypatch):
    rep = {"suggestions": [O.suggestion("history", "history-m1", "x", "y", apply="history",
                                        params={"model": "m1", "name": "M", "tag_at": "2026-06-01T00:00:00+00:00"},
                                        who="model-admins", choices=["condense", "remove"])]}

    class Conn:
        def execute(self, *a, **k):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: {"report": rep, "applied": {}}))

    user = SimpleNamespace(username="ann", roles=["architect"])
    with pytest.raises(ValueError, match="condense or remove"):
        O.apply(Conn(), user, 1, "history-m1")                                         # never chosen for them
    monkeypatch.setattr(O, "_model_admin", lambda *a: False)
    with pytest.raises(O.NotAllowed, match="Model Admin"):
        O.apply(Conn(), user, 1, "history-m1", "remove")


def test_the_others_are_a_super_admins_yes():
    rep = {"suggestions": [O.suggestion("disk", "docker-cache", "x", "y", apply="docker-prune")]}

    class Conn:
        def execute(self, *a, **k):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: {"report": rep, "applied": {}}))

    with pytest.raises(O.NotAllowed):
        O.apply(Conn(), SimpleNamespace(username="it", roles=["it-admin"]), 1, "docker-cache")


def test_compared_with_the_one_before():
    a = {"suggestions": [{"key": "x"}, {"key": "y"}]}
    b = {"suggestions": [{"key": "y"}, {"key": "z"}, {"key": "w"}]}
    assert O.compare(a, b) == {"new": 1, "gone": 2, "same": 1}
    assert O.compare(a, None)["new"] == 2


def test_the_report_as_excel():
    from openpyxl import load_workbook
    rep = {"at": "2026-12-01T02:30:00+00:00", "suggestions": [O.suggestion("disk", "k", "Clear the cache", "3 GB", "3 GB",
                                                                            people={"created by": "eve", "Model Admins": ["fay", "gus"]})]}
    wb = load_workbook(io.BytesIO(O.workbook(rep, {"k": {"by": "ann", "at": "2026-12-02"}})))
    ws = wb["Suggestions"]
    assert ws["A3"].value == "Area" and ws["B4"].value == "Clear the cache" and ws["H4"].value.startswith("ann")
    assert ws["I3"].value == "Created by and admins" and ws["I4"].value == "created by: eve; Model Admins: fay, gus"


def test_history_trim_keeps_the_tag_and_the_guard():
    src = (REPO / "services/api/eax/optimise.py").read_text()
    body = src.split("def trim_history(")[1].split("\ndef ")[0]
    assert "changed_at < :cut" in body and "ENABLE TRIGGER row_versions_no_change" in body and "did not come back on" in body
    assert "_pins(conn)" in body                                                       # tags, baselines, evidence (D445)


def test_it_runs_monthly_on_the_web_and_on_the_command_line():
    jobs = (REPO / "services/api/eax/jobs.py").read_text()
    assert 'name="eax.optimise_report"' in jobs and '@app.periodic(cron="30 2 1 * *")' in jobs
    admin = (REPO / "services/api/eax/api/admin.py").read_text()
    for route in ('"/admin/optimisation"', '"/admin/optimisation/<int:report_id>/apply"', '"/admin/optimisation/<int:report_id>/xlsx"'):
        assert route in admin
    assert '"python", "-m", "eax.optimise"' in (REPO / "eaxcli/optimise_cli.py").read_text()
    assert "|optimise|" in (REPO / "eax.sh").read_text() and '"jobs", "optimise"' in (REPO / "eax.ps1").read_text()   # jobs (R5.30)
    assert "### optimise " in (REPO / "eaxcli/help.txt").read_text()
    sql = (REPO / "services/api/migrations/sql/0083_r5_optimisation.sql").read_text()
    assert "core.optimisation_reports" in sql and "FUNCTION" not in sql
    assert '["optimisation", "Optimisation"' in (REPO / "services/web/src/Admin.jsx").read_text()
    ops = (REPO / "services/ops/ops.py").read_text()
    assert '"/docker/prune"' in ops and '"/docker/space"' in ops and '"volume"' not in ops.split("def docker_prune(")[1].split("\ndef ")[0]


def test_docker_sizes_are_read():
    import importlib.util
    spec = importlib.util.spec_from_file_location("opsmod", REPO / "services/ops/ops.py")
    src = (REPO / "services/ops/ops.py").read_text()
    assert spec and "def _size_mb(" in src
    ns: dict = {}
    exec("import re\n" + "def _size_mb(" + src.split("def _size_mb(")[1].split("\ndef ")[0], ns)   # noqa: S102
    assert ns["_size_mb"]("1.5GB") == 1536 and ns["_size_mb"]("350MB (40%)") == 350 and ns["_size_mb"]("x") == 0
