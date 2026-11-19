"""R5.6-B1: the backup and restore test (owner, 16 Nov 2026: B1, content of every kind, B2, restore B1 - gone, restore B2 -
everything back, checked row by row and file by checksum; synchronous, one command after another from eax; random
backup names, both removed at the end; it replaces the old restore suite).

The parts run here without Docker: the operations helper's steps (brtest.py) with its helpers stood in, the host's test
(eaxcli/backup_restore.py) with the helper and the API stood in by a pretend installation that really forgets what a
restore takes away, and how eax reaches it in every form."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import backup_restore as BR  # noqa: E402


def _brtest():
    spec = importlib.util.spec_from_file_location("brtest_under_test", REPO / "services" / "ops" / "brtest.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- the operations helper's steps
def test_the_fingerprint_lines_are_read():
    b = _brtest()
    out = b.parse("T eaexplorer core.models 3 abc\nT keycloak public.user_entity 2 def\n"
                  "F documents media/a file with spaces.pdf 0123\nF persist settings.json 4567\nnoise\n")
    assert out["tables"] == {"eaexplorer core.models": [3, "abc"], "keycloak public.user_entity": [2, "def"]}
    assert out["files"] == {"documents/media/a file with spaces.pdf": "0123", "persist/settings.json": "4567"}


def test_not_enough_disk_is_refused_before_anything_is_touched():
    b = _brtest()
    assert b.need_bytes([{"status": "ok", "bytes": 1_000_000_000}]) == 4_400_000_000      # four backups and a tenth
    b.bind({"_container": lambda s: {"id": "x", "state": "running"},
            "list_infra": lambda: [{"name": "n", "status": "ok", "bytes": 2_000_000_000}],
            "filesystems": lambda: [{"label": "Backups folder", "free_bytes": 3_000_000_000}]})
    r = b.ready()
    assert not r["enough"] and "8.8 GB" in r["error"] and "3.0 GB are free" in r["error"] and "Nothing was touched" in r["error"]
    b.H["filesystems"] = lambda: [{"label": "Backups folder", "free_bytes": 50_000_000_000}]
    assert b.ready()["enough"]
    b.H["_container"] = lambda s: None
    with pytest.raises(RuntimeError, match="backup container is not running"):
        b.ready()


def test_the_clean_up_never_removes_the_tests_backups_and_the_test_unpins_before_deleting():
    b = _brtest()
    rows = [{"name": "B2", "pinned": True}, {"name": "x2"}, {"name": "B1", "pinned": True}, {"name": "x1"}]
    b.bind({"list_infra": lambda: rows})
    r = b.retention(["B1", "B2"])
    assert r == {"would_remove": 1, "kept": ["B1", "B2"], "lost": []}
    calls = []
    b.H.update(pin_backup=lambda n, p: calls.append(("pin", n, p)), delete_infra_backup=lambda n: calls.append(("delete", n)))
    assert b.delete(["B1", "B2"])["deleted"] == ["B1", "B2"]
    assert calls == [("pin", "B1", False), ("delete", "B1"), ("pin", "B2", False), ("delete", "B2")]


def test_backups_are_pinned_while_the_test_runs_and_each_command_answers_in_json(capsys):
    b = _brtest()
    seen = {}

    class Lock:
        def acquire(self, blocking=True):
            return True

        def release(self):
            pass

    def do_backup(tag, by, kind, version, pinned=False):
        seen.update(tag=tag, pinned=pinned)
        return {"name": f"20261116T120000Z-{tag}", "status": "ok"}
    b.bind({"_block": Lock(), "_do_backup": do_backup, "_infra_folder": lambda n: (_ for _ in ()).throw(FileNotFoundError())})
    assert b.cli(["backup", "brt-abc12345", "--version", "5.6.0"], "5.6.0") == 0
    assert seen == {"tag": "brt-abc12345", "pinned": True}
    assert json.loads(capsys.readouterr().out.strip())["name"] == "20261116T120000Z-brt-abc12345"
    assert b.cli(["nonsense"], "5.6.0") == 1 and "unknown command" in json.loads(capsys.readouterr().out)["error"]
    assert b.cli(["restore", "../etc", "--what", "full"], "5.6.0") == 1 and "name" in json.loads(capsys.readouterr().out)["error"]


# ---------------------------------------------------------------- comparing fingerprints
def test_two_fingerprints_are_compared_table_by_table_and_file_by_file():
    a = {"tables": {"eaexplorer core.models": [3, "a"], "eaexplorer jobs.procrastinate_jobs": [9, "j"],
                    "keycloak public.user_session": [1, "s"], "eaexplorer core.entities": [10, "e"]},
         "files": {"documents/media/x.pdf": "1", "persist/settings.json": "2", "reports/cache/y": "3"}}
    b = json.loads(json.dumps(a))
    assert BR.same(a, b, set())["differ"] == []
    b["tables"]["eaexplorer core.models"] = [4, "b"]
    b["tables"]["eaexplorer jobs.procrastinate_jobs"] = [10, "k"]            # written by the installation itself
    b["tables"]["keycloak public.user_session"] = [2, "t"]
    b["files"]["documents/media/x.pdf"] = "9"
    b["files"]["reports/cache/y"] = "4"
    del b["tables"]["eaexplorer core.entities"]
    c = BR.same(a, b, set())
    assert c["differ"] == ["eaexplorer core.entities: missing after"]                   # lost: fails
    assert c["allowed"] == ["eaexplorer core.models: 1 more rows (3 before, 4 after)", "documents/media/x.pdf: another checksum"]
    assert set(c["not_compared"]) == {"eaexplorer jobs.procrastinate_jobs", "keycloak public.user_session", "reports/cache/y"}
    assert BR.same(a, b, {"eaexplorer core.models", "documents/media/x.pdf", "eaexplorer core.entities"})["differ"] == []
    assert BR.moved(a, b) >= {"eaexplorer core.models", "documents/media/x.pdf"}


def test_backup_names_are_random_and_secrets_are_looked_for(tmp_path):
    names = {BR.random_name() for _ in range(20)}
    assert len(names) == 20 and all(re.fullmatch(r"brt-[a-z0-9]{8}", n) for n in names)
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DB_PASSWORD=s3cretValue1\nEAX_KC_CLIENT_SECRET='abcdefgh12'\nEAX_HOSTNAME=x\nEAX_X_PASSWORD=change-me\n")
    vals = BR.config_secrets(env)
    assert vals == ["s3cretValue1", "abcdefgh12"]
    assert BR.secrets_in("a log with abcdefgh12 in it", vals) == ["secret #2"]       # never the value itself


def test_the_realm_and_switches_are_not_secrets_and_start_up_status_is_the_installations_own(tmp_path):
    """The owner's run (16 Nov 2026, 22:21): "secret #15" was EAX_KEYCLOAK_REALM (KEYCLOAK has KEY in it), and
    operations.startup_parts (written at every start) failed the compare."""
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_KEYCLOAK_REALM=eaexplorer\nEAX_KEYCLOAK_ADMIN_PASSWORD=pw123456\nEAX_API_KEY=k123456789\n"
                   "EAX_TOKEN_ROTATION=true\nEAX_SECRET_SCAN=False\n")
    assert BR.config_secrets(env) == ["pw123456", "k123456789"]
    a = {"tables": {"eaexplorer operations.startup_parts": [5, "x"], "eaexplorer core.viewpoints": [3, "v"]}, "files": {}}
    b = {"tables": {"eaexplorer operations.startup_parts": [5, "y"], "eaexplorer core.viewpoints": [3, "v"]}, "files": {}}
    c = BR.same(a, b, set())
    assert c["differ"] == [] and c["not_compared"] == ["eaexplorer operations.startup_parts"] and c["tables"] == 1
    # Documents writes its settings' copy at every start (23:56); its real settings file is still compared
    a = {"tables": {}, "files": {"documents/config_backup.yml": "1", "documents/config.yml": "c"}}
    b = {"tables": {}, "files": {"documents/config_backup.yml": "2", "documents/config.yml": "c"}}
    c = BR.same(a, b, set())
    assert c["differ"] == [] and c["not_compared"] == ["documents/config_backup.yml"] and c["files"] == 1
    b["files"]["documents/config.yml"] = "changed"                       # a setting rewritten: allowed, listed
    c = BR.same(a, b, set())
    assert c["differ"] == [] and c["allowed"] == ["documents/config.yml: another checksum"]


def test_the_comparison_fails_only_on_data_lost_and_notes_what_the_installation_writes_itself():
    """Broad (the owner, 17 Nov 2026, 00:00: "make comparisons a bit loose"; 01:00: "we need some broad level tests to check
    if backup is done"): his run of 01:00 failed only on two model roles EA Explorer added after it started again."""
    a = {"tables": {"eaexplorer core.models": [3, "m"], "eaexplorer core.viewpoints": [40, "v"], "eaexplorer core.model_users": [202, "u"],
                    "eaexplorer core.entities": [100, "e"], "keycloak public.user_entity": [20, "k"]},
         "files": {"documents/media/document_file_storage/ab12": "1", "documents/config.yml": "s", "persist/s.json": "p"}}
    b = json.loads(json.dumps(a))
    b["tables"]["eaexplorer core.viewpoints"] = [40, "stamped again"]         # rewritten at start-up
    b["tables"]["eaexplorer core.model_users"] = [204, "two more"]            # added at start-up (the run of 01:00)
    b["tables"]["eaexplorer core.new_table"] = [0, ""]                         # a table the installation made
    b["files"]["documents/config.yml"] = "rewritten"
    b["files"]["imports/new.txt"] = "n"
    c = BR.same(a, b, set())
    assert c["differ"] == [] and len(c["allowed"]) == 5 and "2 more rows (202 before, 204 after)" in BR.said(c)
    assert BR.said(c).startswith("6 tables and 4 files compared; nothing lost. Noted, not failed")
    lost = json.loads(json.dumps(b))
    lost["tables"]["eaexplorer core.entities"] = [99, "e"]                     # a row lost
    del lost["tables"]["keycloak public.user_entity"]                          # a table lost
    del lost["files"]["persist/s.json"]                                        # a file lost
    del lost["files"]["documents/media/document_file_storage/ab12"]           # a stored document lost
    assert BR.same(a, lost, set())["differ"] == [
        "eaexplorer core.entities: 100 rows before, 99 after (1 lost)", "keycloak public.user_entity: missing after",
        "documents/media/document_file_storage/ab12: missing after", "persist/s.json: missing after"]
    assert BR.whole({"status": "ok", "parts": {"databases": ["eaexplorer", "keycloak", "mayan"], "files": ["documents"]}})[0]
    ok, why = BR.whole({"status": "ok", "parts": {"databases": ["eaexplorer", "keycloak"], "files": []}})
    assert not ok and "missing: mayan, Documents' files" in why


# ---------------------------------------------------------------- the whole test, against a pretend installation
class Pretend:
    """A pretend installation: its tables and files, backups that copy them, restores that put them back."""

    def __init__(self, keep_after_b1: bool = False, broken_b2: bool = False):
        self.state = {"tables": {"eaexplorer core.models": [1, "base"], "keycloak public.user_entity": [2, "kc"]},
                      "files": {"persist/settings.json": "p", "tls/site.crt": "c", "config/eaexplorer.env": "e"}}
        self.backups: dict[str, dict] = {}
        self.order: list[str] = []
        self.keep_after_b1, self.broken_b2 = keep_after_b1, broken_b2
        self.content = False
        self.quiet = False
        self.n = 0

    def ops(self, *a, state=None):
        cmd = a[0]
        self.order.append(" ".join(a[:2]) if cmd in ("restore", "mark") else cmd)
        if cmd == "quiet":
            self.quiet = a[1] == "on"
            return {"quiet": self.quiet, "page": self.quiet}
        if cmd == "ready":
            return {"enough": True, "need_bytes": 4e9, "free_bytes": 9e9}
        if cmd == "fingerprint":
            return json.loads(json.dumps(self.state))
        if cmd == "backup":
            self.n += 1
            name = f"2026111612000{self.n}Z-{a[1]}"
            self.backups[name] = json.loads(json.dumps({"state": self.state, "content": self.content}))
            return {"name": name, "status": "ok", "seconds": 60,
                    "parts": {"databases": ["eaexplorer", "keycloak", "mayan", "superset"], "files": ["documents", "tls"]}}
        if cmd == "restore":
            b = self.backups[a[1]]
            before = f"before-{self.n}"
            self.n += 1
            self.backups[before] = {"state": json.loads(json.dumps(self.state)), "content": self.content}
            keep = self.keep_after_b1 and self.content
            self.state, self.content = json.loads(json.dumps(b["state"])), b["content"] or keep
            if keep:
                self.state["tables"]["eaexplorer core.models"] = [3, "with the test's"]
            if self.broken_b2 and b["content"]:
                del self.state["files"]["persist/settings.json"]                 # lost
            return {"status": "ok", "before": before, "seconds": 120}
        if cmd == "mark":
            key = f"persist/self_test_{a[1]}_backup_restore.txt"
            if a[2] == "put":
                self.state["files"][key] = "m"
                self.state["files"][key.replace("persist", "imports")] = "m"
            return {"files": [key], "action": a[2]}
        if cmd == "retention":
            return {"would_remove": 0, "kept": list(a[1:]), "lost": []}
        if cmd == "delete":
            for n in a[1:]:
                self.backups.pop(n, None)
            return {"deleted": list(a[1:]), "left": []}
        raise AssertionError(cmd)

    def api(self, cmd, state):
        self.order.append(f"api {cmd}")
        if cmd == "start":
            self.content = True
            self.state["tables"]["eaexplorer core.models"] = [3, "with the test's"]
            return {"run_id": 7, "sid": "abcdef123456", "token": "tok-SECRET-123", "ids": {},
                    "made": [{"what": "a model", "ok": True}, {"what": "a document with its file", "ok": True}], "calls": []}
        if cmd == "snapshot":
            return {"models": {"m1": {"name": "self_test_abcdef123456_1", "entities": 7, "sum": "x"}} if self.content else
                    {"m1": {"missing": True}}, "documents": {"rows": 1, "sum": "d"} if self.content else {}}
        if cmd == "idle":
            return {"idle": True, "waited": 0}
        if cmd == "after":
            return {"checks": [{"scenario": "S1", "check": "the test's Super Admin account signs in", "ok": True}]}
        if cmd == "finish":
            return {"removed": {"models": 2}}
        raise AssertionError(cmd)


def _test(tmp_path, inst):
    return BR.Test(tmp_path / "rep", ops=inst.ops, api=inst.api, wait=lambda: True)


def test_the_owners_test_passes_one_step_after_another_and_cleans_up(tmp_path):
    inst = Pretend()
    rep = BR.run(_test(tmp_path, inst))
    assert rep["passed"], [r for r in rep["results"] if r["ok"] is False]
    assert inst.order == ["quiet", "ready", "api idle", "fingerprint", "backup", "fingerprint", "api start", "mark abcdef123456",
                          "api idle", "api snapshot", "fingerprint", "backup", "fingerprint", "retention", f"restore {rep['B1']}", "api snapshot",
                          "fingerprint", f"restore {rep['B1']}", "fingerprint", f"restore {rep['B2']}", "api snapshot",
                          "fingerprint", "api after", "api finish", "mark abcdef123456", "delete", "quiet"]
    assert not inst.quiet                                      # the maintenance page and the background back
    assert re.search(r"-brt-[a-z0-9]{8}$", rep["B1"]) and re.search(r"-brt-[a-z0-9]{8}$", rep["B2"]) and rep["B1"] != rep["B2"]
    assert inst.backups == {}                                  # B1, B2 and the backups the restores took first: removed
    names = [r["name"] for r in rep["results"]]
    assert "everything the test made is gone (the project, its models and the rest)" in names
    assert "nothing of B2 lost: every database's tables and rows and every file there" in names
    assert "S8: the same backup restored twice loses nothing" in names
    assert "B1 holds every database and all of Documents" in names and "B2 holds every database and all of Documents" in names
    text = (tmp_path / "rep" / "report.md").read_text()
    assert "**Passed**" in text and "recovery time" in text and "Not in this run" in text
    assert "tok-SECRET-123" not in text and "tok-SECRET-123" not in (tmp_path / "rep" / "report.json").read_text()


def test_content_still_there_after_b1_fails_restores_b2_and_keeps_the_backups(tmp_path):
    inst = Pretend(keep_after_b1=True)
    rep = BR.run(_test(tmp_path, inst))
    assert not rep["passed"]
    bad = [r["name"] for r in rep["results"] if r["ok"] is False]
    assert "everything the test made is gone (the project, its models and the rest)" in bad
    assert f"restore {rep['B2']}" in inst.order and "delete" not in inst.order         # B2 put back; the backups kept
    assert inst.order[-1] == "quiet" and not inst.quiet                                 # never left paused
    assert any(r["name"].startswith("the backups kept") for r in rep["results"])


def test_a_file_that_does_not_come_back_the_same_fails(tmp_path):
    inst = Pretend(broken_b2=True)
    rep = BR.run(_test(tmp_path, inst))
    bad = {r["name"]: r["detail"] for r in rep["results"] if r["ok"] is False}
    assert "persist/settings.json: missing after" in bad["nothing of B2 lost: every database's tables and rows and every file there"]


def test_it_says_plainly_what_is_lost_and_asks_nothing(monkeypatch, tmp_path):
    """Owner, 16 Nov 2026, 16:54: "backup and restore test should not ask me anything"."""
    import builtins

    import eaxcli.backup_restore as m
    lines = []
    monkeypatch.setattr(m, "say", lambda t="", c="": lines.append(t))
    monkeypatch.setattr(builtins, "input", lambda *a: (_ for _ in ()).throw(AssertionError("asked")))
    monkeypatch.setattr(m, "WORK", tmp_path)
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "run", lambda t: {"passed": True, "minutes": 1})
    assert m.main([]) == 0
    assert any("ANY REAL WORK" in x for x in lines)
    main = (REPO / "eaxcli/main.py").read_text()
    assert 'last = "full" in rest and "--ci" not in rest\n' in main and "ask_confirmation" not in main


# ---------------------------------------------------------------- the API container's part
def test_the_api_side_says_what_is_there_and_what_differs():
    sys.path.insert(0, str(REPO / "services" / "api"))
    from eax.testing import backup_restore as A
    from eax.views import CODE_RE
    assert CODE_RE.match(A.view_code("abcdef123456")) and not A.view_code("abcdef123456").startswith("VP-")
    snap = {"models": {"m1": {"name": "self_test_x_1", "entities": 7, "sum": "a"}, "p": {"missing": True}},
            "documents": {"rows": 1, "sum": "d"}, "kpis": {}, "views": {"error": "not migrated"}}
    assert sorted(A.present(snap)) == ["documents", "self_test_x_1"]
    other = json.loads(json.dumps(snap))
    other["documents"] = {}
    other["models"]["m1"]["entities"] = 6
    d = A.differences(snap, other)
    assert "documents: 1 row(s) before, 0 after" in d and "self_test_x_1: entities 7 before, 6 after" in d
    assert A.digest([("a", 1)]) == A.digest([("a", "1")]) and A.doc_text("x").startswith(b"EA Explorer")
    assert set(A.COMMANDS) == {"start", "snapshot", "after", "finish", "idle", "busy", "failed"}   # busy, failed: the drill (D747)


# ---------------------------------------------------------------- how eax reaches it, and the old suite gone
def test_eax_runs_it_in_every_form_and_the_old_suite_is_gone():
    sh = (REPO / "eax.sh").read_text()
    assert '*" backup-restore "*|*" restore "*|*" full "*|*" sonar "*) exec "$BASH" ./eaxpy.sh "$@"' in sh   # sonar: R8, D792
    ps1 = (REPO / "eax.ps1").read_text()
    assert '$RestArgs -contains "backup-restore" -or $RestArgs -contains "restore" -or $RestArgs -contains "full" -or $RestArgs -contains "sonar"' in ps1
    main = (REPO / "eaxcli/main.py").read_text()
    assert 'rest[:1] in (["backup-restore"], ["restore"])' in main and 'backup_restore.main([])' in main
    assert not (REPO / "services/api/eax/testing/restore_check.py").exists()
    run = (REPO / "services/api/eax/testing/run.py").read_text()
    assert "restore_check" not in run.replace("replaced restore_check.py", "")
    tr = (REPO / "services/ops/testruns.py").read_text()
    assert "def restore_agreed" not in tr and "eax test backup-restore" in tr
    assert "COPY brtest.py /app/brtest.py" in (REPO / "services/ops/Dockerfile").read_text()
    ops = (REPO / "services/ops/ops.py").read_text()
    assert 'if cmd == "brtest":' in ops and "brtest.bind(globals())" in ops
    fp = (REPO / "services/backup/fingerprint.sh").read_text()
    assert "\\gexec" in fp and "sha256sum" in fp and "./safety-backups/*" in fp
    help_ = (REPO / "eaxcli/help.txt").read_text()
    assert "backup|backup-restore|restore|" in help_ and "backup-restore  the backup and restore test" in help_


# ---------------------------------------------------------------- the fingerprint's SQL on a real database
def _psql():
    import os
    import shutil
    for p in ("psql", "/usr/lib/postgresql/16/bin/psql", "/usr/lib/postgresql/17/bin/psql"):
        if shutil.which(p) or os.path.exists(p):
            return shutil.which(p) or p
    return ""


@pytest.mark.skipif(not _psql() or not __import__("os").environ.get("EAX_JOBS_TEST_DSN"), reason="needs psql and a scratch PostgreSQL")
def test_the_fingerprint_sql_reads_every_table_the_same_whatever_the_row_order():
    import os
    import subprocess
    from urllib.parse import parse_qs, urlparse
    sql = (REPO / "services/backup/fingerprint.sh").read_text().split("<<'SQL'", 1)[1].split("\n", 1)[1].split("\nSQL\n", 1)[0]
    u = urlparse(os.environ["EAX_JOBS_TEST_DSN"].replace("postgresql+psycopg", "postgresql"))
    q = parse_qs(u.query)
    env = {**os.environ, "PGHOST": q.get("host", [u.hostname or ""])[0], "PGPORT": q.get("port", [str(u.port or 5432)])[0],
           "PGUSER": u.username or "postgres"}
    db = f"brt_{os.getpid()}"
    run = lambda d, s: subprocess.run([_psql(), "-X", "-q", "-At", "-F", " ", "-d", d], input=s, text=True,  # noqa: E731
                                      capture_output=True, env=env, check=True).stdout
    run("postgres", f"CREATE DATABASE {db};")
    try:
        run(db, "CREATE SCHEMA s; CREATE TABLE s.t (a int, b text); INSERT INTO s.t VALUES (1, 'x'), (2, 'y'); CREATE TABLE s.empty (a int);")
        one = run(db, sql)
        run(db, "DELETE FROM s.t; INSERT INTO s.t VALUES (2, 'y'), (1, 'x');")    # the same rows, another order
        assert run(db, sql) == one
        rows = dict((ln.split(" ")[0], ln.split(" ")[1:]) for ln in one.splitlines())
        assert rows["s.t"][0] == "2" and rows["s.empty"] == ["0", "d41d8cd98f00b204e9800998ecf8427e"]
        run(db, "UPDATE s.t SET b = 'z' WHERE a = 1;")
        assert run(db, sql) != one
    finally:
        run("postgres", f"DROP DATABASE {db};")


def test_fingerprint_sh_runs_to_the_end_with_no_database_on_its_own_server(tmp_path):
    """The owner's first run (16 Nov 2026, 17:08): "fingerprint.sh failed: T superset public.user_favorite_tag ...": with
    no database on a server of its own, the loop over them ended with 1 and set -e stopped the script after the last
    table. The real script, with psql stood in."""
    import os
    import shutil
    import subprocess
    if not shutil.which("sh") or not shutil.which("sha256sum"):
        pytest.skip("needs sh and sha256sum")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    for f in ("fingerprint.sh", "servers.sh"):
        shutil.copy(REPO / "services/backup" / f, bin_ / f)
    (bin_ / "psql").write_text("#!/bin/sh\ncase \"$*\" in *datname*) echo eaexplorer; echo superset;; "
                               "*) cat >/dev/null; echo 'public.t 2 abc';; esac\n")
    (bin_ / "psql").chmod(0o755)
    docs = tmp_path / "mayan"
    (docs / "media").mkdir(parents=True)
    (docs / "media" / "a file.pdf").write_text("x")
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "EAX_BACKUP_DOCS": str(docs),
           "EAX_BACKUP_TLS": str(tmp_path / "none"), "EAX_BACKUP_REPORTS": str(tmp_path / "none"),
           "EAX_BACKUP_IMPORTS": str(tmp_path / "none"), "EAX_BACKUP_EXPORTS": str(tmp_path / "none"),
           "EAX_BACKUP_PERSIST": str(tmp_path / "none"), "PGHOST": "db", "PGPORT": "5432"}
    for k in [k for k in env if k.endswith("_DB_URL") or k.endswith("_DB_HOST")]:
        env.pop(k)
    r = subprocess.run(["sh", str(bin_ / "fingerprint.sh")], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout
    out = _brtest().parse(r.stdout)
    assert out["tables"] == {"eaexplorer public.t": [2, "abc"], "superset public.t": [2, "abc"]}
    assert list(out["files"]) == ["documents/media/a file.pdf"]


def test_quiet_puts_the_maintenance_page_on_pauses_the_background_and_survives_the_restores(tmp_path, monkeypatch):
    """Owner, 16 Nov 2026, 19:28: "before we run this test let us put mantainance page and stop everything in background"."""
    import os
    b = _brtest()
    monkeypatch.setenv("EAX_WORK_MOUNT", str(tmp_path))
    flag = tmp_path / "proxy" / "maintenance"

    class Lock:
        def acquire(self, blocking=True):
            return True

        def release(self):
            pass

    def do_restore(name, what, by, version, force, rec):
        flag.unlink(missing_ok=True)                 # a restore ends its own maintenance page
        return {"status": "ok", "before": "x"}
    b.bind({"PROXY_FLAG": str(flag), "maintenance": lambda: None, "_block": Lock(), "RESTORE_WHAT": {"full": {}},
            "new_restore": lambda *a: ({"id": 1}, None), "_do_restore": do_restore})
    assert b.quiet("on", "test") == {"quiet": True, "page": True}
    assert b.is_quiet() and flag.exists() and (tmp_path / "quiet.json").exists()
    b.restore("B1", "full", "test", "5.6.0")
    assert flag.exists()                                   # the test's page stays up across the restore
    assert b.quiet("off", "test") == {"quiet": False, "page": False} and not b.is_quiet() and not flag.exists()
    b.quiet("on", "test")
    old = (tmp_path / "quiet.json")
    os.utime(old, (0, 0))
    assert not b.is_quiet()                                # a flag left by a test stopped hard is stale after 8 hours

    sys.path.insert(0, str(REPO / "services" / "api"))
    from eax import jobs, quiet
    monkeypatch.setattr(quiet, "path", lambda: str(tmp_path / "q.json"))
    t = jobs.app.tasks["eax.reports_refresh"]
    called = []
    monkeypatch.setattr("eax.reports.refresh_typed_views", lambda conn, wait="": called.append(1) or 0)
    (tmp_path / "q.json").write_text("{}")
    assert t.func(timestamp=0) is None and not called    # a recurring job misses its turn while quiet
    assert "timestamp" not in __import__("inspect").signature(jobs.app.tasks["eax.run_task"].func).parameters
    for f in ("updates.py", "commandcentre.py"):
        assert "brtest.is_quiet()" in (REPO / "services/ops" / f).read_text()


def test_a_database_dump_is_tried_again_and_its_failure_named(tmp_path):
    """The owner's run (16 Nov 2026, 19:26): B1 failed with only "pg_dump: detail: Query was: SELECT
    pg_catalog.pg_get_viewdef(...)": a report view was made again while pg_dump read it. Now a dump is tried three times
    and a failure's last line names the database and pg_dump's error."""
    import os
    import shutil
    import subprocess
    if not shutil.which("sh"):
        pytest.skip("needs sh")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "pg_dump").write_text(
        "#!/bin/sh\nn=$(cat \"$COUNT\" 2>/dev/null || echo 0); n=$((n+1)); echo $n > \"$COUNT\"\n"
        "if [ $n -le \"$FAILS\" ]; then echo 'pg_dump: error: query failed: ERROR:  could not open relation with OID 24192' >&2;"
        " echo 'pg_dump: detail: Query was: SELECT pg_catalog.pg_get_viewdef(24192)' >&2; exit 1; fi\n"
        "for a in \"$@\"; do case $a in --file=*) echo dump > \"${a#--file=}\";; esac; done\n")
    (bin_ / "pg_dump").chmod(0o755)
    script = f". {REPO / 'services/backup/dumpdb.sh'}; dumpdb eaexplorer {tmp_path / 'e.dump'}"
    for fails, ok in ((2, True), (3, False)):
        (tmp_path / "count").unlink(missing_ok=True)
        env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "COUNT": str(tmp_path / "count"), "FAILS": str(fails),
               "EAX_DUMP_RETRY_SECONDS": "0"}
        r = subprocess.run(["sh", "-c", script], env=env, capture_output=True, text=True, timeout=60)
        assert (r.returncode == 0) is ok, r.stderr
        assert "try 2 of 3" in r.stdout and (tmp_path / "count").read_text().strip() == "3"
        if ok:
            assert (tmp_path / "e.dump").read_text() == "dump\n"
        else:
            assert r.stderr.strip().splitlines()[-1] == ("backup: database eaexplorer could not be dumped (3 tries): "
                                                         "pg_dump: error: query failed: ERROR:  could not open relation with OID 24192")
    assert 'dumpdb "$DB" "$TARGET/databases/$DB.dump"' in (REPO / "services/backup/backup.sh").read_text()


def test_a_tools_message_is_not_a_failure_and_new_folders_are_made_while_quiet():
    """The owner's run (16 Nov 2026, 21:11): "FAIL made: a project step: Step added to phase A ..." (a tool's message read
    as an error), and "a document with its file: The project's repository is not built yet in Documents" (the job that
    makes a new document class's folder was paused with the rest)."""
    sys.path.insert(0, str(REPO / "services" / "api"))
    from eax import jobs
    from eax.testing import backup_restore as A
    assert A._err({"message": "Step added to phase A: self_test_x step."}) == ""
    assert A._err({"error": "No such project"}) == "No such project" and A._why({"message": "done"}) == "done"
    assert not hasattr(jobs.app.tasks["eax.project_repositories"].func, "__wrapped__")     # runs while quiet
    assert hasattr(jobs.app.tasks["eax.reports_refresh"].func, "__wrapped__")               # waits while quiet
