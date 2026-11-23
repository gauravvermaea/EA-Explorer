"""R5.19 (owner, 14 Nov 2026: "A user will put in the number of concurrent users and models and projects. We need to be
able to predict RAM, CPU and Disk for server deployments"; "based on best guess"; "same for containers etc"): the tests
the story names."""

import io
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))
sys.path.insert(0, str(REPO))

from eax import sizing as S  # noqa: E402


def laptop_limits() -> dict:
    out = {}
    for name, svc in yaml.safe_load((REPO / "deploy/compose/docker-compose.laptop.yml").read_text())["services"].items():
        mem = (((svc.get("deploy") or {}).get("resources") or {}).get("limits") or {}).get("memory")
        if mem:
            out[name] = int(mem.rstrip("g")) * 1024
    return out


def test_a_laptop_comes_out_at_the_laptops_own_settings():
    r = {c["container"]: c for c in S.estimate(S.LAPTOP)["containers"]}
    for name, limit in laptop_limits().items():
        assert abs(r[name]["memory_limit_mb"] - limit) <= 0.25 * limit, (name, r[name]["memory_limit_mb"], limit)
    assert S.estimate(S.LAPTOP)["server"]["ram_gb"] <= 16                                   # the owner's laptop


@pytest.mark.parametrize("key,more", [("users", 400), ("models", 200), ("projects", 500), ("documents_per_project", 900),
                                      ("backups_kept", 30)])
def test_it_grows_as_each_input_grows_and_never_shrinks(key, more):
    base = {"users": 20, "models": 10, "model_size": "medium", "projects": 10, "documents_per_project": 50, "backups_kept": 7}
    prev = None
    for v in (base[key], (base[key] + more) // 2, more):
        s = S.estimate({**base, key: v})["server"]
        now = (s["ram_needed_gb"], s["cores_needed"], s["disk_needed_gb"])
        if prev:
            assert all(a >= b for a, b in zip(now, prev, strict=True)), (key, v, now, prev)
        prev = now
    small, large = (S.estimate({**base, "model_size": x})["server"]["disk_needed_gb"] for x in ("small", "large"))
    assert large > small


def test_the_limits_are_ones_compose_accepts():
    r = S.estimate({"users": 120, "models": 40, "projects": 30})
    doc = yaml.safe_load(r["override"])
    for name, svc in doc["services"].items():
        lim = svc["deploy"]["resources"]["limits"]
        assert re.fullmatch(r"\d+m", lim["memory"]) and float(lim["cpus"]) > 0, name
        assert re.fullmatch(r"\d+m", svc["deploy"]["resources"]["reservations"]["memory"])
    known = set(yaml.safe_load((REPO / "docker-compose.yml").read_text().replace("<<: *logging", "")
                               .replace("<<: [*secrets, *folders]", "").replace("<<: [*restart, *logging]", ""))["services"])
    assert set(doc["services"]) <= known                                                      # only services that exist


def test_only_what_can_run_twice_gets_copies():
    r = S.estimate({"users": 2000, "models": 50, "projects": 100})
    for c in r["containers"]:
        if not c["many"]:
            assert c["copies"] == 1, c["container"]
    assert next(c for c in r["containers"] if c["container"] == "api")["copies"] > 1
    assert {"db", "setup", "reports-init", "keycloak"} <= {c["container"] for c in r["containers"] if not c["many"]}


def test_the_containers_add_up_to_the_server():
    r = S.estimate({"users": 80, "models": 25, "projects": 20})
    total = sum(c["memory_limit_mb"] * c["copies"] for c in r["containers"] if not c["once"]) / 1024 + 1
    assert r["server"]["ram_needed_gb"] == round(total, 1) and r["server"]["ram_gb"] >= total
    assert r["server"]["disk_gb"] >= sum(r["disk_in_a_year"].values())


def test_every_answer_carries_its_assumptions_and_says_it_is_an_estimate():
    r = S.estimate({"users": 10, "assumptions": {"mb_per_document": 5}})
    assert r["estimate"] is True and "best estimate" in r["says"].lower()
    assert r["assumptions"]["mb_per_document"] == 5 and set(S.DATA) <= set(r["assumptions"]) and r["headroom"] == S.HEADROOM
    assert "best estimate" in S.text_report(r).lower() and S.CHANGES[-1][0] == S.VERSION


def test_switching_off_leaves_their_containers_out():
    names = {c["container"] for c in S.estimate({"reports": False, "documents": False})["containers"]}
    assert not names & {"reports", "reports-init", "dms", "dms-broker"}


def test_past_a_size_it_says_split():
    assert S.estimate(S.LAPTOP)["split"] == []
    assert any("database" in x for x in S.estimate({"users": 600, "models": 100, "model_size": "large", "projects": 300})["split"])


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError, match="users"):
        S.estimate({"users": -1})
    with pytest.raises(ValueError, match="model_size"):
        S.estimate({"model_size": "huge"})
    with pytest.raises(ValueError, match="number"):
        S.estimate({"models": "many"})


def test_the_workbook_and_beside_reality():
    from openpyxl import load_workbook
    r = S.estimate(S.LAPTOP)
    wb = load_workbook(io.BytesIO(S.workbook(r)))
    assert wb.sheetnames == ["Estimate", "Containers", "Disk", "Settings", "Assumptions"]
    assert wb["Estimate"]["A1"].value.endswith("a best estimate")
    side = {x["container"]: x for x in S.against(r, [{"container": "eaexplorer-api-1", "memory_peak_mb": 1700}])}
    assert side["api"]["really_mb"] == 1700 and side["db"]["really_mb"] is None


def test_eax_estimate_needs_nothing_running(capsys, tmp_path):
    from eaxcli import estimate_cli
    out = tmp_path / "o.yml"
    assert estimate_cli.main(["--users", "50", "--models", "30", "--size", "medium", "--projects", "40", "--override", str(out)]) == 0
    text = capsys.readouterr().out
    assert "best estimate" in text.lower() and "GB RAM" in text and yaml.safe_load(out.read_text())["services"]["api"]
    from eaxcli.core import Failure
    with pytest.raises(Failure):
        estimate_cli.main(["--what"])


def test_it_is_on_the_screen_and_the_command_line():
    assert '"/admin/sizing"' in (REPO / "services/api/eax/api/admin.py").read_text()
    assert "|estimate|" in (REPO / "eax.sh").read_text() and '"optimise", "estimate",' in (REPO / "eax.ps1").read_text()
    assert "### estimate " in (REPO / "eaxcli/help.txt").read_text()
    assert '{ key: "sizing", label: "Sizing' in (REPO / "services/web/src/adminNav.js").read_text()   # System Admin's pages and menu: adminNav.js (D898)
    assert "#/admin/sizing" in (REPO / "services/web/src/Deploy.jsx").read_text()
    sql = (REPO / "services/api/migrations/sql/0085_r5_sizing.sql").read_text()
    assert "core.sizing_estimates" in sql and "FUNCTION" not in sql
