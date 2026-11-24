"""R9.12 (D841, D843; owner, 22 Nov 2026: "Add a schedule to check for latets images every 3 months"): `eax images`
lists every image in use (our Dockerfiles' bases and the others), whether a newer one is published and its fixable
findings, changes nothing, and a system schedule runs it on the first day of every third month, telling the admins."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "services" / "ops"))
from eaxcli import commands as C  # noqa: E402
from eaxcli import images as I  # noqa: E402

OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64


def test_a_dockerfiles_bases_without_its_own_stages_or_variables():
    df = ("FROM node:22-alpine AS build\nRUN x\nFROM --platform=linux/amd64 nginxinc/nginx-unprivileged:1.30-alpine\n"
          "FROM build AS again\nFROM ${BASE}\nFROM scratch\nfrom python:3.12-slim\n")
    assert I.from_lines(df) == ["node:22-alpine", "nginxinc/nginx-unprivileged:1.30-alpine", "python:3.12-slim"]


def test_images_from_the_compose_config(tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "Dockerfile").write_text("FROM node:22-alpine AS b\nFROM nginx:1.30\n")
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "Api.Dockerfile").write_text("FROM python:3.12-slim\n")
    config = {"services": {"web": {"build": {"context": str(tmp_path / "web")}},
                           "api": {"build": {"context": "api", "dockerfile": "Api.Dockerfile"}},
                           "db": {"image": "postgres:16-alpine"}, "db2": {"image": "postgres:16-alpine"}}}
    got = {i["ref"]: i for i in I.images_of(config, root=tmp_path)}
    assert got["node:22-alpine"]["kind"] == "base" and got["nginx:1.30"]["services"] == ["web"]
    assert got["python:3.12-slim"]["services"] == ["api"]
    assert got["postgres:16-alpine"] == {"ref": "postgres:16-alpine", "kind": "image", "services": ["db", "db2"]}


def _docker(here: dict[str, str], latest: dict[str, str]):
    """docker as the test sees it: image inspect gives the digest here, imagetools inspect the published one."""
    def run(cmd):
        ref = cmd[3] if cmd[1] == "image" else cmd[4]
        if cmd[1] == "image":
            return (0, f'["{ref.split(":")[0]}@{here[ref]}"]|2026-08-01T10:00:00.000Z') if ref in here else (1, "")
        return (0, json.dumps({"digest": latest[ref]})) if ref in latest else (1, "no network")
    return run


def test_newer_current_not_here_and_unknown():
    images = [{"ref": r, "kind": "image", "services": [r.split(":")[0]]}
              for r in ("postgres:16", "keycloak:26", "redis:7", "mayan:4")]
    run = _docker({"postgres:16": OLD, "keycloak:26": NEW, "mayan:4": OLD}, {"postgres:16": NEW, "keycloak:26": NEW})
    rows = {r["ref"]: r for r in I.check(images, [], run)}
    assert rows["postgres:16"]["status"] == "newer" and rows["postgres:16"]["created"] == "2026-08-01T10:00:00"
    assert rows["keycloak:26"]["status"] == "current"
    assert rows["redis:7"]["status"] == "not here"
    assert rows["mayan:4"]["status"] == "unknown"           # the registry not reached: said, not guessed


def test_fixable_findings_are_matched_to_their_image():
    findings = [
        {"source": "trivy", "severity": "high", "fix": True, "where": "image postgres:16.4-alpine"},
        {"source": "trivy", "severity": "critical", "fix": True, "where": "image eaexplorer/api:8.0.0"},
        {"source": "trivy", "severity": "high", "fix": False, "where": "image postgres:16"},     # no fix: not counted
        {"source": "trivy", "severity": "medium", "fix": True, "where": "image postgres:16"},    # medium: not counted
        {"source": "semgrep", "severity": "high", "fix": True, "where": "image postgres:16"},
    ]
    assert I.repo("docker.io/library/postgres:16@" + OLD) == "docker.io/library/postgres"
    assert I.repo("localhost:5000/x/y:1") == "localhost:5000/x/y"
    assert I.fixable(findings, "postgres:16-alpine") == 1
    rows = I.check([{"ref": "python:3.12-slim", "kind": "base", "services": ["api"]}], findings, _docker({}, {}))
    assert rows[0]["fixable"] == 1                            # a base counts its service's own image's findings


def test_the_report_and_who_is_told(tmp_path):
    rows = [{"ref": "keycloak:26", "kind": "image", "services": ["keycloak"], "created": "", "status": "current", "fixable": 0},
            {"ref": "postgres:16", "kind": "image", "services": ["db"], "created": "2026-08-01", "status": "newer", "fixable": 3}]
    path = I.report(rows, "20261121T142504Z", tmp_path)
    md = path.read_text(encoding="utf-8")
    assert md.index("postgres:16") < md.index("keycloak:26") and "1 of 2 images have a newer one" in md
    assert "Nothing was changed" in md and json.loads(path.with_suffix(".json").read_text())["findings_from"]
    told = []
    assert I.tell(rows, path, post=lambda e: told.append(e) or True)
    assert told[0]["event"] == "reminder" and "postgres:16 (3 fixable findings)" in told[0]["detail"]
    assert not I.tell([rows[0]], path, post=lambda e: told.append(e) or True) and len(told) == 1   # nothing newer


def test_eax_images_end_to_end_changes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(I, "WORK", tmp_path)
    monkeypatch.setattr(I, "compose_args", lambda a: ["docker", "compose", *a])
    monkeypatch.setattr(I, "say", lambda *a, **k: None)
    told = []
    monkeypatch.setattr(I, "tell", lambda rows, path, post=None: told.append(path) or True)
    calls = []
    docker = _docker({"postgres:16": OLD}, {"postgres:16": NEW})

    def run(cmd):
        calls.append(cmd)
        if cmd[:2] == ["docker", "compose"]:
            return 0, json.dumps({"services": {"db": {"image": "postgres:16"}}})
        return docker(cmd)
    assert I.main(["check"], run=run) == 0
    assert told and next((tmp_path / "images").glob("check-*.md"))
    verbs = {c[1] if c[1] != "buildx" else "imagetools" for c in calls}
    assert verbs <= {"compose", "image", "imagetools"}        # nothing pulled, built or removed
    assert all("pull" not in c and "rm" not in c for c in calls)


def test_a_schedule_every_three_months_that_is_a_command_of_the_catalogue():
    import commandcentre
    s = next(x for x in commandcentre.SYSTEM_SCHEDULES if x["id"] == "r9images")
    assert s["argv"] == ["images", "check"] and s["enabled"] and s["cron"].split()[2:4] == ["1", "1,4,7,10"]
    assert C.check_argv(s["argv"]) == ["images", "check"]
    assert "r9images" not in commandcentre.OFF_UNTIL_CHOSEN


def test_every_form_runs_it():
    assert '"sonar", "images", "diag"))' in (REPO / "eax.ps1").read_text(encoding="utf-8")   # diag after it (R14.23)
    assert "|errors|sonar|images|diag)" in (REPO / "eax.sh").read_text(encoding="utf-8")
    assert 'if command == "images":' in (REPO / "eaxcli" / "main.py").read_text(encoding="utf-8")
    entry = next(c for g in C.catalogue()["groups"] for c in g["commands"] if c["name"] == "images")
    assert len(entry["summary"]) <= 102
