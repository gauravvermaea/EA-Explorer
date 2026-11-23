"""Release 6.7: settings and admin configuration exported and imported (D755; the owner, 17 Nov 2026, 22:06: "we need
another release for import and export of settings and admin configs"; 18 Nov 2026, 11:55: "Please build 6.5.4 6.7").

One file, the parts chosen; never a secret; a file from a newer release refused; import shows every difference first,
keeps a safety copy before taking anything, takes only what is ticked, never removes what is only here, does the
database's parts before the operations helper's, and says what was taken when a part fails halfway. Every way: the API,
the screen, eax settings, Jenkins, and git as one more place.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from eaxcli import commands as C  # noqa: E402
from eaxcli import jenkins as J  # noqa: E402
from eaxcli import settings_cli as cli  # noqa: E402

from eax import __version__  # noqa: E402
from eax import settings_transfer as st  # noqa: E402


def _file(parts: dict, release: str = __version__) -> dict:
    return {"format": st.FORMAT, "release": release, "made_at": "2026-11-18T10:00:00+00:00", "made_by": "a", "site": "dev",
            "parts": parts}


class Ops:
    """The operations helper, faked: the banner, the allow lists and the schedules, and every call made."""

    def __init__(self, schedules=None, fail_on: str = ""):
        self.calls, self.fail_on = [], fail_on
        self.schedules = schedules or []

    def __call__(self, method, path, body=None, timeout=60):
        self.calls.append((method, path, body))
        if self.fail_on and path.startswith(self.fail_on) and method == "POST":
            raise st.TransferError("the helper refused", 502)
        if path == "/banner/all":
            return {"banner": {"text": "Hello", "level": "info", "audience": "everyone", "by": "x", "at": "t", "source": "admin"}}
        if path == "/allow":
            return {"lists": {"site": [{"address": "10.0.0.0/8", "name": "office", "why": ""}]}, "trusted": [], "internal": []}
        if path == "/commands/schedules":
            return {"schedules": self.schedules}
        return {}


# ---------------------------------------------------------------- the file
def test_a_file_from_a_newer_release_or_not_a_settings_file_is_refused():
    with pytest.raises(st.TransferError, match="not an EA Explorer settings file"):
        st.load("{}")
    with pytest.raises(st.TransferError, match="not JSON"):
        st.load("garbage")
    with pytest.raises(st.TransferError, match="newer") as e:
        st.load(json.dumps(_file({}, "99.0.0")))
    assert e.value.status == 409
    old = st.load(json.dumps(_file({"system": {"setting:x": 1}, "users": {"a": 1}}, "1.0.0")))
    assert list(old["parts"]) == ["system"]                        # an older release taken; never a part not known


def test_a_secret_never_travels_either_way():
    with pytest.raises(st.TransferError, match="secret"):
        st.load(json.dumps(_file({"webhooks": {"webhook:a": {"url": "https://x", "secret": "s"}}})))
    with pytest.raises(st.TransferError):
        st.no_secrets({"pairings": {"pairing:sender:a": {"key_enc": "x"}}})
    st.no_secrets({"webhooks": {"webhook:a": {"url": "https://x", "kinds": [], "enabled": True}}})


def test_unknown_parts_are_refused_and_the_parts_are_the_same_everywhere():
    with pytest.raises(st.TransferError, match="No part called users"):
        st.chosen("system,users")
    assert st.chosen("branding, system") == ["system", "branding"]
    assert tuple(st.PARTS) == cli.PARTS and set(st.OPS_PARTS) <= set(st.PARTS)


# ---------------------------------------------------------------- the preview
def test_the_preview_shows_every_difference_and_what_is_only_here():
    here = {"system": {"setting:a": 1, "setting:b": 2, "setting:c": 3},
            "pairings": {"pairing:sender:dr": {"send_mode": "auto"}},
            "branding": {"file:logo": {"data": "QUJD" * 512}}}
    file = {"system": {"setting:a": 1, "setting:b": 5, "setting:d": 4},
            "pairings": {"pairing:sender:dr": {"send_mode": "manual"}, "pairing:sender:uat": {"send_mode": "auto"}},
            "branding": {"file:logo": {"data": "WFla" * 1024}}}
    d = st.diff(here, file)
    rows = {r["key"]: r for r in d["system"]["differences"]}
    assert set(rows) == {"setting:b", "setting:d"} and rows["setting:b"]["change"] == "changed" and rows["setting:d"]["change"] == "new"
    assert d["system"]["only_here"] == ["setting:c"] and d["system"]["same"] == 1
    pr = {r["key"]: r for r in d["pairings"]["differences"]}
    assert not pr["pairing:sender:dr"]["cannot"] and "pair the sites" in pr["pairing:sender:uat"]["cannot"]
    assert "KB file" in d["branding"]["differences"][0]["file"]["data"]          # a file by its size, never its bytes


def test_a_schedule_turned_on_that_puts_the_maintenance_page_up_says_so():
    assert st.maintenance_of("schedules", "schedule:n", {"argv": ["backup"], "enabled": True})
    assert not st.maintenance_of("schedules", "schedule:n", {"argv": ["backup"], "enabled": False})
    assert not st.maintenance_of("schedules", "schedule:n", {"argv": ["status"], "enabled": True})
    assert not st.maintenance_of("system", "setting:x", {"argv": ["backup"], "enabled": True})


# ---------------------------------------------------------------- the operations helper's parts as read
def test_the_banner_allow_lists_and_schedules_are_read_without_who_and_when():
    ops = Ops(schedules=[{"id": "a1", "name": "Nightly backup", "argv": ["backup"], "cron": "0 2 * * *", "enabled": True,
                          "created_by": "x", "last": {"ok": True}},
                         {"id": "w1", "name": "Demo reset", "argv": ["clean-restart", "laptop"], "cron": "0 2 * * *", "wipe": True},
                         {"id": "o1", "name": "Once", "argv": ["backup"], "once_at": "2026-11-20T17:00"}])
    assert st._banner(ops) == {"banner": {"text": "Hello", "link": None, "link_text": None, "level": "info",
                                          "audience": "everyone", "dismissible": None, "starts": None, "ends": None}}
    assert st._allow_lists(ops)["place:site"] == [{"address": "10.0.0.0/8", "name": "office", "why": ""}]
    sch = st._schedules(ops)
    assert list(sch) == ["schedule:Nightly backup"]                 # never one that deletes everything, nor a once
    assert sch["schedule:Nightly backup"] == {"argv": ["backup"], "cron": "0 2 * * *", "enabled": True}


# ---------------------------------------------------------------- taking the differences
@pytest.fixture
def taking(monkeypatch):
    """take() with the parts read from `here`, each part's changes and the safety copy recorded in order."""
    seen = {"order": [], "here": {}, "records": []}

    def read(conn, parts, ops=None):
        return {p: dict(seen["here"].get(p, {})) for p in st.chosen(parts)}, {}

    def apply(conn, p, items, by, ops, caller, roles):
        seen["order"].append(("apply", p, sorted(items)))
        if p == seen.get("fail"):
            raise ValueError("a setting refused it")
        return []
    monkeypatch.setattr(st, "read_parts", read)
    monkeypatch.setattr(st, "_apply", apply)
    monkeypatch.setattr(st, "export", lambda conn, parts, by="?", site="", ops=None: {"parts": {p: {} for p in parts}})
    seen["keep"] = lambda body, parts: seen["order"].append(("copy", sorted(parts))) or "copy-1"
    seen["record"] = lambda conn, by, action, part, key, details: seen["records"].append((action, part, key))
    return seen


def test_a_safety_copy_first_then_only_what_is_ticked_the_database_before_the_helper(taking):
    taking["here"] = {"system": {"setting:a": 1, "setting:b": 2}, "banner": {"banner": None}}
    f = json.dumps(_file({"banner": {"banner": {"text": "Hi"}}, "system": {"setting:a": 9, "setting:b": 8, "setting:c": 7}}))
    out = st.take(None, f, {"banner": "all", "system": ["setting:a", "setting:c"]}, "admin", ops=Ops(),
                  keep=taking["keep"], record=taking["record"])
    assert taking["order"] == [("copy", ["banner", "system"]), ("apply", "system", ["setting:a", "setting:c"]),
                               ("apply", "banner", ["banner"])]
    assert out["taken"] == {"system": ["setting:a", "setting:c"], "banner": ["banner"]} and out["copy"] == "copy-1"
    assert ("settings.import", "system", "setting:a") in taking["records"] and len(taking["records"]) == 3


def test_nothing_different_means_nothing_kept_or_changed(taking):
    taking["here"] = {"system": {"setting:a": 1}}
    out = st.take(None, json.dumps(_file({"system": {"setting:a": 1}})), {"system": "all"}, "admin", ops=Ops(),
                  keep=taking["keep"], record=taking["record"])
    assert out["taken"] == {} and out["copy"] is None and taking["order"] == []


def test_a_pairing_not_here_is_never_made_by_an_import(taking):
    taking["here"] = {"pairings": {}}
    out = st.take(None, json.dumps(_file({"pairings": {"pairing:sender:uat": {"send_mode": "auto"}}})), {"pairings": "all"},
                  "admin", ops=Ops(), keep=taking["keep"], record=taking["record"])
    assert out["taken"] == {} and "pair the sites" in out["refused"][0]


def test_a_part_failing_halfway_says_what_the_helper_had_already_taken(taking):
    taking["here"] = {"banner": {"banner": None}, "schedules": {}}
    taking["fail"] = "schedules"
    f = json.dumps(_file({"banner": {"banner": {"text": "Hi"}}, "schedules": {"schedule:x": {"argv": ["status"], "cron": "0 1 * * *"}}}))
    with pytest.raises(st.TransferError) as e:
        st.take(None, f, {"banner": "all", "schedules": "all"}, "admin", ops=Ops(), keep=taking["keep"], record=taking["record"])
    msg = str(e.value)
    assert "Command centre schedules could not be taken" in msg and "Banner had already been taken" in msg and "copy-1" in msg
    taking["order"].clear()
    taking["fail"] = "system"
    taking["here"] = {"system": {"setting:a": 1}, "banner": {"banner": None}}
    with pytest.raises(st.TransferError) as e:
        st.take(None, json.dumps(_file({"system": {"setting:a": 2}, "banner": {"banner": {"text": "Hi"}}})),
                {"system": "all", "banner": "all"}, "admin", ops=Ops(), keep=taking["keep"], record=taking["record"])
    assert "already been taken" not in str(e.value)                 # the database first: the banner never reached
    assert ("apply", "banner", ["banner"]) not in taking["order"]


def test_schedules_are_made_switched_or_remade_never_ones_of_ea_explorer_remade():
    have = [{"id": "s1", "name": "Nightly backup", "argv": ["backup"], "cron": "0 2 * * *", "enabled": False},
            {"id": "s2", "name": "Tidy", "argv": ["db", "tidy"], "cron": "0 3 * * *", "enabled": True},
            {"id": "r6rotate", "name": "Rotate", "argv": ["secrets", "rotate", "--due"], "cron": "17 3 * * *", "enabled": False,
             "system": True}]
    ops = Ops(schedules=have)
    st._apply_schedules({"schedule:Nightly backup": {"argv": ["backup"], "cron": "0 2 * * *", "enabled": True},
                         "schedule:Tidy": {"argv": ["db", "tidy"], "cron": "30 4 * * *", "enabled": True},
                         "schedule:Rotate": {"argv": ["secrets", "rotate", "--due"], "cron": "0 1 * * *", "enabled": True},
                         "schedule:New": {"argv": ["status"], "cron": "0 6 * * *", "enabled": True}}, "admin", ops, ["super-admin"])
    posts = [(p, (b or {}).get("name")) for m, p, b in ops.calls if m == "POST"]
    assert ("/commands/schedules/s1/on", None) in posts                              # the same job: switched on
    assert ("/commands/schedules/s2/remove", None) in posts and ("/commands/schedules", "Tidy") in posts   # remade
    assert ("/commands/schedules/r6rotate/on", None) in posts                        # EA Explorer's own: only switched
    assert not any(p == "/commands/schedules/r6rotate/remove" for p, _ in posts)
    assert ("/commands/schedules", "New") in posts


def test_an_allow_list_that_would_lock_out_the_importer_is_refused():
    with pytest.raises(st.TransferError, match="IP allow lists"):
        st._apply_allow({"place:admin": [{"address": "192.0.2.0/24", "name": "", "why": ""}]}, "admin", Ops(), "198.51.100.7")


# ---------------------------------------------------------------- every way
def test_eax_settings_export_writes_the_file_and_import_without_yes_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "compose_args", lambda a: a)
    calls = []

    def run(args, **k):
        calls.append((args, k.get("input")))
        if "export" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps(_file({"system": {"setting:a": 1}})), "")
        return subprocess.CompletedProcess(args, 0, json.dumps({"file": {}, "differences": {}}), "")
    target = tmp_path / "out" / "s.json"
    assert cli.main(["export", str(target), "--parts", "system"], run=run) == 0
    assert json.loads(target.read_text())["parts"] == {"system": {"setting:a": 1}}
    assert calls[0][0][:6] == ["exec", "-T", "api", "python", "-m", "eax.settings_transfer"] and "--parts" in calls[0][0]
    assert cli.main(["import", str(target)], run=run) == 0
    assert calls[1][0][6] == "preview" and "--yes" not in calls[1][0] and '"setting:a"' in calls[1][1]
    with pytest.raises(cli.Failure, match="No part called users"):
        cli.main(["export", str(target), "--parts", "users"], run=run)


def test_the_jenkins_tasks_and_the_command_line_agree():
    assert J.argv_for("admin-import-settings", {"FILE": "D:/s.json", "PARTS": "system,branding"}) == \
        ["settings", "import", "D:/s.json", "--parts", "system,branding", "--yes"]
    assert J.argv_for("admin-settings-differences", {"FILE": "D:/s.json"}) == ["settings", "import", "D:/s.json"]
    assert J.ADMIN_BY_NAME["admin-import-settings"]["confirm"] and J.ADMIN_BY_NAME["admin-undo-a-settings-import"]["confirm"]
    assert C.check_argv(["settings", "export", "work/exports/s.json", "--parts", "system"])
    assert "settings" in {p["name"] for p in J.pipelines()}


def test_the_screen_the_api_git_and_the_table_are_there():
    web = REPO / "services/web/src"
    assert '{ key: "settings-transfer", label: "Settings import and export", ok: sup' in (web / "adminNav.js").read_text()   # D898
    assert "tab:Settings import and export" in json.loads((web / "help/catalogue.json").read_text(encoding="utf-8"))
    page = (web / "SettingsTransfer.jsx").read_text()
    for call in ("/settings-transfer/export", "/settings-transfer/preview", "/settings-transfer/import", "/settings-transfer/undo",
                 'source: "settings"', 'suffix=".json"'):
        assert call in page, call
    assert "settings_transfer_blp" in (REPO / "services/api/eax/app.py").read_text()
    sql = (REPO / "services/api/migrations/sql/0106_r6_7_settings_copies.sql").read_text()
    assert "core.settings_copies" in sql and "TO eax_app" in sql
    from eax import gitpackages
    assert gitpackages._NAME.match("eax-settings-dev-20261118T100000Z.json")
    for launcher in ("eax.ps1", "eax.sh"):
        assert "settings" in (REPO / launcher).read_text()
