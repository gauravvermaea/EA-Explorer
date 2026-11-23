"""R5.12 (owner, 14 Nov 2026: "Database mantainance, the application checkes the dB and does mantainance of the dB vaccine
analysis clearing logs and so on Lock resolution etc"; 15 Nov 2026, D691: "1 + find what else is needed")."""

import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))

from eax import dbmaint as D  # noqa: E402
from eax import settings as st  # noqa: E402
from eax.metamodel_edit import EditError  # noqa: E402


def test_the_tidy_does_what_the_check_found_and_never_locks():
    found = [D.finding("eax", "bloat", "warning", "x", "", "", "core.entities"),
             D.finding("eax", "stale_stats", "info", "x", "", "", "core.models"),
             D.finding("eax", "invalid_index", "warning", "x", "", "", 'core."odd""name"'),
             D.finding("kc", "wraparound", "critical", "x", ""),
             D.finding("eax", "unused_index", "info", "x", "", "", "core.i")]          # a person decides: not done
    plan = D.tidy(found, dry_run=True)
    sql = [p["sql"] for p in plan]
    assert sql == ['VACUUM (ANALYZE) "core"."entities"', 'ANALYZE "core"."models"',
                   'REINDEX INDEX CONCURRENTLY "core"."odd""name"', "VACUUM (FREEZE, ANALYZE)"]
    assert not any("FULL" in s for s in sql)                              # VACUUM FULL only by a person (compact)


def test_confirmations_are_signed_and_expire(monkeypatch):
    monkeypatch.setenv("EAX_OPS_TOKEN", "k1")
    t = D.make_token({"pid": 42, "end": True})
    assert D.read_token(t) == {"pid": 42, "end": True}
    with pytest.raises(ValueError, match="expired"):
        D.read_token(t, now=time.time() + D.CONFIRM_SECONDS + 5)
    with pytest.raises(ValueError, match="not one of ours"):
        D.read_token(t[:-2] + "00")
    monkeypatch.setenv("EAX_OPS_TOKEN", "other")
    with pytest.raises(ValueError):
        D.read_token(t)                                                     # another installation's: refused


def test_the_window_may_cross_midnight():
    at = lambda h, m: datetime(2026, 1, 1, h, m)                            # noqa: E731
    assert D.in_window(at(2, 0), "01:00", "05:00") and not D.in_window(at(5, 0), "01:00", "05:00")
    assert D.in_window(at(0, 30), "23:00", "03:00") and D.in_window(at(23, 30), "23:00", "03:00")
    assert not D.in_window(at(12, 0), "23:00", "03:00")


def test_its_settings_are_checked():
    assert st.default_of("db_maint_window_start") == "01:00" and st.default_of("db_idle_tx_minutes") == 30
    with pytest.raises(EditError):
        st.check("db_maint_window_start", "25:00")
    assert st.check("db_maint_window_end", "04:30") == "04:30"


def test_it_runs_by_itself_on_the_web_and_on_the_command_line():
    jobs = (REPO / "services/api/eax/jobs.py").read_text()
    for name in ("eax.db_check", "eax.db_tidy", "eax.db_idle_sessions"):
        assert f'name="{name}"' in jobs
    assert "dbmaint.busy_reason()" in jobs
    admin = (REPO / "services/api/eax/api/admin.py").read_text()
    assert '"/admin/db-maintenance"' in admin and "compact-preview" in admin and "stop-preview" in admin
    assert '"python", "-m", "eax.dbmaint"' in (REPO / "eaxcli/db_cli.py").read_text()
    assert "|db|" in (REPO / "eax.sh").read_text() and '"verify", "db"' in (REPO / "eax.ps1").read_text()
    assert "### db " in (REPO / "eaxcli/help.txt").read_text()
    sql = (REPO / "services/api/migrations/sql/0081_r5_db_maintenance.sql").read_text()
    assert "core.db_maintenance_runs" in sql and "FUNCTION" not in sql
    assert '{ key: "db-maintenance", label: "Database maintenance' in (REPO / "services/web/src/adminNav.js").read_text()   # System Admin's pages and menu: adminNav.js (D898)


def test_what_else_is_checked():
    """D691 "find what else is needed": beyond the proposal, these are checked too."""
    src = (REPO / "services/api/eax/dbmaint.py").read_text()
    for key in ("sequence", "no_primary_key", "invalid_index", "replication", "settings", "wraparound", "duplicate_index"):
        assert f'"{key}"' in src
