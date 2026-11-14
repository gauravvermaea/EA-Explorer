"""Release 4's bugs (R4.11 to R4.17), each with a test that fails without its fix (D599)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _app(monkeypatch):
    from eax import auth
    from eax.app import create_app
    user = auth.User(username="t", roles=["super-admin"])
    monkeypatch.setattr(auth, "current_user", lambda: user)
    return create_app(testing=True)


# ---------------------------------------------------------------- R4.13
def test_r4_13_one_route_archives_a_model_and_it_is_the_archives(monkeypatch):
    """The phase-2 archive (read only, no body) shadowed the archive's own route: the screen's Archive button only hid
    the model, and a body that was not JSON archived it."""
    app = _app(monkeypatch)
    rules = [r for r in app.url_map.iter_rules() if r.rule.endswith("/archive") and r.rule.startswith("/api/v1/models/")
             and "POST" in r.methods]
    assert len(rules) == 1 and rules[0].endpoint.startswith("archive."), [(r.rule, r.endpoint) for r in rules]


@pytest.mark.parametrize("body,status", [(b"{this is not json", 400), (b"[1, 2, 3]", 422), (b"", 422), (b"{}", 422),
                                         (b'{"state": "gone"}', 422)])
def test_r4_13_archive_refuses_a_body_that_does_not_say_what_to_do(monkeypatch, body, status):
    from eax.api import archive as ar_api
    reached = []
    monkeypatch.setattr(ar_api.repo, "get_model", lambda conn, mid: reached.append(mid) or {"id": mid, "name": "m"})
    monkeypatch.setattr(ar_api, "get_engine", lambda: (_ for _ in ()).throw(AssertionError("reached the database")))
    c = _app(monkeypatch).test_client()
    for path in ("/api/v1/models/00000000-0000-4000-8000-00000000dead/archive",
                 "/api/v1/projects/00000000-0000-4000-8000-00000000dead/archive"):
        r = c.post(path, data=body, headers={"Content-Type": "application/json"})
        assert r.status_code == status, (path, r.status_code, r.get_data(as_text=True)[:200])
    assert reached == []


def test_r4_13_the_negative_tests_never_send_to_what_cannot_be_undone():
    from eax.testing import negative
    spec = {"paths": {p: {"post": {"requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}}}}
                      for p in ("/api/v1/models/{model_id}/archive", "/api/v1/archive/{ident}/restore",
                                "/api/v1/models/{model_id}/changes/discard", "/api/v1/models/{model_id}/content/entities")}}
    sent = {c[4] for c in negative.checks(spec, {"model_id": "m", "model": "m"})}
    assert sent == {"/api/v1/models/{model_id}/content/entities"}


# ---------------------------------------------------------------- R4.14
def test_r4_14_a_project_backup_that_is_not_there_is_a_404(monkeypatch):
    from contextlib import contextmanager

    from eax.api import projects as api_pj

    @contextmanager
    def connections(write=False):
        yield object()
    monkeypatch.setattr(api_pj.pj, "connections", connections)
    monkeypatch.setattr(api_pj, "_admin_project", lambda c, p: {"guid": "00000000-0000-4000-8000-00000000dead"})
    c = _app(monkeypatch).test_client()
    for file in ("nope.zip", "not-a-backup.txt"):
        r = c.get(f"/api/v1/projects/p/backups/{file}")
        assert r.status_code == 404 and "No such backup" in r.get_data(as_text=True), (file, r.status_code)


def test_r4_14_a_governance_record_id_that_is_not_one_is_a_404_before_any_query():
    from eax import governance as gv
    from eax.metamodel_edit import EditError
    with pytest.raises(EditError) as err:
        gv._row(None, {"id": 1}, "Decision")             # the self-test sent a type's name; no database touched
    assert err.value.status == 404


def test_r4_14_the_industry_pack_of_a_model_that_is_not_there_is_a_404():
    from eax import industry_packs as ip
    from eax.metamodel_edit import EditError

    class Conn:
        def execute(self, *a, **k):
            class R:
                def mappings(self):
                    return self

                def first(self):
                    return None
            return R()
    with pytest.raises(EditError) as err:
        ip.for_model(Conn(), "00000000-0000-4000-8000-00000000dead")
    assert err.value.status == 404


# ---------------------------------------------------------------- R4.15
def _ops(monkeypatch, tmp_path):
    import importlib.util
    import sys
    monkeypatch.setenv("EAX_WORK_MOUNT", str(tmp_path))
    sys.path.insert(0, str(REPO / "services" / "ops"))
    spec = importlib.util.spec_from_file_location("ops_r4_15", REPO / "services" / "ops" / "ops.py")
    ops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ops)
    return ops


def test_r4_15_a_container_gone_between_list_and_look_is_left_out(monkeypatch, tmp_path):
    """GET /admin/scaling answered 500 to every role: "no such object: 194efbd99e8a" (a container listed a moment
    earlier had gone)."""
    import json
    ops = _ops(monkeypatch, tmp_path)
    ps = "\n".join(json.dumps({"ID": i, "Names": f"eaexplorer-{s}-1", "State": "running", "Status": "Up", "Image": "x"})
                    for i, s in (("aaa", "api"), ("bbb", "testrunner"), ("ccc", "api")))

    def docker(*args, timeout=120):
        if args[0] == "ps":
            return ps
        if args[-1] == "bbb" or (args[-1] == "ccc" and "{{json .}}" in args):
            raise RuntimeError("Error: No such object: " + args[-1])
        if "{{json .}}" in args:
            return json.dumps({"Config": {"Labels": {"com.docker.compose.container-number": "1"}},
                               "State": {"Health": {"Status": "healthy"}, "StartedAt": "x"}})
        return "api|1|hash|False"
    monkeypatch.setattr(ops, "docker", docker)
    monkeypatch.setattr(ops, "project", lambda: "eaexplorer")
    monkeypatch.setattr(ops, "is_service_container", lambda made, oneoff: True)
    assert [c["id"] for c in ops.containers()] == ["aaa", "ccc"]           # bbb gone before its labels were read
    assert [s["id"] for s in ops.api_servers()] == ["aaa"]                 # ccc gone before it was looked into
    with pytest.raises(RuntimeError):                                       # any other Docker error still says so
        monkeypatch.setattr(ops, "docker", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("permission denied"))
                            if a[0] == "inspect" else ps)
        ops.containers()


# ---------------------------------------------------------------- R4.16
def test_r4_16_the_restore_test_unpins_the_safety_backups_it_made_before_deleting_them(monkeypatch):
    """A restore pins the backup it takes first; deleting a pinned one is refused, so the restore suite said
    "could not remove ... delete them on the Backups page"."""
    import test_restore_check as trc

    from eax.testing import restore_check as rc

    class Pinned(trc._Install):
        def __init__(self):
            super().__init__()
            self.unpinned = set()

        def call(self, base, method, path, token, body=None):
            if method == "POST" and path.endswith("/pin"):
                self.calls.append((method, path, body))
                if body == {"pinned": False}:
                    self.unpinned.add(path.split("/")[-2])
                return 200, {}
            if method == "POST" and path.endswith("-before/delete") and "20991231T000000Z-before" not in self.unpinned:
                self.calls.append((method, path, body))
                return 409, {"message": "pinned: unpin it first"}
            return super().call(base, method, path, token, body)
    inst, recorded = Pinned(), []
    trc._wire(monkeypatch, inst)
    rc.run("http://api", "tok", {"model": "m1", "project": "p1"}, lambda *a: recorded.append(a), lambda m: None, None, 7,
           "eax", call=inst.call, sleep=lambda s: None)
    removed = next(r for r in recorded if r[0] == "restore: the test's backups removed")
    assert removed[1] == "passed", removed


def test_r4_16_the_discovery_checks_read_the_whole_answer():
    from eax.testing import discovery_check, negative
    assert discovery_check.run.__defaults__[-1] is discovery_check._whole
    import inspect
    assert inspect.signature(negative.send).parameters["limit"].default == 800
    src = inspect.getsource(discovery_check._whole)
    assert "limit=None" in src


def test_r4_16_a_path_value_with_a_space_is_encoded():
    from eax.testing.api_matrix import fill
    assert fill("/api/v1/models/{model}/quality/types/{type}", {"model": "m", "type": "Application Component"}) == \
        "/api/v1/models/m/quality/types/Application%20Component"


def test_r4_16_an_id_is_found_in_a_list_of_records_not_a_list_of_choices():
    import json

    from eax.testing.api_matrix import _first_item
    body = json.dumps({"kinds": ["Decision", "Risk"], "records": [{"id": "6f1c0d4e-0000-4000-8000-000000000001", "ref": "D1"}]})
    assert _first_item(body) == {"id": "6f1c0d4e-0000-4000-8000-000000000001", "ref": "D1"}
    assert _first_item(json.dumps({"kinds": ["Decision"]})) == "Decision"          # only choices: as before


def test_r4_16_too_long_and_sql_names_reach_the_runs_own_records():
    """R3.9's long-name and SQL-name kinds ran 0 times; they go to the endpoints that make a plain record in the run's
    model (with what such a record also needs), never to promote or framework-move."""
    import json

    from eax.app import create_app
    from eax.testing import negative
    spec = create_app(testing=True).test_client().get("/api/openapi.json").get_json()
    got = [c for c in negative.checks(spec, {"model": "m", "model_id": "m", "entity": "e", "entity_id": "e"})
           if c[0] in ("too long", "SQL text")]
    paths = {c[4] for c in got}
    assert "/api/v1/models/{model_id}/content/entities" in paths and len(got) >= 6
    assert not any("promote" in p or "framework-move" in p for p in paths)
    body = json.loads(next(c[3] for c in got if c[0] == "SQL text" and c[4].endswith("/content/entities")))
    assert body == {"entity_type": "ApplicationComponent", "name": negative.SQL_TEXT}


class _SpaPage:
    """A browser page with a one-page app: moving to another #route is not a load; a script error kills the app until
    the page is really loaded again (a different document first)."""

    def __init__(self, breaks: str):
        self.breaks, self.url, self.alive, self.handlers = breaks, "", True, {}
        self.keyboard = self

    def on(self, event, fn):
        self.handlers.setdefault(event, []).append(fn)

    def goto(self, url, **kw):
        same_doc = self.url.split("#")[0] == url.split("#")[0] and self.url != "about:blank"
        if not same_doc:
            self.alive = True                            # a real load starts the app again
        self.url = url
        self._arrive()

    def _arrive(self):
        if self.breaks in self.url and self.alive:
            self.alive = False
            for fn in self.handlers.get("pageerror", []):
                fn("TypeError: m.containers is undefined")

    def evaluate(self, js, arg=None):
        if arg is not None:                               # a move to another #route inside the page
            self.url = self.url.split("#")[0] + arg
            self._arrive()
            return None
        return {"head": "Title", "links": [], "notFound": False}

    def wait_for_selector(self, sel, timeout=0):
        if not self.alive:
            raise TimeoutError("Timeout 60000ms exceeded waiting for text=EA Explorer")

    def wait_for_timeout(self, ms):
        pass

    def wait_for_load_state(self, *a, **k):
        pass

    def press(self, key):
        pass

    def screenshot(self, **kw):
        return b""


def test_r4_16_one_page_that_breaks_never_takes_the_rest_with_it(monkeypatch):
    """The measuring run of 14 Nov 2026: the Footprint page's script error left the app dead, and the eleven System
    Admin pages after it each waited 60 s and failed."""
    from eax.testing import ui_pages
    monkeypatch.setattr(ui_pages, "judge", lambda found, errors, help_state:
                        ("failed", errors[0]) if errors else ("passed", "ok"))
    page = _SpaPage(breaks="/footprint")
    base = "https://localhost/?eaxselftest=t&eaxrole=super-admin"
    routes = ["#/admin/system", "#/admin/footprint", "#/admin/backups", "#/admin/users", "#/admin/health"]
    got = []
    ui_pages.sweep(page, lambda r: page.goto(base + r), {}, lambda *a, **k: got.append((a[0], a[1])), routes=routes)
    assert got == [("page: #/admin/system", "passed"), ("page: #/admin/footprint", "failed"),
                   ("page: #/admin/backups", "passed"), ("page: #/admin/users", "passed"), ("page: #/admin/health", "passed")]


# ---------------------------------------------------------------- R4.17
def test_r4_17_the_iteration_journey_waits_for_what_saving_said_before_the_dialog_must_be_gone():
    """Step 14 waited a fixed 8 s for the dialog to close; under the full test's load the save itself took longer, so
    "Note (optional)" was still there. Now each save waits for its answer ("Now a ..."), which also says why when a save
    is refused, and only then for the dialog to close (1.5 s after)."""
    from eax.testing import ui_flows
    j = next(x for x in ui_flows.JOURNEYS if x["name"] == "project: iteration, frozen phase, back")
    steps = j["steps"]
    saves = [i for i, s in enumerate(steps) if s.get("click") == "Save"]
    assert len(saves) == 2
    for i, said in zip(saves, ("Now a Transition Planning", "Now a Full cycle"), strict=True):
        assert steps[i].get("within") == "[role=dialog]" and "wait" not in steps[i]
        assert steps[i + 1] == {"expect": said} and steps[i + 2]["expect_not"] == "Note (optional)"
    dialog = (REPO / "services/web/src/IterationControl.jsx").read_text()
    assert "refreshAll(); setTimeout(onClose, 1500);" in dialog
    assert "\"message\": f\"Now a {now['label']}.\"" in (REPO / "services/api/eax/iterations.py").read_text()


# ---------------------------------------------------------------- R4.11
def test_r4_11_the_screen_comes_back_until_exit(monkeypatch, tmp_path):
    """The owner's Windows laptop: after any command the screen closed and the prompt was back. Now it only ends on
    Exit or Ctrl+C; any other end is written down and the screen opens again."""
    import sys
    sys.path.insert(0, str(REPO))
    from eaxcli import screen
    monkeypatch.setattr(screen, "LOG", tmp_path / "eax-screen.log")
    runs = []

    class App:
        def __init__(self, ends):
            self.ends, self.return_code = ends, 1

        def run(self, mouse=True):
            runs.append(self.ends)
            if self.ends == "error":
                raise RuntimeError("console lost")
            if self.ends == "exit":
                self.asked_to_leave = True
    plan = iter(["dropped", "error", "exit"])
    t = iter(range(0, 1000, 30))
    said = []
    assert screen.run_screen(lambda: App(next(plan)), clock=lambda: next(t), say=said.append) == 0
    assert runs == ["dropped", "error", "exit"]                         # back twice, then Exit ends it
    log = (tmp_path / "eax-screen.log").read_text()
    assert "it ended without Exit (return code 1)" in log and "RuntimeError: console lost" in log
    assert len(said) == 2 and "opening it again" in said[0]


def test_r4_11_a_screen_that_keeps_closing_gives_way_to_the_numbered_menu(monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, str(REPO))
    from eaxcli import screen
    monkeypatch.setattr(screen, "LOG", tmp_path / "eax-screen.log")
    monkeypatch.setattr(screen.menu_, "main", lambda argv: 7)

    class App:
        return_code = 1

        def run(self, mouse=True):
            pass
    said = []
    assert screen.run_screen(App, clock=lambda: 0, say=said.append) == 7
    assert "the numbered menu instead" in said[-1] and len(said) == screen.REOPEN_LIMIT


def test_r4_11_a_command_in_the_window_shares_no_console_with_the_screen_on_windows():
    src = (REPO / "eaxcli/screen.py").read_text()
    assert 'DETACHED = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}' in src
    assert "cwd=str(ROOT),\n                                     **DETACHED)" in src
    assert "def action_quit(self) -> None:" in src and "self.asked_to_leave = True" in src
    assert "self.push_screen(Output(line))" in src.split("def user_screen", 1)[1].split("def _on_user_screen", 1)[0]


def test_r4_11_the_screen_still_runs_after_a_command_in_the_window_and_exits_on_alt_x(monkeypatch):
    pytest.importorskip("textual")
    import asyncio
    import sys
    sys.path.insert(0, str(REPO))
    from eaxcli import core, screen
    monkeypatch.setattr(core, "compose_out", lambda args: [])
    monkeypatch.setattr(screen, "argv_for", lambda line, form=None: [sys.executable, "-c", "print('done')"])
    seen = {}

    async def drive():
        app = screen.build_app("py", False, "./eaxpy.sh")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            app.ran(["status"])                              # a command in the window, as a menu pick would
            await pilot.pause(1.0)
            await pilot.press("escape")
            await pilot.pause(0.2)
            seen["running"] = app.is_running and type(app.screen).__name__ == "Screen"
            await pilot.press("alt+x")
            await pilot.pause(0.2)
        seen["left"] = getattr(app, "asked_to_leave", False)
    asyncio.run(drive())
    assert seen == {"running": True, "left": True}


def test_r4_16_coverage_counts_only_our_own_code():
    """Owner, 14 Nov 2026, 19:05: "When we talk about code coverage we are only talking about code we have written"."""
    src = (REPO / "services/api/eax/coverage_probe.py").read_text()
    assert "source=[PACKAGE]" in src and 'omit=[f"{PACKAGE}/testing/*"]' in src
    assert 'PACKAGE = str(Path(__file__).resolve().parent)' in src          # eax itself: no library is ever measured
