"""Release 14: the fixes for what the full test of 24 Nov 2026 found (owner, 24 Nov 2026, 05:41: "start 1-4"; 05:47:
"Please fix all bugs too"). One test, or more, for each fix."""

import ast
import re
import smtplib
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
API = REPO / "services/api"
WEB = REPO / "services/web/src"
sys.path.insert(0, str(REPO))


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- 1. the MCP modules import each other only when called
def test_no_mcp_module_imports_another_at_its_top_but_the_server():
    """mcp_scenarios imported alone broke: it imports mcp_server, which imports mcp_scenario_planning, which imported
    _proj from the half-loaded mcp_scenarios. Only mcp_server (where `mcp` is) may be imported at a module's top."""
    bad = []
    for f in sorted((API / "eax").glob("mcp_*.py")):
        for node in ast.parse(_read(f)).body:                       # top level only: imports inside functions are fine
            if isinstance(node, ast.ImportFrom) and node.level == 1 and (node.module or "").startswith("mcp_") \
                    and node.module != "mcp_server":
                bad.append(f"{f.name}: from .{node.module} import ...")
    assert bad == [], bad


def test_scenario_planning_reaches_the_project_wrapper_when_a_tool_runs():
    src = _read(API / "eax/mcp_scenario_planning.py")
    assert "async def _proj(*args, **kwargs):" in src and "from .mcp_scenarios import _proj as proj" in src


# ---------------------------------------------------------------- 1. MCP probes: each parameter its own type
def _tool(name, params):
    return {"name": name, "params": [{"name": n, "type": t, "required": True} for n, t in params]}


def test_a_tool_pointed_at_nothing_keeps_a_number_and_a_set_of_fields_as_their_own_type():
    from eax.testing import mcp_check as m
    step = _tool("complete_project_step", [("project", "str"), ("step", "int")])
    assert m.missing_ids(step) == {"project": m.MISSING}                 # the step stays a number
    item = _tool("draft_set_item", [("draft", "str"), ("section", "str"), ("item", "dict")])
    assert m.missing_ids(item) == {"draft": m.MISSING}                   # the item stays a set of fields
    args = {**m.change_arguments(item, {}), **m.missing_ids(item)}
    assert isinstance(args["item"], dict) and args["draft"] == m.MISSING


def test_a_tool_with_nothing_to_point_at_nothing_is_not_called():
    from eax.testing import mcp_check as m
    assert m.missing_ids(_tool("x", [("step", "int"), ("text", "str")])) == {}
    src = _read(API / "eax/testing/mcp_check.py")
    assert "if not missing_ids(t):" in src


def test_the_tools_that_need_a_kind_of_project_may_say_the_project_is_not_one():
    from eax.testing import mcp_check as m
    assert {"sp_work_out", "agile_overview"} <= m.MAY_SAY_NONE


# ---------------------------------------------------------------- 1. the SQL window's logins may sign in
class _SQL:
    def __init__(self, s, parts=()):
        self.s, self.parts = s, parts

    def format(self, *parts):
        return _SQL(self.s, parts)

    def render(self):
        out = self.s
        for p in self.parts:
            out = out.replace("{}", p.render() if hasattr(p, "render") else str(p), 1)
        return out


class _Ident:
    def __init__(self, v):
        self.v = v

    def render(self):
        return '"' + self.v + '"'


class _Conn:
    def __init__(self):
        self.ran = []

    def execute(self, q, params=None):
        text = q.render() if hasattr(q, "render") else q
        self.ran.append(text)
        row = ("eaexplorer",) if "current_database" in text else None
        return types.SimpleNamespace(fetchone=lambda: row)


def test_both_logins_get_the_right_to_sign_in_to_the_repository_database(monkeypatch):
    """Full test, 24 Nov 2026: "permission denied for database eaexplorer": PUBLIC has no CONNECT there."""
    fake = types.ModuleType("psycopg.sql")
    fake.SQL, fake.Identifier, fake.Literal = _SQL, _Ident, lambda v: "'***'"
    pkg = types.ModuleType("psycopg")
    pkg.sql = fake
    monkeypatch.setitem(sys.modules, "psycopg", pkg)
    monkeypatch.setitem(sys.modules, "psycopg.sql", fake)
    monkeypatch.setenv("EAX_CONSOLE_IT_PASSWORD", "a")
    monkeypatch.setenv("EAX_CONSOLE_SUPER_PASSWORD", "b")
    from eax import sqlconsole
    conn = _Conn()
    assert sorted(sqlconsole.ensure_logins(conn)) == ["eax_console_it", "eax_console_super"]
    for user in ("eax_console_it", "eax_console_super"):
        assert f'GRANT CONNECT, TEMPORARY ON DATABASE "eaexplorer" TO "{user}"' in conn.ran     # TEMPORARY: R14.31


# ---------------------------------------------------------------- 1. an index for each foreign key the db check found
def test_the_five_foreign_keys_get_an_index_after_release_13():
    sql = _read(API / "migrations/sql/0122_r14_foreign_key_indexes.sql")
    for table, column in (("backlog_items", "item_id"), ("backlog_items", "sprint_id"), ("sprint_decisions", "backlog_id"),
                          ("raci", "item_id"), ("raci", "step_id")):
        assert re.search(rf"CREATE INDEX IF NOT EXISTS \w+\s+ON proj\.{table} \({column}\);", sql), (table, column)
    py = _read(API / "migrations/versions/0122_r14_foreign_key_indexes.py")
    assert 'down_revision = "0121_release_13_0_0"' in py and "DROP INDEX IF EXISTS proj." in py
    assert not re.search(r"CREATE (OR REPLACE )?(FUNCTION|TRIGGER|PROCEDURE)", sql)     # D248


# ---------------------------------------------------------------- 1. messages say the command as it was typed
@pytest.mark.parametrize("typed", [".\\eax", "./eax.sh"])
def test_messages_say_eax_when_eax_handed_the_command_over(typed):
    out = subprocess.run([sys.executable, "-c", "from eaxcli import core; print(core.EAX)"], cwd=REPO, capture_output=True,
                         text=True, env={"EAX_TYPED": typed, "PATH": "/usr/bin:/bin"}, timeout=60)
    assert out.stdout.strip() == typed, out.stderr[-400:]


def test_eax_ps1_and_eax_sh_say_how_they_were_typed():
    ps1, sh = _read(REPO / "eax.ps1"), _read(REPO / "eax.sh")
    assert '$env:EAX_TYPED = ".\\eax"' in ps1 and ps1.isascii()
    assert 'EAX_TYPED=./eax.sh exec "$BASH" ./eaxpy.sh "$@" ;;' in sh


# ---------------------------------------------------------------- 2. the journeys follow Release 13's navigation
def test_a_control_is_found_by_its_name_after_its_icon():
    from eax.testing.ui_flows import text_pattern as t
    assert t("Infrastructure").search("▦ Infrastructure") and t("Tools", True).search("⚒ Tools")
    assert not t("Tools", True).search("⚒ Toolset") and not t("Wizards").search("Model Wizards")
    assert t("+ In a form").search("+ In a form") and t("History", True).search("History")
    # an icon only, not punctuation: "› System Admin" in a path is not the menu (the full test of 24 Nov 2026, 11:24)
    assert not t("System Admin").search("› System Admin › Settings") and not t("System Admin").search("→ System Admin")
    assert t("Tools", True).search("Tools›") and t("Wizards", True).search("Wizards›")   # a sub-menu's arrow
    assert not t("Tools", True).search("Tools and more›")


def test_the_menu_journey_opens_the_wizards_through_the_tools_group():
    src = _read(API / "eax/testing/ui_flows.py")
    assert '{"click": "Tools", "within": ".tm-area.open", "exact": True}' in src


def test_no_journey_opens_a_phase_by_an_address_the_app_has_not():
    """#/projects/<id>/phases/B was never an address: the Phases tab takes ?phase=B."""
    from eax.testing import ui_flows as F
    opened = [s["open"] for j in F.JOURNEYS for s in j["steps"] if "open" in s]
    assert not [o for o in opened if re.search(r"/phases/[A-Z]", o)]
    assert "#/projects/{p}/phases?phase=B" in opened


def test_a_tick_the_journey_needs_is_set_not_toggled():
    """A run stopped half-way left Data Architect ticked; the next run's click unticked it."""
    from eax.testing import ui_flows as F
    by = {j["name"]: j for j in F.JOURNEYS}
    for name, label in (("TOGAF skills: on my profile, then by role", "Data Architect"),
                        ("project plan: RACI, a gate, a phase planned, a milestone, a status", "B")):
        states = [s.get("checked") for s in by[name]["steps"] if s.get("choose") == label]
        assert states == [True, False], (name, states)
    assert 'want = s.get("checked")' in _read(API / "eax/testing/ui_flows.py")


def test_the_guides_upload_opens_when_its_link_is_followed_on_the_page():
    src = _read(WEB / "ReferenceLibrary.jsx")
    assert 'window.addEventListener("hashchange", seen)' in src and 'removeEventListener("hashchange", seen)' in src


# ---------------------------------------------------------------- OCR: any time, or only between two times
def test_ocr_runs_any_time_unless_a_window_is_set():
    """Owner, 24 Nov 2026, 05:43: "The document OCR may or may not have a window, we may choose it to run always"."""
    from eax import documents_ocr as d
    from eax import settings as S
    assert S.REGISTRY["documents_ocr_from"][3] == "" and S.REGISTRY["documents_ocr_to"][3] == ""
    assert d.window({}) is None and d.window({"documents_ocr_from": "", "documents_ocr_to": ""}) is None
    assert d.inside(None, __import__("datetime").time(13, 0))
    src = _read(WEB / "DocumentsAdmin.jsx")
    assert "Any time</label>" in src and "Only between</label>" in src
    assert 'save({ documents_ocr_from: "", documents_ocr_to: "" })' in src       # Any time clears the window
    assert '{"expect": "Any time"}' in _read(API / "eax/testing/ui_flows.py")


# ---------------------------------------------------------------- 4. SonarQube: the bugs and the real vulnerabilities
def test_mail_over_ssl_checks_the_server_certificate(monkeypatch):
    from eax import alerts
    seen = {}

    class Fake:
        def __init__(self, host, port, timeout=None, context=None):
            seen["context"] = context

        def send_message(self, msg):
            seen["sent"] = True

        def quit(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP_SSL", Fake)
    monkeypatch.setenv("EAX_SMTP_HOST", "mail.example.org")
    monkeypatch.setenv("EAX_SMTP_PORT", "465")
    monkeypatch.setenv("EAX_SMTP_SECURITY", "ssl")
    monkeypatch.delenv("EAX_SMTP_USER", raising=False)
    assert alerts.send_email(["a@example.org"], "s", "b") == ""
    import ssl
    ctx = seen["context"]
    assert ctx is not None and ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname


def test_deploy_puts_its_files_in_a_folder_only_the_user_may_open():
    from eaxcli import deploy as D
    ctx = D.Ctx(answers={"kind": "server", "where": "ssh", "ssh_target": "me@server", "ssh_key": "k"}, plan=True, out=lambda _l: None)
    where = ctx.upload(Path("x.env"), "eaexplorer.env", "the config file")
    plan = "\n".join(ctx.printed)
    assert where == '"$HOME/.eaexplorer-stage"/eaexplorer.env'
    assert 'mkdir -p "$HOME/.eaexplorer-stage" && chmod 700 "$HOME/.eaexplorer-stage"' in plan
    assert "me@server:.eaexplorer-stage/eaexplorer.env" in plan and "/tmp/" not in plan
    assert not re.search(r'"/tmp/(eaexplorer\.env|tls|\{name\})', _read(REPO / "eaxcli/deploy.py"))


def test_a_session_key_is_a_file_of_its_own_not_a_fixed_name_in_tmp():
    src = _read(REPO / "services/ops/ops.py")
    assert 'tempfile.mkstemp(prefix=f"eax-ssh-{sid}-", suffix=".key")' in src and 'os.path.join("/tmp", f"eax-ssh-' not in src


def test_sorts_say_how_they_compare_and_promises_are_not_left_floating():
    assert ".sort(byText)" in _read(WEB / "BrandingAdmin.jsx") and ".sort()" not in _read(WEB / "BrandingAdmin.jsx")
    assert ".sort(byKey)" in _read(WEB / "Skills.jsx") and "Object.entries(data.togaf_levels || {}).sort()" not in _read(WEB / "Skills.jsx")
    assert "void call(`${base}/${e.record.id}/describes`" in _read(WEB / "RiskRegister.jsx")
    site = _read(REPO / "docs/site/assets/site.js")
    assert 'void sget((document.body' in site and 'void sget("/api/v1/heartbeat")' in site


def test_the_website_steps_pattern_finds_the_same_as_before():
    old, new = r"^## Steps\s*\n(.*?)(?=^## |\Z)", r"^## Steps\s*\n(.*?)(?=(?:^## )|\Z)"
    for body in ("# P\n## Steps\n1. a\n2. b\n## Next\nx", "## Steps\n1. only\n", "## Other\n", "## Steps\n\n## End"):
        a, b = re.search(old, body, re.M | re.S), re.search(new, body, re.M | re.S)
        assert (a and a.group(1)) == (b and b.group(1)), body
    assert new in _read(REPO / "tools/build_website.py")


# ---------------------------------------------------------------- the tests the code had outgrown
def test_the_unit_tests_that_had_outgrown_the_code_say_why():
    t = _read(API / "tests/test_backup_checks.py")
    assert '"performance", "attack", "backup", "restore")' in t
    for f in ("tests/test_mcp_ops.py", "tests/test_mcp_operations.py"):
        assert 'n.replace("togaf_role", "togaf")' in _read(API / f)
    assert 'monkeypatch.delenv("EAX_AUTH_MODE", raising=False)' in _read(API / "tests/test_sqlconsole.py")
    assert "for _ in range(150):" in _read(API / "tests/test_screen.py")
