"""R5.4 (owner, 15 Nov 2026, 11:07, D687: "we just need to have a base folder's we put in then users can mount whatever
they want if they want for example DB wont live on NAS but logs or docuemnts may"): one base folder (EAX_DATA_ROOT), a
fixed folder per kind under it, checked before containers are made, in all three forms of eax."""

import os
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from eaxcli import core, logkeep  # noqa: E402
from eaxcli import datafolders as F  # noqa: E402

KINDS = {"EAX_DATA_DIR": "databases", "EAX_DOCS_DIR": "documents", "EAX_LOGS_DIR": "logs", "EAX_BACKUP_DIR": "backups",
         "EAX_IMPORT_DIR": "imports", "EAX_EXPORT_DIR": "exports", "EAX_TLS_DIR": "certificates",
         "EAX_REPORTS_DIR": "reports"}


def getter(d):
    return lambda k: d.get(k, "")


def test_every_kind_goes_under_the_base_folder():
    base, places = F.resolve(getter({"EAX_DATA_ROOT": "/srv/eax"}), windows=False)
    assert base == "/srv/eax"
    assert {p.key: p.value for p in places} == {k: f"/srv/eax/{f}" for k, f in KINDS.items()}
    assert all(p.source == "base" for p in places)


def test_without_a_base_folder_nothing_changes():
    base, places = F.resolve(getter({"EAX_DATA_DIR": "eax-pgdata", "EAX_IMPORT_DIR": "./work/data/imports"}), windows=False)
    assert base == "" and F.env_lines(places) == []
    assert {p.key: p.source for p in places}["EAX_IMPORT_DIR"] == "own"     # the laptop's own folder, as before


def test_a_folder_of_its_own_wins_and_volumes_and_work_defaults_are_replaced():
    cfg = {"EAX_DATA_ROOT": "/srv/eax", "EAX_LOGS_DIR": "/mnt/nas/eax-logs", "EAX_DATA_DIR": "eax-pgdata",
           "EAX_IMPORT_DIR": "./work/data/imports"}
    _, places = F.resolve(getter(cfg), windows=False)
    by = {p.key: p for p in places}
    assert by["EAX_LOGS_DIR"].value == "/mnt/nas/eax-logs" and by["EAX_LOGS_DIR"].source == "own"
    assert by["EAX_DATA_DIR"].value == "/srv/eax/databases"        # a Docker volume's name: the base folder decides
    assert by["EAX_IMPORT_DIR"].value == "/srv/eax/imports"        # the laptop template's work/ folder: likewise
    assert "EAX_LOGS_DIR=/mnt/nas/eax-logs" not in F.env_lines(places)   # already in the config file


def test_windows_keeps_the_databases_in_their_volume():
    _, places = F.resolve(getter({"EAX_DATA_ROOT": "D:\\eax"}), windows=True)
    by = {p.key: p for p in places}
    assert by["EAX_DATA_DIR"].source == "volume" and "PostgreSQL" in by["EAX_DATA_DIR"].note
    assert by["EAX_DOCS_DIR"].value == "D:\\eax\\documents"


def test_folders_are_made_checked_and_said(tmp_path):
    base = tmp_path / "data"
    base.mkdir()
    _, places = F.resolve(getter({"EAX_DATA_ROOT": str(base)}), windows=False)
    ok, checks = F.check(str(base), places)
    assert ok and all((base / f).is_dir() for f in KINDS.values())
    text = F.table(str(base), checks)
    assert "GB free" in text and ("own disk" in text or "mounted at" in text)


def test_a_missing_base_folder_stops_the_start(tmp_path):
    missing = tmp_path / "nowhere"
    _, places = F.resolve(getter({"EAX_DATA_ROOT": str(missing)}), windows=False)
    ok, checks = F.check(str(missing), places)
    assert not ok and "is not there" in checks[0].said and not missing.exists()     # never made: it may be a mount


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="root writes anywhere")
def test_a_folder_that_cannot_be_written_stops_the_start(tmp_path):
    base = tmp_path / "data"
    (base / "logs").mkdir(parents=True)
    (base / "logs").chmod(0o500)
    try:
        _, places = F.resolve(getter({"EAX_DATA_ROOT": str(base)}), windows=False)
        ok, checks = F.check(str(base), places)
        assert not ok and any("cannot be written" in c.said for c in checks)
    finally:
        (base / "logs").chmod(0o700)


def test_where_a_folder_is_never_stops_it(tmp_path):
    """D687: EA Explorer does not decide what is mounted where."""
    src = (REPO / "eaxcli/datafolders.py").read_text()
    assert "own disk" in src and "refuse" not in src.split("def check")[1].split("def table")[0].lower()


def test_show_does_not_make_folders(tmp_path):
    base = tmp_path / "data"
    base.mkdir()
    _, places = F.resolve(getter({"EAX_DATA_ROOT": str(base)}), windows=False)
    ok, checks = F.check(str(base), places, make=False)
    assert ok and not (base / "logs").exists() and "made at the next start" in checks[0].said


def test_compose_gives_the_containers_the_folders_and_reports_its_own():
    c = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    assert set(c["x-folders"]) == {"EAX_DATA_ROOT", *KINDS}
    for name, svc in c["services"].items():
        if "env_file" in svc:
            assert set(KINDS) <= set(svc.get("environment") or {}), name
    vols = [v for s in ("reports", "reports-init", "backup") for v in c["services"][s]["volumes"]]
    assert any(v.startswith("${EAX_REPORTS_DIR:-eax-superset-home}:") for v in vols)


def test_every_form_resolves_the_folders_before_containers_are_made():
    sh = (REPO / "eax.sh").read_text()
    ps = (REPO / "eax.ps1").read_text()
    assert "up|run|create) folders_env || return 1" in sh and '"$ROOT/eaxpy.sh" folders env' in sh
    assert '@("up", "run", "create") -contains $Arguments[0]) { Use-DataFolders }' in ps and '"eaxpy.ps1") folders env' in ps
    assert "folders_env()" in (REPO / "eaxcli/core.py").read_text().split("def compose_args")[1].split("def _compose_base")[0]
    assert 'certs|deploy|secrets|packs|schedule|persist|folders|' in sh and '"persist", "folders"' in ps
    assert "### folders" in (REPO / "eaxcli/help.txt").read_text()


def test_python_form_puts_the_values_in_its_environment(tmp_path, monkeypatch):
    base = tmp_path / "data"
    base.mkdir()
    for k in ["EAX_FOLDERS_RESOLVED", *KINDS]:
        monkeypatch.setenv(k, "")                 # so the values folders_env sets are taken back after the test
    monkeypatch.setenv("EAX_DATA_ROOT", str(base))
    monkeypatch.setattr(core, "say", lambda *a, **k: None)
    core.folders_env()
    assert os.environ["EAX_LOGS_DIR"] == f"{base}/logs" and os.environ["EAX_FOLDERS_RESOLVED"] == "1"


def test_python_form_stops_on_a_missing_base_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("EAX_FOLDERS_RESOLVED", "")
    monkeypatch.setenv("EAX_DATA_ROOT", str(tmp_path / "nowhere"))
    monkeypatch.setattr(core, "say", lambda *a, **k: None)
    with pytest.raises(core.Failure, match="nothing was started"):
        core.folders_env()


def test_the_logs_folder_follows_the_base_folder(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    (tmp_path / "work/eaexplorer.env").write_text("EAX_DATA_ROOT=/srv/eax\n")
    monkeypatch.delenv("EAX_LOGS_DIR", raising=False)
    monkeypatch.delenv("EAX_DATA_ROOT", raising=False)
    assert str(logkeep.folder(tmp_path)).replace("\\", "/") == "/srv/eax/logs"


def test_init_server_asks_for_the_base_folder_in_every_form():
    tpl = (REPO / "deploy/templates/eaexplorer.server.env").read_text()
    assert "\nEAX_DATA_ROOT=/srv/eax\n" in tpl and "\nEAX_DATA_DIR=\n" in tpl
    assert "\nEAX_DATA_ROOT=\n" in (REPO / "deploy/templates/eaexplorer.laptop.env").read_text()
    assert "_ask_base_folder()" in (REPO / "eaxcli/main.py").read_text()
    # every form's init is the Python one since Release 6 (R6-C1: it also asks certificate or password), so the
    # question is asked in one place for all of them
    assert '"init", "certs", "deploy"' in (REPO / "eax.ps1").read_text() and "Set-BaseFolder" not in (REPO / "eax.ps1").read_text()
    assert 'init)\n    # R6-C1' in (REPO / "eax.sh").read_text() and 'exec "$BASH" ./eaxpy.sh "$@" ;;' in (REPO / "eax.sh").read_text()


def test_init_server_writes_the_base_folder(tmp_path, monkeypatch):
    from eaxcli import main
    env = tmp_path / "eaexplorer.env"
    env.write_text("A=1\nEAX_DATA_ROOT=/srv/eax\nB=2\n")
    monkeypatch.setattr(main, "ENV_FILE", env)
    monkeypatch.setattr(main, "say", lambda *a, **k: None)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    main._ask_base_folder()
    assert env.read_text() == "A=1\nEAX_DATA_ROOT=/srv/eax\nB=2\n"
