"""What can take EA Explorer down for a moment runs only when an admin chooses it (the owner, 18 Nov 2026, 10:18 to 10:21:
"not sure how or why the application went to mantainance", "I didnt ask", "ensure its not restarting like this when it
feels. The user needs to be able to enable the key rotation and all these schedules as one of the initial configuration
tasks").

On his laptop, "Check the integrity now" found a safe fix, took a backup to make it, and the backup put the maintenance
page up and waited up to half an hour for the background, which held the very check that asked for it.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services" / "ops"))


def test_check_now_only_checks_and_fixes_wait_for_a_yes_or_the_setting(monkeypatch):
    from eax import dbintegrity as D
    found = {"findings": [{"key": "sequence", "level": "warning", "database": "eaexplorer", "what": "behind",
                           "action": "moved on"}], "databases": ["eaexplorer"], "seconds": 1}
    monkeypatch.setattr(D, "check", lambda: found)
    monkeypatch.setattr(D.dm, "record", lambda *a, **k: None)
    monkeypatch.setattr(D, "_tell", lambda *a, **k: None)
    monkeypatch.setattr(D, "backed_up_recently", lambda: False)
    monkeypatch.setattr(D, "safe_fixes", lambda safe: [{"what": "moved on", "status": "done"}])
    backups = []
    monkeypatch.setattr(D, "fixes_by_themselves", lambda conn: False)
    out = D.run(None, "eaadmin", backup=lambda by: backups.append(by))              # Check now, the weekly run: setting off
    assert backups == [] and out["actions"] == []
    out = D.run(None, "eaadmin", backup=lambda by: backups.append(by), fix=True)    # Fix the safe ones
    assert backups == ["eaadmin"] and out["actions"]
    monkeypatch.setattr(D, "fixes_by_themselves", lambda conn: True)                # switched on
    assert D.run(None, "schedule", backup=lambda by: backups.append(by))["actions"]


def test_the_safe_fixes_setting_is_off_until_chosen():
    from eax import settings as S
    assert S.REGISTRY["integrity_fixes"][3] is False


def test_a_backup_never_waits_for_the_integrity_check_that_asked_for_it():
    src = (REPO / "services/api/eax/testing/backup_restore.py").read_text()
    assert "NOT starts_with(task_name, 'eax.db_integrity')" in src


def test_rotating_when_due_is_off_until_chosen_and_the_first_run_asks():
    import commandcentre as CC
    rot = next(s for s in CC.SYSTEM_SCHEDULES if s["id"] == "r6rotate")
    assert rot["enabled"] is False
    # "For now disable key and certificate rotation by default until this is fully tested" (10:58)
    assert next(s for s in CC.SYSTEM_SCHEDULES if s["id"] == "r6certs")["enabled"] is False
    from eax import first_run as F
    assert "upkeep" in [s[0] for s in F.STEPS]
    web = REPO / "services/web/src"
    assert "<UpkeepChoices />" in (web / "GuidedWizards.jsx").read_text()
    assert "<UpkeepChoices cleanup />" in (web / "CommandCentre.jsx").read_text()   # with Clean up now (D825)
    up = (web / "Upkeep.jsx").read_text()
    assert "schedules/r6rotate/" in up and '"secrets", "schedule"' in up and "integrity_fixes" in up
    jsx = (web / "DbIntegrity.jsx").read_text()
    assert "JSON.stringify({ fix, accept_maintenance: fix })" in jsx and "Fix the safe ones" in jsx



# ---------------------------------------------------------------- the maintenance page only on a yes (10:32)
def test_what_puts_the_maintenance_page_up_is_known_from_the_command():
    """"Anything that will bring up mantaiance page needs to show a warning and user to accept it"."""
    from eax.api.maintenance_gate import LATER, argv_says
    for argv in (["backup"], ["restore", "latest"], ["update"], ["secrets", "rotate", "--all"], ["db", "integrity", "--fix"],
                 ["restart"], ["maintenance", "on"], ["test", "backup-restore"]):
        assert argv_says(argv), argv
    assert argv_says(["secrets", "schedule", "monthly"])[1] == LATER
    for argv in (["status"], ["secrets", "rotate", "EAX_DB_PASSWORD"], ["db", "integrity"], ["maintenance", "off"],
                 ["update", "--status"], ["secrets", "schedule", "off"]):
        assert argv_says(argv) is None, argv


def test_every_way_in_asks_and_the_screens_send_the_yes():
    api = REPO / "services/api/eax/api"
    gated = {"backups.py": ["A backup of the whole installation", "A restore", "Scheduled backups"],
             "updates.py": ["An update", "A roll back", "The update, tried again"],
             "admin.py": ["Rotate all", "The database's safe fixes", "Database safe fixes by themselves"],
             "command_centre.py": ["argv_needs_yes(data, data.get(\"argv\")", "scheduled=True", "scheduled=what == \"on\""]}
    for f, says in gated.items():
        src = (api / f).read_text()
        for s in says:
            assert s in src, (f, s)
    auth = (REPO / "services/web/src/auth.js").read_text()
    assert "response.status === 428 && body.errors?.accept_maintenance" in auth and "accept_maintenance: true" in auth


def test_the_gate_refuses_without_the_yes_and_lets_it_through_with_it():
    import pytest
    from werkzeug.exceptions import HTTPException

    from eax.api.maintenance_gate import needs_yes
    with pytest.raises(HTTPException) as e:
        needs_yes({}, "A backup of the whole installation")
    assert e.value.code == 428
    assert needs_yes({"accept_maintenance": True}, "A backup") is None


# ---------------------------------------------------------------- EAX_HOSTNAME (10:16, 10:32)
def test_the_hostname_is_checked_and_written(monkeypatch, tmp_path):
    import pytest
    sys.path.insert(0, str(REPO))
    from eaxcli import hostname as H
    from eaxcli.core import Failure
    assert H.valid("EA.Example.org.") == "ea.example.org" and H.valid("localhost") == "localhost"
    for bad in ("https://ea.example.org", "ea.example.org:443", "ea example", "-ea.example.org", ""):
        with pytest.raises(Failure):
            H.valid(bad)
    env = tmp_path / "eaexplorer.env"
    env.write_text("EAX_DEPLOYMENT=server\nEAX_HOSTNAME=ea.example.org\n")
    monkeypatch.setattr(H, "ENV_FILE", env)
    import eaxcli.secrets as sec
    monkeypatch.setattr(sec, "dated_copy", lambda text: tmp_path / "copy")
    assert H.set_name("ea.thotnr.co.za") == "ea.thotnr.co.za"
    assert "EAX_HOSTNAME=ea.thotnr.co.za" in env.read_text()
    assert H.addresses("ea.thotnr.co.za")[1] == "https://reports.ea.thotnr.co.za"



def test_rotation_and_renewal_switched_off_where_they_were_on_unless_an_admin_chose_them(monkeypatch, tmp_path):
    import commandcentre as CC

    class Store:
        items = [{"id": "r6rotate", "enabled": True, "system": True}, {"id": "r6certs", "enabled": True, "chosen": True,
                                                                       "system": True}, {"id": "x1", "enabled": True}]

        def path(self):
            return tmp_path / "s.json"

        def load(self):
            return self.items, ""

        def save(self, items):
            self.items = items
    (tmp_path / "s.json").write_text("[]")
    st = Store()
    monkeypatch.setattr(CC, "S", st)
    CC.ensure_system_schedules()
    by = {s["id"]: s["enabled"] for s in st.items}
    assert by == {"r6rotate": False, "r6certs": True, "x1": True, "r12tests": False}                  # an admin's choice kept
    up = (REPO / "services/web/src/Upkeep.jsx").read_text()
    assert "schedules/r6certs/" in up
    assert 's["chosen"] = True' in (REPO / "eaxcli/schedules.py").read_text()


def test_a_log_held_open_by_the_powershell_form_never_stops_the_command(monkeypatch, tmp_path):
    """The owner, 18 Nov 2026, 11:13: `.\\eax maintenance clear` stopped at "PermissionError: ... -maintenance.log": the
    PowerShell form had the log of the same name open while it handed the command to eaxpy."""
    sys.path.insert(0, str(REPO))
    import builtins

    from eaxcli import core
    monkeypatch.setattr(core, "LOG_DIR", tmp_path)
    monkeypatch.setattr(core, "STAMP", "20261118-111326")
    real = builtins.open

    def locked(p, *a, **k):
        if str(p).endswith("-maintenance.log"):
            raise PermissionError(13, "Permission denied", str(p))
        return real(p, *a, **k)
    monkeypatch.setattr(builtins, "open", locked)
    core.start_log("maintenance", ["clear"])
    assert core._log["path"].name == "eax-20261118-111326-maintenance-py.log"
    core._log["file"].close()
    core._log["file"] = None


def test_restart_takes_away_a_maintenance_page_left_behind(monkeypatch, tmp_path):
    """The owner, 18 Nov 2026, 11:50: "eax restart should remove mantainance page if any"."""
    sys.path.insert(0, str(REPO))
    from eaxcli import main as M
    (tmp_path / "work" / "proxy").mkdir(parents=True)
    (tmp_path / "work" / "proxy" / "maintenance").write_text("x")
    (tmp_path / "work" / "quiet.json").write_text("{}")
    monkeypatch.setattr(M, "ROOT", tmp_path)
    monkeypatch.setattr(M, "WORK", tmp_path / "work")
    steps = []
    monkeypatch.setattr(M, "run_self", lambda s: steps.append((s, (tmp_path / "work" / "quiet.json").exists())) or 0)
    assert M.restart(False) == 0
    assert steps == [(["down"], True), (["up"], False)]                       # gone after down, before up
    assert not (tmp_path / "work" / "proxy" / "maintenance").exists()
    ps, sh = (REPO / "eax.ps1").read_text(), (REPO / "eax.sh").read_text()
    for t in (ps, sh):
        assert "work/proxy/maintenance" in t and "work/quiet.json" in t
