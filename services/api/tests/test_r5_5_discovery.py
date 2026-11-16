"""R5.5 enterprise discovery, the code (runs anywhere; the whole run on a real database is in
test_r5_5_discovery_on_a_real_database.py). The owner's design (15 Nov 2026, 20:11 to 20:28): EA Explorer is the source
and sink; the people's own AI runs discovery through MCP."""
import ast
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
WEB = REPO / "services/web/src"


class U:
    def __init__(self, name, roles):
        self.username, self.roles, self.break_glass = name, tuple(roles), False


def test_every_kind_of_source_the_owner_agreed_is_there():
    from eax import discovery_projects as dp
    wanted = {"mailbox", "folder", "ftp", "sftp", "sharepoint", "git", "wiki", "tickets", "chat", "database",
              "cloud-storage", "cloud-account", "recordings"}                 # owner, 20:26: "All of them in 5.5"
    assert wanted <= set(dp.KINDS)
    assert set(dp.SIGN_INS) == {"none", "key", "basic", "certificate", "sso"}


def test_the_schedule_marks_when_a_run_is_due():
    from eax import discovery_projects as dp
    from eax.metamodel_edit import EditError
    mon = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)                    # a Monday
    assert dp.next_due("none", 1, "02:00", mon) is None
    assert dp.next_due("daily", 1, "02:00", mon) == datetime(2026, 11, 17, 2, 0, tzinfo=UTC)
    assert dp.next_due("daily", 1, "11:30", mon) == datetime(2026, 11, 16, 11, 30, tzinfo=UTC)
    assert dp.next_due("weekly", 3, "02:00", mon) == datetime(2026, 11, 18, 2, 0, tzinfo=UTC)   # Wednesday
    assert dp.next_due("weekly", 1, "02:00", mon) == datetime(2026, 11, 23, 2, 0, tzinfo=UTC)   # next Monday
    assert dp.next_due("monthly", 28, "02:00", datetime(2026, 12, 29, tzinfo=UTC)) == datetime(2027, 1, 28, 2, 0, tzinfo=UTC)
    for bad in (("weekly", 8, "02:00"), ("monthly", 31, "02:00"), ("daily", 1, "25:00"), ("hourly", 1, "02:00")):
        with pytest.raises(EditError):
            dp.next_due(*bad, mon)


def test_due_overdue_and_running():
    from eax import discovery_projects as dp
    now = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
    assert dp.due_state(None, False, now) == ""
    assert dp.due_state(now + timedelta(minutes=5), False, now) == ""
    assert dp.due_state(now - timedelta(minutes=30), False, now) == "due"
    assert dp.due_state(now - timedelta(hours=3), False, now) == "overdue"
    assert dp.due_state(now - timedelta(hours=3), True, now) == "running"
    assert dp.schedule_text({"schedule": "weekly", "schedule_day": 5, "schedule_time": "03:00"}) == "Every Friday at 03:00"


def test_only_discovery_admins_and_super_admins_set_up():
    from eax import discovery_projects as dp
    from eax.metamodel_edit import EditError
    assert dp.may_manage(U("d", ["discovery-admin"])) and dp.may_manage(U("s", ["super-admin"]))
    assert not dp.may_manage(U("u", ["user", "architecture-board"]))
    with pytest.raises(EditError) as e:
        dp.test_link(U("u", ["user"]), "git", "https://git.example.com", "none")
    assert e.value.status == 403


def test_test_the_link_forgets_the_sign_in(monkeypatch):
    from eax import discovery_projects as dp
    seen = {}

    def fake(url, sign_in, secret):
        seen.update(secret)
        return True, "It answered (200)."
    monkeypatch.setattr(dp, "_http", fake)
    secret = {"token": "s3cr3t-value"}
    out = dp.test_link(U("d", ["discovery-admin"]), "sharepoint", "https://example.sharepoint.com/sites/a", "sso", secret)
    assert out["ok"] and seen == {"token": "s3cr3t-value"}
    assert "s3cr3t" not in str(out) and "forgotten" in out["kept"]


def test_test_the_link_says_when_nothing_answers():
    from eax import discovery_projects as dp
    out = dp.test_link(U("d", ["discovery-admin"]), "sftp", "sftp://127.0.0.1:1/x", "basic", {"username": "a", "password": "b"})
    assert out["ok"] is False and "did not answer" in out["note"]


def test_the_sign_in_is_never_kept_anywhere():
    import re
    sql = re.sub(r"--[^\n]*", "", (API / "migrations/sql/0094_r5_5_discovery_projects.sql").read_text()).lower()
    for word in ("password", "secret", "token", "private_key"):
        assert word not in sql                                             # no column can hold a sign-in
    api = (API / "eax/api/discovery_projects.py").read_text()
    assert 'k != "secret"' in api and "secret.clear()" in api            # never stored with a source, cleared after the test


def test_the_migration_adds_the_role_and_the_tables():
    sql = (API / "migrations/sql/0094_r5_5_discovery_projects.sql").read_text()
    assert "'discovery-admin'" in sql and "'eax-discovery-admin'" in sql
    for t in ("discovery_projects", "discovery_resources", "discovery_runs", "discovery_found_in", "discovery_skipped",
              "discovery_maybe_same", "discovery_not_found"):
        assert f"core.{t}" in sql
    assert "CREATE TRIGGER" not in sql.upper() and "CREATE FUNCTION" not in sql.upper()   # D248
    py = (API / "migrations/versions/0094_r5_5_discovery_projects.py").read_text()
    assert 'down_revision = "0093_r5_5_1_decisions"' in py


def test_the_ai_runs_it_through_mcp_tools():
    tree = ast.parse((API / "eax/mcp_discovery.py").read_text())
    tools = {f.name for f in tree.body if isinstance(f, ast.AsyncFunctionDef)}
    assert {"run_discovery_project", "discovery_projects_due", "discovery_record_found", "discovery_report_skipped",
            "discovery_finish_run", "discovery_run_report", "discovery_log_decision", "discovery_projects"} <= tools
    from eax import mcp_catalogue
    assert mcp_catalogue.AREAS["mcp_discovery"] == "Enterprise discovery"
    assert "mcp_discovery" in (API / "eax/mcp_server.py").read_text()


def test_the_guide_respects_not_for_ai_and_asks_before_a_run():
    from eax import discovery_projects as dp
    assert dp.NOT_FOR_AI in dp.RUN_GUIDE and "discovery_report_skipped" in dp.RUN_GUIDE
    assert "AI agent on behalf of" in (API / "eax/discovery_projects.py").read_text()


def test_overdue_runs_raise_an_alert():
    from eax import alerts
    assert "discovery_overdue" in alerts.DEFAULTS
    assert "discovery_projects.overdue_count" in (API / "eax/alerts.py").read_text()


def test_the_screens_route_menu_tab_and_help():
    app = (WEB / "App.jsx").read_text()
    assert 'route.startsWith("#/discovery-projects")' in app
    assert '"#/discovery-projects"' in (WEB / "menu.js").read_text()
    mv = (WEB / "ModelViews.jsx").read_text()
    assert '["found", "Found in"]' in mv and "<FoundIn" in mv
    page = (WEB / "DiscoveryProjects.jsx").read_text()
    assert "Test the link" in page and "setSecret({})" in page and "rel=\"noopener noreferrer\"" in page
    import json
    help_ = json.loads((WEB / "help/catalogue.json").read_text())
    assert "page:#/discovery-projects" in help_ and "tab:Found in" in help_
    from eax.testing import ui_pages
    assert "#/discovery-projects" in ui_pages.SEEDS


def test_only_a_live_working_model_may_be_the_target():
    """Owner, 16 Nov 2026, 13:58: "Setting up discovery we should not show Library frozen and read only models"."""
    from eax import discovery_projects as dp
    ok = {"name": "Claims", "kind": "project", "lifecycle": "active", "lock_level": "none", "is_locked": False, "frozen_at": None}
    assert dp.target_refused(ok) == ""
    assert "library model" in dp.target_refused({**ok, "kind": "reference"})
    assert "root metamodel" in dp.target_refused({**ok, "kind": "template"})
    assert "frozen" in dp.target_refused({**ok, "frozen_at": "2026-11-01"})
    assert "archived" in dp.target_refused({**ok, "lifecycle": "archived"})
    assert "read only" in dp.target_refused({**ok, "lock_level": "content"})
    assert "locked" in dp.target_refused({**ok, "is_locked": True})


def test_the_screen_offers_only_those_and_a_new_model_button():
    """Owner, 13:58: "Give a button to create a new model from here itself"."""
    page = (WEB / "DiscoveryProjects.jsx").read_text()
    assert 'm.kind === "project" && !m.is_locked && (m.lock_level || "none") === "none"' in page and "liveModels(list)" in page
    assert "＋ New model" in page and "<NewModelDialog" in page and 'set("target_model", m.id)' in page
    ops = (WEB / "ModelOps.jsx").read_text()
    assert "onCreated = null" in ops and "if (onCreated) onCreated(out.model);" in ops
    assert "else go(`/${admin ? \"model-admin\" : \"metamodel\"}/${out.model.id}`);" in ops   # elsewhere as before
