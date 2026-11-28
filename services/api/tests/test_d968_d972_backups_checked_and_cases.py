"""D968 to D972 (owner, 28 Nov 2026, 09:00 to 09:08): every backup file checked after it is made and before it is
restored (its fingerprint, D968); the standard versions carried by a model package (D969); the one-model and one-project
commands (D970); eax test backup-cases (D971); the OData feed checked in the full test (D972). No database or Docker
needed: the files are made here, the commands' helpers stood in."""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
sys.path.insert(0, str(REPO))

from eaxcli import backup_cases as BC  # noqa: E402
from eaxcli import command_tests as CT  # noqa: E402
from eaxcli import commands as C  # noqa: E402

from eax import backup_check as bc  # noqa: E402
from eax import backups as bk  # noqa: E402
from eax import model_ops as mo  # noqa: E402
from eax import project_backup as pb  # noqa: E402

SPEC = {"format": mo.SPEC_FORMAT, "name": "T", "domains": [{"code": "business", "name": "Business"}],
        "entity_types": [{"code": "Capability", "name": "Capability", "domain": "business"}], "relationship_types": [],
        "allowed": [], "attributes": [], "pick_lists": [], "rules": []}


def package(entities: int = 2, counts: int | None = None, versions: dict | None = None) -> bytes:
    rows = [{"key": f"k{i}", "display_id": f"CAP-{i}", "name": f"Capability {i}", "description": "", "parent": "",
             "status": "published"} for i in range(entities)]
    manifest = {"format": mo.PACKAGE_FORMAT, "model": {"name": "T", "kind": "project"},
                "counts": {"entity_types": 1, "entities": entities if counts is None else counts, "relationships": 0}}
    hist = {"standard_versions": versions} if versions else {}
    data, _n, _t = mo.write_package(manifest, SPEC, {"entities": {"Capability": rows}, "relationships": []}, hist, "zip", "T")
    return data


def model_backup(fingerprinted: bool = True, version: str | None = None, **kw) -> bytes:
    members = {"package.zip": package(**kw), "README.txt": b"readme\n",
               "restore/side.json": json.dumps({"commit": 1, "metamodel_version": 1, "spec": SPEC, "snapshot": {}}).encode()}
    info = {"format": bk.FORMAT, "version": version or bk.__version__, "created": "20261128T080000Z", "by": "t",
            "model": {"id": "11111111-1111-1111-1111-111111111111", "name": "T", "kind": "project"},
            "counts": {"entities": 2, "relationships": 0}}
    if fingerprinted:
        info["files"] = bc.fingerprint(members)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("backup.json", json.dumps(info))
        for n, b in members.items():
            z.writestr(n, b)
    return buf.getvalue()


def rezip(data: bytes, change=None, drop: str = "", add: tuple[str, bytes] | None = None) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for n in src.namelist():
            if n == drop:
                continue
            b = src.read(n)
            z.writestr(n, change(n, b) if change else b)
        if add:
            z.writestr(*add)
    return out.getvalue()


# ---------------------------------------------------------------- D968: a model backup's file checked
def test_a_good_model_backup_checks_out():
    c = bc.check_model_bytes(model_backup(), "m.eaxbackup.zip")
    assert c["ok"], c["problems"]
    assert c["counts"]["entities"] == 2 and "the fingerprint of 3 member(s)" in c["checked"]


@pytest.mark.parametrize("bad, words", [
    (lambda d: b"not a zip at all" * 10, "not a readable zip"),
    (lambda d: d[: len(d) // 2], "zip"),
    (lambda d: rezip(d, lambda n, b: b + b"x" if n == "README.txt" else b), "changed since the backup was made"),
    (lambda d: rezip(d, drop="restore/side.json"), "restore/side.json is missing"),
    (lambda d: rezip(d, add=("extra.txt", b"x")), "not in the fingerprint"),
    (lambda d: rezip(d, drop="backup.json"), "no backup.json"),
    (lambda d: model_backup(version="999.0.0"), "newer"),
    (lambda d: model_backup(counts=5), "its manifest says 5"),
    (lambda d: rezip(d, lambda n, b: json.dumps({**json.loads(b), "format": "x/1"}).encode() if n == "backup.json" else b),
     "not a model backup"),
])
def test_a_bad_model_backup_is_found(bad, words):
    c = bc.check_model_bytes(bad(model_backup()), "m.eaxbackup.zip")
    assert not c["ok"] and words in " ".join(c["problems"]), c["problems"]


def test_a_file_from_before_fingerprints_is_checked_for_the_rest():
    c = bc.check_model_bytes(model_backup(fingerprinted=False))
    assert c["ok"] and any("before backups were fingerprinted" in n for n in c["notes"])


def test_model_file_fingerprints_every_member_but_backup_json():
    src = (API / "eax" / "backups.py").read_text(encoding="utf-8")
    body = src[src.index("def model_file("):src.index("def read_file(")]
    assert 'info["files"] = bc.fingerprint(members)' in body and body.index('info["files"]') < body.index('z.writestr("backup.json"')


def test_a_written_file_that_does_not_check_out_is_not_kept(tmp_path):
    good, bad = tmp_path / "a.eaxbackup.zip", tmp_path / "b.eaxbackup.zip"
    good.write_bytes(model_backup())
    bad.write_bytes(model_backup()[:300])
    assert bk.written_ok(good)["sha256"] == hashlib.sha256(good.read_bytes()).hexdigest()
    with pytest.raises(bk.EditError, match="did not check out after it was written"):
        bk.written_ok(bad)
    assert not bad.exists()


def test_every_backup_is_checked_as_it_is_written_and_before_it_is_restored():
    src = (API / "eax" / "backups.py").read_text(encoding="utf-8")
    assert src.count("written_ok(") >= 4                       # a model's own, each model and project of a run, the def
    assert "whole = bc.check_run(folder.parent)" in src         # the whole application backup after it is written
    restore = src[src.index("def restore(conn, user, p: dict)"):src.index("def _restore_new(")]
    assert restore.index("refuse_unchecked(path, z)") < restore.index("new_record(")   # before anything is touched
    app = src[src.index("def restore_application("):]
    assert app.index("bc.check_run(d)") < app.index("new_record(")
    psrc = (API / "eax" / "project_backup.py").read_text(encoding="utf-8")
    assert "bk.refuse_unchecked(path)" in psrc and "checked = bk.written_ok(out_dir / file)" in psrc
    assert 'info["files"] = bc.fingerprint(members)' in psrc


def project_backup_bytes(docs: int = 1, missing: int = 0, with_model: bool = True, tamper: str = "") -> bytes:
    guid = "22222222-2222-2222-2222-222222222222"
    rows = {"projects": [{"guid": guid, "name": "P"}],
            "documents": [{"guid": f"d{i}", "file_name": f"f{i}.txt", "mayan_document_id": i + 1} for i in range(docs)],
            "steps": [{"name": "s"}]}
    members = {f"project/{t}.json": json.dumps(v).encode() for t, v in rows.items()}
    for i in range(docs - missing):
        members[f"documents/d{i}/f{i}.txt"] = b"file"
    models = []
    if with_model:
        members["models/33333333-3333-3333-3333-333333333333.eaxbackup.zip"] = model_backup()
        models.append({"guid": "33333333-3333-3333-3333-333333333333", "name": "M", "how": "created", "in_file": True})
    info = {"format": pb.FORMAT, "format_version": pb.FORMAT_VERSION, "version": "1.0.0", "project": {"id": guid, "name": "P"},
            "counts": {t: len(v) for t, v in rows.items()}, "models": models, "documents_missing": ["x"] * missing,
            "files": bc.fingerprint(members)}
    if tamper == "count":
        info["counts"]["steps"] = 9
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("backup.json", json.dumps(info))
        for n, b in members.items():
            z.writestr(n, b)
    return buf.getvalue()


def test_a_project_backup_is_checked_with_its_models_and_document_files():
    assert bc.check_project_bytes(project_backup_bytes())["ok"]
    assert bc.check_project_bytes(project_backup_bytes(docs=2, missing=1))["ok"]       # a file said missing is not a fault
    c = bc.check_project_bytes(project_backup_bytes(tamper="count"))
    assert not c["ok"] and "backup.json says 9" in " ".join(c["problems"])
    broken = rezip(project_backup_bytes(), lambda n, b: b[:200] if n.startswith("models/") else b)
    c = bc.check_project_bytes(broken)
    assert not c["ok"] and any("models/" in p for p in c["problems"])


def test_an_application_backup_is_checked_file_by_file(tmp_path):
    run = tmp_path / "20261128T080000Z-t"
    (run / "models").mkdir(parents=True)
    (run / "projects").mkdir()
    (run / "models" / "m.eaxbackup.zip").write_bytes(model_backup())
    (run / "projects" / "p.eaxproject.zip").write_bytes(project_backup_bytes())
    sha = hashlib.sha256((run / "models" / "m.eaxbackup.zip").read_bytes()).hexdigest()
    man = {"status": "ok", "tag": "t", "models": [{"name": "M", "file": "m.eaxbackup.zip", "status": "ok", "sha256": sha}],
           "projects": [{"name": "P", "file": "p.eaxproject.zip", "status": "ok"}]}
    (run / "manifest.json").write_text(json.dumps(man))
    assert bc.check_run(run)["ok"]
    man["models"][0]["sha256"] = "0" * 64
    (run / "manifest.json").write_text(json.dumps(man))
    c = bc.check_run(run)
    assert not c["ok"] and "differs from the one the manifest gives" in " ".join(c["problems"])
    man["models"].append({"name": "Gone", "file": "gone.eaxbackup.zip", "status": "ok"})
    man["models"][0].pop("sha256")
    (run / "manifest.json").write_text(json.dumps(man))
    assert "its file gone.eaxbackup.zip is missing" in " ".join(bc.check_run(run)["problems"])


def test_check_backup_command(tmp_path, monkeypatch, capsys):
    from eax import backups_cli as cli
    monkeypatch.setenv("EAX_BACKUP_MOUNT", str(tmp_path))
    up = tmp_path / "application" / "uploaded"
    up.mkdir(parents=True)
    (up / "good.eaxbackup.zip").write_bytes(model_backup())
    (up / "bad.eaxbackup.zip").write_bytes(b"nope" * 50)
    assert cli.check(["good.eaxbackup.zip"]) == 0 and "OK  model backup good.eaxbackup.zip" in capsys.readouterr().out
    assert cli.check(["bad.eaxbackup.zip"]) == 1 and "NOT OK" in capsys.readouterr().out
    assert cli.check(["../manifest.json"]) == 2 and "not a path" in capsys.readouterr().out
    assert cli.check([]) == 0 and "No application backup to check yet" in capsys.readouterr().out
    assert cli.check(["all"]) == 1


# ---------------------------------------------------------------- D969: the standard versions in a package
def test_a_package_carries_the_standard_versions_and_reads_them_back():
    sv = {"versions": [{"standard": "ArchiMate", "version": "4.0", "sort_order": 40}],
          "domains": [{"code": "business", "start": "ArchiMate 4.0"}]}
    pkg = mo.read_package(package(versions=sv))
    assert pkg["standard_versions"] == sv and "standard_version" not in json.dumps(pkg["spec"])   # not in metamodel.json
    assert mo.read_package(package())["standard_versions"] is None


def test_an_upload_or_restore_of_a_root_puts_the_versions_back():
    src = (API / "eax" / "model_ops.py").read_text(encoding="utf-8")
    imp = src[src.index("def import_package("):src.index("def load_content(")]
    assert imp.count("standard_versions_in(conn") == 2                   # a root restored, a root of its own
    exp = src[src.index("def export_package("):src.index("def write_package(")]
    assert "standard_versions_out(conn" in exp


# ---------------------------------------------------------------- D970: the commands
def test_the_new_commands_are_in_the_catalogue_with_their_options():
    cat = C.catalogue()
    for name, keys in (("app-backup", {"--models", "--projects"}), ("model-backup", set()), ("project-backup", set()),
                       ("restore-project", {"--new", "--over", "--yes"}), ("check-backup", set())):
        assert keys <= {p["key"] for p in C.find(name, cat)["params"]}, name
    assert C.check_argv(["app-backup", "t", "--models", "a,b", "--projects", "p"])
    assert "restore-project" in C.INTERACTIVE
    for name in ("model-backup", "project-backup", "restore-project"):
        assert name in CT.NOT_RUN and "backup-cases" in CT.NOT_RUN[name]
    assert any(args[0] == "check-backup" for args, *_ in CT.CASES)


def test_eax_routes_the_new_commands_to_the_api():
    main = (REPO / "eaxcli" / "main.py").read_text(encoding="utf-8")
    for name in ("model-backup", "project-backup", "restore-project", "check-backup"):
        assert f'"{name}"' in main
    assert 'stack.interactive([*api, "check"], rest)' in main
    cli = (API / "eax" / "backups_cli.py").read_text(encoding="utf-8")
    for name in ("model-backup", "project-backup", "restore-project", "check"):
        assert f'if argv[0] == "{name}":' in cli


def test_app_backup_takes_models_and_projects():
    from eax import backups_cli as cli
    assert cli._list_option(["t", "--models", "a, b,", "--projects", "p"], "--models") == ["a", "b"]
    assert cli._list_option(["t"], "--projects") == []
    assert cli.backup(["t", "--projects", "p"]) == 2                       # projects go with models


def test_the_new_commands_are_documented():
    help_ = (REPO / "eaxcli" / "help.txt").read_text(encoding="utf-8")
    for h in ("### model-backup <model> [why]", "### project-backup <project> [why]", "### check-backup",
              "### restore-project <project|run> <file>", "--models <names>", "backup-cases  model and project backups"):
        assert h in help_, h
    doc = (REPO / "docs" / "command-line-and-console.md").read_text(encoding="utf-8")
    for w in ("eax model-backup", "eax project-backup", "eax restore-project", "eax check-backup", "eax test backup-cases"):
        assert w in doc, w


# ---------------------------------------------------------------- D971: eax test backup-cases
def test_the_cases_read_the_commands_output():
    listing = "OK  application backup r\n    ok   protea-1a2b3c4d.eaxbackup.zip  ab\n    BAD  p-9f8e7d6c.eaxproject.zip  cd\n"
    assert BC.file_for(listing, "1a2b3c4d-0000") == "protea-1a2b3c4d.eaxbackup.zip"
    assert BC.file_for(listing, "9f8e7d6c-0000") == "p-9f8e7d6c.eaxproject.zip" and BC.file_for(listing, "") == ""
    assert BC.said("x\nFile: 2026-a.eaxbackup.zip\n", "File") == "2026-a.eaxbackup.zip"
    assert BC.restore_id("Log: work/backups/restores/r12/restore.log") == "r12"
    from datetime import UTC, datetime
    assert BC.once_at(UTC, datetime(2026, 11, 28, 8, 0, 10, tzinfo=UTC)) == "2026-11-28T08:01"
    assert BC.once_at(UTC, datetime(2026, 11, 28, 8, 0, 50, tzinfo=UTC)) == "2026-11-28T08:02"


def test_every_case_runs_and_the_clean_up_runs_whatever_happens(tmp_path):
    G = [f"{i}{i}{i}{i}{i}{i}{i}{i}-aaaa-bbbb-cccc-00000000000{i}" for i in range(1, 8)]
    seen: list[str] = []

    def api(cmd, state):
        seen.append(cmd)
        if cmd == "start":
            return {"run_id": 1, "sid": "ab12", "token": "a-token-of-the-test", "made": [],
                    "ids": {"model": G[0], "other_model": G[1], "project": G[2], "canvas": "c"}}
        if cmd == "fingerprint":
            fp = {"name": "n", "kind": "project", "parts": {}, "counts": {"entities": 1}, "keys": "k"}
            return {"models": {g: fp for g in state.get("models") or []},
                    "projects": {g: {"core": {}, "counts": {}, "all": {}, "files": "f"} for g in state.get("projects") or []}}
        if cmd == "compare":
            return {"differences": []}
        if cmd == "find":
            return {"models": {n: (G[3] if n == "ArchiMate 4" else G[4]) for n in state.get("models") or []},
                    "projects": {n: G[5] for n in state.get("projects") or []}}
        if cmd == "runs":
            return {"runs": [{"name": f"20261128T080000Z-{state['prefix']}", "status": "ok"}]}
        if cmd == "forge":
            return {"files": {"not-a-zip": "brc-ab12-not-a-zip.eaxbackup.zip"}}
        if cmd == "change_model":
            raise RuntimeError("the helper broke")              # a case that breaks: the rest of the run still reports
        return {"model": G[6]} if cmd == "new_model" else {}

    def eax(args, seconds):
        return 0, "every file checked; checked out\nRun: r1\nFile: f.eaxbackup.zip\nLog: work/backups/restores/x1/restore.log\n"

    c = BC.Cases(tmp_path / "rep", api=api, eax=eax, sleep=lambda s: None)
    BC.run(c)
    rep = BC.report(c)
    assert seen[0] == "start" and "finish" in seen and seen[1] == "others" and seen[-1] == "others"
    assert any(r["case"] == "C?" and not r["ok"] for r in c.results)          # the broken case is said
    assert any(r["case"] == "C15" for r in c.results) and any(r["case"] == "C14" for r in c.results)
    assert (tmp_path / "rep" / "report.md").read_text(encoding="utf-8").startswith("# eax test backup-cases")
    assert not rep["passed"]


def test_the_clean_up_only_touches_the_tests_own_backups(tmp_path, monkeypatch):
    from eax.testing import backup_cases as H
    monkeypatch.setenv("EAX_BACKUP_MOUNT", str(tmp_path))
    app = tmp_path / "application"
    root, own = "44444444-aaaa-bbbb-cccc-000000000004", "11111111-aaaa-bbbb-cccc-000000000001"
    for d in (app / "models" / root, app / "models" / own, app / "models" / "99999999-aaaa-bbbb-cccc-000000000009", app / "uploaded"):
        d.mkdir(parents=True)
    (app / "models" / root / "2026-brc-ab12-root.eaxbackup.zip").write_bytes(b"x")
    (app / "models" / root / "2026-the-owners-own.eaxbackup.zip").write_bytes(b"x")
    (app / "uploaded" / "brc-ab12-not-a-zip.eaxbackup.zip").write_bytes(b"x")
    (app / "uploaded" / "someone-elses.eaxbackup.zip").write_bytes(b"x")
    with pytest.raises(ValueError):
        H.files_of({"prefix": "", "models": [""]})
    found = H.files_of({"prefix": "brc-ab12", "models": ["", own, "../x"], "shared_models": [root], "projects": [""]})
    assert found["models"] == [own] and found["shared"] == [f"{root}/2026-brc-ab12-root.eaxbackup.zip"]
    assert found["uploaded"] == ["brc-ab12-not-a-zip.eaxbackup.zip"] and found["projects"] == []
    H.remove_files({"prefix": "brc-ab12", "models": [own], "shared_models": [root], "projects": []})
    assert (app / "models" / root / "2026-the-owners-own.eaxbackup.zip").exists()
    assert (app / "models" / "99999999-aaaa-bbbb-cccc-000000000009").is_dir() and (app / "uploaded" / "someone-elses.eaxbackup.zip").exists()
    assert not (app / "models" / own).exists()


def test_the_fingerprints_compare_without_ids():
    from eax.testing import backup_cases as H
    a = {"kind": "project", "parts": {"entities": "1", "views": "unavailable"}, "counts": {"entities": 3}, "keys": "k1"}
    b = {**a, "keys": "k2"}
    assert H.compare_models(a, b) == [] and H.compare_models(a, b, keys=True)
    c = {**a, "parts": {"entities": "2", "views": "x"}, "counts": {"entities": 4}}
    assert H.compare_models(a, c) == ["entities: 3 before, 4 after"]
    assert H.compare_models(a, {"missing": True}) == ["the model is missing"]
    assert all(":m" in q for q in H.MODEL_PARTS.values()) and not any(re.search(r"\b(id|guid)\b,", q) for q in H.MODEL_PARTS.values() if "SELECT 'e'" in q)
    assert H.digest([[1, "a"], [2, "b"]]) == H.digest([[2, "b"], [1, "a"]])


def test_backup_cases_run_in_the_full_test_after_backup_restore():
    main = (REPO / "eaxcli" / "main.py").read_text(encoding="utf-8")
    i, j = main.index('full_step("backup and restore test"'), main.index('full_step("backup and restore cases"')
    assert i < j < main.index('full_step("SonarQube scan"')
    assert 'rest[:1] == ["backup-cases"]' in main


# ---------------------------------------------------------------- D972: the OData feed in the full test
def test_the_odata_checks_pass_on_a_feed_that_is_right_and_fail_on_one_that_is_not(monkeypatch):
    from eax import odata as od
    from eax.testing import odata_check as oc
    names = ["Self-test application 1", "Self-test application 2", "Self-test duplicate app", "Self-test duplicate ap"]
    rows = {"ApplicationComponent": [{"Id": str(i), "Name": n} for i, n in enumerate(names)],
            "Capability": [{"Id": "c1", "Name": "Self-test capability 1"}]}
    rows["Entities"] = rows["ApplicationComponent"] + rows["Capability"]
    rows["Relationships"] = [{"Id": "r1"}]
    cols = ["Id", "DisplayId", "Name", "Description", "EntityType"]
    meta = ('<?xml version="1.0"?><edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx"><edmx:DataServices>'
            '<Schema xmlns="http://docs.oasis-open.org/odata/ns/edm"><EntityType Name="Entities">'
            + "".join(f'<Property Name="{c}"/>' for c in cols) + "</EntityType><EntityContainer>"
            + "".join(f'<EntitySet Name="{t}"/>' for t in rows) + "</EntityContainer></Schema></edmx:DataServices></edmx:Edmx>")
    wrong = {"count": False}

    def get(base, path, token, timeout=120):
        from urllib.parse import parse_qsl, urlsplit
        if not token:
            return 401, ""
        if token == "n":                                     # the person without the model
            return 404, json.dumps({"error": {"message": "No model"}})
        u = urlsplit(path)
        tail = u.path.rsplit("/", 1)[-1]
        if path.startswith("/api/v1/odata/governance/"):
            return 200, json.dumps({"value": [{"name": "GovernanceDecisions"}]})
        if tail == "":
            return 200, json.dumps({"value": [{"name": t} for t in rows]})
        if tail == "$metadata":
            return 200, meta
        if tail not in rows:
            return 404, json.dumps({"error": {"message": "no table"}})
        data = list(rows[tail]) + ([{"Id": "x", "Name": "extra"}] if wrong["count"] and tail == "Entities" else [])
        try:
            return 200, json.dumps(od.page(data, ["Id", "Name"], dict(parse_qsl(u.query)), "b/", tail))
        except od.ODataError as exc:
            return exc.status, json.dumps({"error": {"message": str(exc)}})

    truth = {"*": sorted(r["Name"] for r in rows["Entities"]), "ApplicationComponent": names, "Capability": ["Self-test capability 1"],
             "#rel": [""]}
    monkeypatch.setattr(oc, "get", get)
    monkeypatch.setattr(oc, "db_rows", lambda engine, model: truth)
    results: list[tuple] = []
    out = oc.run("http://api", {"super-admin": "t", "no-role": "n"}, {"model": "m"}, lambda *a: results.append(a), lambda m: None, None)
    assert out["failed"] == 0 and out["passed"] >= 18, [r for r in results if r[1] == "failed"]
    wrong["count"] = True
    results.clear()
    out = oc.run("http://api", {"super-admin": "t"}, {"model": "m"}, lambda *a: results.append(a), lambda m: None, None)
    assert any("Entities holds" in r[0] and r[1] == "failed" for r in results)


def test_the_odata_checks_run_in_the_api_suite():
    run = (API / "eax" / "testing" / "run.py").read_text(encoding="utf-8")
    assert "odata_check.run(API, tokens, ids, r.recorder(\"api\"), r.log, r.repo)" in run


def test_the_others_backups_are_listed_without_the_tests_own(tmp_path, monkeypatch):
    from eax.testing import backup_cases as H
    monkeypatch.setenv("EAX_BACKUP_MOUNT", str(tmp_path))
    own = "11111111-aaaa-bbbb-cccc-000000000001"
    for rel in ("infrastructure/2026-nightly/db.dump", "application/20261128T010000Z-nightly/manifest.json",
                f"application/models/{own}/x.eaxbackup.zip", "application/20261128T090000Z-brc-ab12-all/manifest.json",
                "restores/r1/restore.log"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"12345")
    files = H.others({"prefix": "brc-ab12", "models": [own], "projects": []})["files"]
    assert files == ["application/20261128T010000Z-nightly/manifest.json:5", "infrastructure/2026-nightly/db.dump:5"]
