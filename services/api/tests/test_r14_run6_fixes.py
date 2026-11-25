"""Release 14: the fixes for the five failures of the full test of 24 Nov 2026, run 6 (20261124T130501Z; owner, 24 Nov
2026, 18:27: "fix the 5 issues"). One test, or more, for each fix."""

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API = REPO / "services/api"
WEB = REPO / "services/web/src"
sys.path.insert(0, str(API))


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _journey(name: str) -> dict:
    from eax.testing import ui_flows
    return next(j for j in ui_flows.JOURNEYS if j["name"] == name)


# ---------------------------------------------------------------- 1. the start page's System admin tile
def test_the_system_admin_tile_is_for_those_the_menu_shows_it_to():
    """A Report Viewer saw the start page's System admin tile open while the menu bar hid System Admin ("System Admin is
    offered to report-viewer"). One rule now, in menu.js, for both."""
    menu, areas = _read(WEB / "menu.js"), _read(WEB / "Areas.jsx")
    assert 'export const maySystemAdmin = () => ops() || can("settings.manage") || can("users.read");' in menu
    assert '{ key: "system", label: "System Admin", ok: maySystemAdmin, items: [' in menu
    system = re.search(r'\{ key: "system", name: "System admin".*?\},\n', areas, re.S).group(0)
    assert "ok: maySystemAdmin" in system and "ok: () => true" not in system
    assert 'needsRole(["super-admin", "it-admin", "user-admin"])' in system      # greyed with the reason, as Model admin
    assert "import { mayModelAdmin, mayProjectAdmin, maySystemAdmin } from \"./menu\";" in areas


def test_the_refused_check_still_looks_for_system_admin_on_the_start_page():
    j = _journey("the menu bar: areas, wizards and Find")
    assert j["refused"] == {"role": "report-viewer", "open": "#/", "disabled_or_absent": "System Admin"}


def test_a_greyed_tile_is_not_a_control_the_refused_check_can_find():
    """The greyed tile is a div with aria-disabled, not a link or button: the check finds no control to offer."""
    areas = _read(WEB / "Areas.jsx")
    assert ': <div key={a.key} className={`area-tile area-${a.key} off`} aria-disabled="true"' in areas
    from eax.testing import ui_flows
    assert "div" not in [x.strip() for x in ui_flows._CLICKABLE.split(",")]


# ---------------------------------------------------------------- 2. the iteration's save as architect
def test_the_iteration_saves_wait_up_to_a_minute_for_their_answer():
    steps = _journey("project: iteration, frozen phase, back")["steps"]
    assert {"expect": "Now a Transition Planning", "timeout": 60000} in steps
    assert {"expect": "Now a Full cycle", "timeout": 60000} in steps


def test_a_failed_step_says_what_the_open_dialog_answered():
    """The report said only the dialog's first 200 characters and the page's first three status lines; the dialog's own
    answer (drawn last) never showed, so why the save did not finish was not known."""
    src = _read(API / "eax/testing/ui_flows.py")
    assert 'flatMap((e) => [...e.querySelectorAll(".status, .error, [role=alert]")])' in src
    assert 'parts += [f"the dialog answered: \\"{x[:200]}\\"" for x in said.get("dialog_said") or []]' in src


class _Page:
    def __init__(self, said):
        self.said = said

    def evaluate(self, _js):
        return self.said


def test_the_dialog_answer_is_in_the_failure_text():
    from eax.testing import ui_flows
    said = {"at": "#/projects/x", "h1": [], "status": ["active", "being built", "open"], "dialog": "ADM iteration ? ✕ Which",
            "dialog_said": ["Phase B isn't part of this Transition Planning iteration."]}
    out = ui_flows._page_says(_Page(said))
    assert out.endswith("the dialog answered: \"Phase B isn't part of this Transition Planning iteration.\"")
    said.pop("dialog_said")                                        # an older page answer: as before
    assert "the dialog answered" not in ui_flows._page_says(_Page(said))


# ---------------------------------------------------------------- 3. the project plan meets the project in a Full cycle
def test_the_project_plan_journey_puts_the_project_in_a_full_cycle_first():
    """Phase B had no "Mark the phase complete": the iteration journey had failed and left the project in Transition
    Planning, where B is frozen. The plan journey now sets a Full cycle before it needs phase B."""
    steps = _journey("project plan: RACI, a gate, a phase planned, a milestone, a status")["steps"]
    full = steps.index({"choose": "Full cycle", "within": "[role=dialog]"})
    assert steps[full - 1] == {"click": "Change…", "optional_alt": "Choose…", "within": ".iteration-bar"}
    assert steps[full + 1] == {"click": "Save", "exact": True, "within": "[role=dialog]"}
    assert steps[full + 2] == {"expect": "a Full cycle", "timeout": 60000}     # Now a … or Already a …
    assert full < steps.index({"click": "Mark the phase complete", "wait": 1500})
    it = _read(API / "eax/iterations.py")
    assert 'f"Already a {was[\'label\']}."' in it and 'f"Now a {now[\'label\']}."' in it


def test_the_journey_text_still_checks_out():
    from eax.testing import ui_flows
    j = _journey("project plan: RACI, a gate, a phase planned, a milestone, a status")
    for s in j["steps"]:
        assert any(k in s for k in ui_flows.STEP_KINDS), s


# ---------------------------------------------------------------- 4. Reports: the page crashed
def test_every_chromium_the_tests_start_keeps_off_the_small_shared_memory():
    """Chromium in a container writes to /dev/shm (64 MB by default) and its page crashes on a big page (the Reports'
    dashboards, drawn 4000 pixels tall): every launch in eax/testing passes --disable-dev-shm-usage."""
    launches = 0
    for f in sorted((API / "eax/testing").glob("*.py")):
        for m in re.finditer(r"chromium\.launch\((.*?)\)\n", _read(f), re.S):
            launches += 1
            assert "--disable-dev-shm-usage" in m.group(1), f.name
    assert launches >= 4


class _FakePage:
    def __init__(self, crash: bool):
        self.crash, self.closed, self.on_ = crash, False, {}

    def on(self, name, fn):
        self.on_[name] = fn

    def goto(self, *_a, **_k):
        if self.crash:
            raise RuntimeError("Page.goto: Page crashed")

    def wait_for_timeout(self, _ms):
        pass

    def close(self):
        self.closed = True


class _FakeContext:
    def __init__(self, crashes: int):
        self.pages, self.crashes = [], crashes

    def new_page(self):
        p = _FakePage(crash=len(self.pages) < self.crashes)
        self.pages.append(p)
        return p


class _FakeBrowser:
    def __init__(self, crashes: int):
        self.ctx = _FakeContext(crashes)

    def new_context(self, **_k):
        return self.ctx


def test_a_crashed_page_fails_its_dashboard_and_the_next_opens_in_a_new_page(monkeypatch):
    from eax.testing import reports_check as R
    monkeypatch.setattr(R, "FAIL_MS", 0)
    b = _FakeBrowser(crashes=1)
    s = R.Session(b, "super-admin", "u", "p", "https://reports.x")
    ms, answers = s.open({"slug": "vp-16"})
    assert answers and answers[-1][0] == 0 and "crashed" in answers[-1][1]
    ok, why, _rows = R.chart_answer(*answers[-1])
    assert not ok and "crashed" in why
    assert len(b.ctx.pages) == 2 and b.ctx.pages[0].closed and s.page is b.ctx.pages[1]
    assert set(s.page.on_) == {"request", "requestfinished", "requestfailed"}   # the new page still counts the charts
    ms, answers = s.open({"slug": "vp-17"})                                     # the next dashboard: no crash now
    assert not any("crashed" in a[1] for a in answers)


def test_anything_else_still_stops_the_suite(monkeypatch):
    from eax.testing import reports_check as R

    class Bad(_FakePage):
        def goto(self, *_a, **_k):
            raise RuntimeError("net::ERR_CONNECTION_REFUSED")

    class Ctx(_FakeContext):
        def new_page(self):
            return Bad(False)

    class Br:
        def new_context(self, **_k):
            return Ctx(0)

    monkeypatch.setattr(R, "FAIL_MS", 0)
    s = R.Session(Br(), "super-admin", "u", "p", "https://reports.x")
    try:
        s.open({"slug": "x"})
    except RuntimeError as exc:
        assert "REFUSED" in str(exc)
    else:
        raise AssertionError("a refused connection is not a crash: it goes on up")


# ---------------------------------------------------------------- 5. the security gate: the new image findings
DOCKER = {"web": REPO / "services/web/Dockerfile", "ops": REPO / "services/ops/Dockerfile"}
INDEX = "ADD https://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/APKINDEX.tar.gz /tmp/apk-index.tar.gz"


def test_a_new_alpine_fix_starts_the_upgrade_step_again():
    """libxml2's fix was in Alpine from 20 Nov 2026 but not in the web image built on 24 Nov: with the base image the
    same, Docker kept the apk upgrade step from an older build. Alpine's package index is fetched just before it, so a
    changed index runs the step again (owner, 24 Nov 2026: "Lets updated packages now to fix these", D912)."""
    for name, f in DOCKER.items():
        lines = [x for x in _read(f).replace("\\\n", " ").splitlines() if x and not x.startswith("#")]   # one RUN a line
        add = lines.index(INDEX)
        assert re.match(r"RUN apk upgrade --no-cache\s+&& ", lines[add + 1]), name
        assert "rm -f /tmp/apk-index.tar.gz" in lines[add + 1] or "rm -rf /tmp/*" in lines[add + 1], name


def test_the_web_image_takes_nginx_1_30_7_from_alpine():
    """nginx 1.30.6 had six high or critical findings fixed in 1.30.7; its makers' image is still 1.30.6, Alpine's own
    package is 1.30.7 (built 18 Nov 2026): it replaces the image's nginx, and the build fails if it does not run."""
    web = _read(DOCKER["web"])
    run = " ".join(web.replace("\\\n", " ").split())
    assert ('RUN apk upgrade --no-cache && apk info -q | grep \'^nginx-module-\' | xargs -r apk del --no-cache '
            '&& apk add --no-cache "nginx>=1.30.7" && nginx -v && nginx -t && rm -rf /tmp/* /tmp/.[!.]*') in run
    assert web.index("USER root") < web.index(INDEX) < web.index("USER 101")         # back to the unprivileged user
    assert "FROM nginxinc/nginx-unprivileged:1.30-alpine" in web


def test_nothing_root_made_is_left_in_tmp_for_the_unprivileged_user():
    """24 Nov 2026, 20:24: the web container stopped at every start on "open() /tmp/nginx.pid failed (13: Permission
    denied)": nginx -t ran as root at the build and left its files in /tmp. /tmp is emptied after it, before USER 101."""
    web = _read(DOCKER["web"])
    run = " ".join(web.replace("\\\n", " ").split())
    assert run.index("nginx -t") < run.index("rm -rf /tmp/* /tmp/.[!.]*")
    assert web.index("rm -rf /tmp/*") < web.index("USER 101")


def test_the_modules_tied_to_the_old_nginx_go_first_and_none_is_loaded():
    """The build of 24 Nov 2026, 19:52: "unable to select packages: nginx-1.30.7-r0 ... breaks: nginx-module-geoip-1.30.6-r1
    [nginx~1.30.6] ...": the image makers' optional modules hold their nginx back. They are deleted before the new nginx
    is added, and nothing of ours loads a module."""
    run = " ".join(_read(DOCKER["web"]).replace("\\\n", " ").split())
    assert run.index("xargs -r apk del") < run.index('apk add --no-cache "nginx>=1.30.7"')
    for f in [*(REPO / "services/web/nginx").glob("*"), *(REPO / "deploy/proxy/templates").glob("*")]:
        assert "load_module" not in _read(f), f.name


def test_the_web_configuration_uses_only_nginx_core():
    """Alpine's nginx is built with other options than the image makers': the web container's configuration uses only
    core directives (no module either build might lack), and its paths are set in the image's own nginx.conf."""
    conf = _read(REPO / "services/web/nginx/default.conf.template")
    used = set(re.findall(r"^\s*([a-z_0-9]+)\s", conf, re.M))
    assert used <= {"server", "listen", "root", "location", "add_header", "try_files", "return", "default_type", "index",
                    "server_name", "gzip", "gzip_types", "expires", "include", "error_page"}, used


def test_package_updates_are_still_never_accepted_in_writing():
    """D835 stands: what has a fix is updated, not accepted. The one exception (owner, 24 Nov 2026, 19:59: "accept the 2
    issues"): the ops image's two inside Docker's own plug-ins, which no release has fixed, to the end of the year only."""
    d = json.loads(_read(API / "eax/testing/security_accepted.json"))
    web = {"CVE-2026-86144", "CVE-2026-113425", "CVE-2026-121810", "CVE-2026-123007", "CVE-2026-123633", "CVE-2026-118899",
           "CVE-2026-123634"}
    assert not [a for a in d["accepted"] if a["id"] in web or a["id"] in {"package:nginx", "package:libxml2"}]
    ops = {a["id"]: a for a in d["accepted"] if a["id"] in {"CVE-2026-17106", "CVE-2026-78661"}}
    assert set(ops) == {"CVE-2026-17106", "CVE-2026-78661"}
    for a in ops.values():
        assert a["where"] == "image ops" and a["until"] == "2026-12-31" and "19:59" in a["by"] and "D835" in a["reason"]


def test_the_two_pass_now_only_in_the_ops_image_and_fail_in_january():
    from eax.testing import security_gate as g
    acc = g.accepted((API / "eax/testing/security_accepted.json",))
    f = g.finding("trivy", "CVE-2026-78661", "high", "golang.org/x/net v0.60.0: CVE-2026-78661", "image ops", True)
    elsewhere = {**f, "where": "image api"}
    now = g.gate([f, elsewhere], acc, date(2026, 11, 24))
    assert [x["where"] for x in now["failing"]] == ["image api"]
    assert len(g.gate([f], acc, date(2027, 1, 1))["failing"]) == 1


def test_the_gate_still_fails_them_until_the_images_are_rebuilt():
    from eax.testing import security_gate as g
    f = g.finding("trivy", "CVE-2026-113425", "critical", "nginx 1.30.6-r1: CVE-2026-113425", "image web", True)
    got = g.gate([f], g.accepted((API / "eax/testing/security_accepted.json",)), date(2026, 11, 24))
    assert len(got["failing"]) == 1


# ---------------------------------------------------------------- 6. the warnings fixed (owner, 24 Nov 2026, 19:11: "Fix what you can")
def test_the_documentation_pages_have_their_heading_while_they_load():
    """#/documentation and the printed guides had "no heading": the list is slow (every document is read) and the page
    showed only "Loading the documentation…" until it came."""
    src = _read(WEB / "Documentation.jsx")
    assert 'const head = <h1>{guidesOnly ? "Printed guides" : "Documentation"}</h1>;' in src
    assert '{head}<p><span className="spinner" aria-hidden="true" /> Loading the documentation…</p>' in src
    assert '{head}<p className="status error">{error}</p>' in src
    assert src.index("const guidesOnly") < src.index("if (!data) return")


def test_the_reports_import_line_is_read_from_the_whole_log():
    """"no import line in Reports' last 5,000 log lines": after hours of tests the line written at Reports' start had
    scrolled out. The check asks for the lines that contain it, from the whole log."""
    rc = _read(API / "eax/testing/reports_check.py")
    assert "/api/v1/admin/containers/reports/logs?tail=20&match=report%20dashboards%20imported%3A" in rc
    admin = _read(API / "eax/api/admin.py")
    assert 'extra = f"&match={quote(match)}" if match else ""' in admin
    ops = _read(REPO / "services/ops/ops.py")
    assert 'container_logs(m.group(1), tail, (q.get("match") or [""])[0])' in ops


def test_the_operations_helper_keeps_only_the_matching_lines(monkeypatch):
    sys.path.insert(0, str(REPO / "services/ops"))
    import importlib
    ops = importlib.import_module("ops")
    log = "".join(f"2026-11-24T13:0{i}:00Z line {i}\n" for i in range(5))
    log = "2026-11-24T13:00:00Z EA Explorer: report dashboards imported: 145 new or changed, 0 failed\n" + log * 3

    class P:
        def __init__(self, argv, **_k):
            assert argv[:3] == ["docker", "logs", "--timestamps"] and "--tail" not in argv   # the whole log
            self.stdout = iter(log.splitlines(keepends=True))

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(ops.subprocess, "Popen", P)
    monkeypatch.setattr(ops, "_one_container", lambda s: {"id": "c1"})
    got = ops.container_logs("reports", 20, "report dashboards imported:")
    assert got["lines"] == ["2026-11-24T13:00:00Z EA Explorer: report dashboards imported: 145 new or changed, 0 failed"]
    assert ops.container_logs("reports", 2, "line")["lines"] == ["2026-11-24T13:03:00Z line 3", "2026-11-24T13:04:00Z line 4"]


def test_every_address_is_opened_through_the_http_only_opener():
    """Bandit B310 (40 of the 42 medium findings): urllib's urlopen also opens file://. Every call in eax goes through
    eax.httpopen, which opens http and https only."""
    direct = []
    for f in sorted((API / "eax").rglob("*.py")):
        if f.name == "httpopen.py":
            continue
        for n, line in enumerate(_read(f).splitlines(), 1):
            if "urllib.request.urlopen(" in line:
                direct.append(f"{f.relative_to(API)}:{n}")
    assert direct == [], direct
    assert "# nosec B310 - the scheme is checked above" in _read(API / "eax/httpopen.py")


def test_the_opener_refuses_anything_but_http_and_https(monkeypatch):
    import urllib.error
    import urllib.request

    from eax import httpopen
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, *a, **k: seen.append(req) or "answer")
    assert httpopen.urlopen("https://api:8000/x", timeout=5) == "answer"
    assert httpopen.urlopen(urllib.request.Request("http://ops:8090/health")) == "answer"
    for bad in ("file:///etc/passwd", "ftp://host/x", "/etc/passwd", "gopher://x"):
        try:
            httpopen.urlopen(bad)
        except urllib.error.URLError as exc:
            assert "only http and https" in str(exc.reason)
        else:
            raise AssertionError(bad)
    assert len(seen) == 2                                       # the refused ones never reached urllib


def test_coverage_data_goes_to_the_systems_temporary_folder(monkeypatch):
    import tempfile

    from eax import coverage_probe
    monkeypatch.delenv("EAX_COVERAGE_DIR", raising=False)
    assert coverage_probe.folder() == Path(tempfile.gettempdir()) / "eax-coverage"
    monkeypatch.setenv("EAX_COVERAGE_DIR", "/elsewhere")
    assert coverage_probe.folder() == Path("/elsewhere")
    assert '"/tmp/eax-coverage"' not in _read(API / "eax/coverage_probe.py")


def test_the_consoles_insecure_sign_in_is_under_d835_for_bandit_too():
    d = json.loads(_read(API / "eax/testing/security_accepted.json"))
    a = next(a for a in d["accepted"] if a["id"] == "bandit:B323")
    assert a["where"] == "eax/console_cli.py" and a["until"] == "2027-05-21" and "D835" in a["by"]
    from eax.testing import codescan
    from eax.testing import security_gate as g
    acc = g.accepted((API / "eax/testing/security_accepted.json",))
    hit = {"test_id": "B323", "issue_severity": "MEDIUM", "issue_text": "unverified context",
           "filename": "/app/eax/console_cli.py", "line_number": 246}
    assert codescan.bandit_accepted(hit, acc)
    assert not codescan.bandit_accepted({**hit, "filename": "/app/eax/sites.py"}, acc)   # kept to its own file


# ---------------------------------------------------------------- 7. SonarQube's five of the full test of 24 Nov 2026, 19:09
def test_mail_tls_is_checked_in_full():
    """S4830 at alerts.py 387 and 391: ssl.create_default_context() passed straight in was still flagged. One helper says
    every check: the certificate required, the name checked, TLS 1.2 at least."""
    import ssl

    from eax import alerts
    ctx = alerts._checked_tls()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname and ctx.minimum_version >= ssl.TLSVersion.TLSv1_2
    src = _read(API / "eax/alerts.py")
    assert src.count("context=_checked_tls()") == 2 and "context=ssl.create_default_context()" not in src


def test_upload_has_one_return_and_still_says_where(monkeypatch):
    """S3516 (a blocker) at deploy.py: upload() returned the same text from two places."""
    sys.path.insert(0, str(REPO))
    import ast

    from eaxcli import deploy as D
    fn = next(n for n in ast.walk(ast.parse(_read(REPO / "eaxcli/deploy.py")))
              if isinstance(n, ast.FunctionDef) and n.name == "upload")
    assert len([n for n in ast.walk(fn) if isinstance(n, ast.Return)]) == 1
    ran = []
    for remote in (False, True):
        monkeypatch.setattr(D, "_remote", lambda _a, r=remote: r)
        obj = D.Ctx.__new__(D.Ctx)                     # no __init__: only what upload() reads
        obj.answers, obj.values = {"ssh_target": "u@h"}, {}
        obj.remote = lambda *a, **k: ""
        obj.run = lambda argv, *a, **k: ran.append(argv[0]) or ""
        assert obj.upload("/x/f.tar", "f.tar") == f"{D.STAGE_SH}/f.tar"
    assert ran == ["sudo", "scp"]


def test_the_two_screen_issues():
    assert "Number.parseInt(days[k], 10)" in _read(WEB / "Upkeep.jsx") and " parseInt(" not in _read(WEB / "Upkeep.jsx")
    assert 'void save({ documents_ocr_from: "", documents_ocr_to: "" })' in _read(WEB / "DocumentsAdmin.jsx")


# ---------------------------------------------------------------- 8. the full test of 24 Nov 2026, 21:37 (owner, 06:23: "if they can be fixed with increased time out I am fine")
def test_the_mcp_calls_wait_up_to_ten_minutes():
    """docs_list: "HTTP 599: no answer: timed out" after 3 minutes; the documentation tools read every document first."""
    import inspect

    from eax.testing import mcp_check
    assert mcp_check.RPC_TIMEOUT == 600
    assert inspect.signature(mcp_check.rpc).parameters["timeout"].default == 600


def test_a_dashboard_page_may_take_five_minutes_to_open():
    """"Page.goto: Timeout 120000ms exceeded" ended the Reports suite: the page itself now has 5 minutes; its charts are
    still timed against WARN_MS and FAIL_MS."""
    from eax.testing import reports_check as R
    assert R.NAV_MS == 300000 and (R.WARN_MS, R.FAIL_MS) == (30000, 120000)
    src = _read(API / "eax/testing/reports_check.py")
    assert 'wait_until="domcontentloaded", timeout=NAV_MS)' in src and "timeout=FAIL_MS)" not in src


def test_one_disk_is_listed_once_even_when_its_free_space_changes(monkeypatch, tmp_path):
    """test_disks found 2 disks for 1: the free space changed between the two reads of one busy disk."""
    import shutil as sh
    sys.path.insert(0, str(REPO))
    from eaxcli import screen_model as sm
    free = iter([100, 90, 80])
    monkeypatch.setattr(sm.shutil, "disk_usage", lambda _p: sh._ntuple_diskusage(1000, 1000 - 100, next(free)))
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert len(sm.disks([a, b, tmp_path])) == 1


# ---------------------------------------------------------------- 9. the project plan journey's gate (owner, 06:36: "Why cant we fix Project plan journey")
class _Labels:
    """Playwright's label list, as far as choose uses it: has_text a text (any case, anywhere) or a pattern."""
    def __init__(self, texts):
        self.texts = texts

    def filter(self, has_text):
        if isinstance(has_text, re.Pattern):
            return _Labels([t for t in self.texts if has_text.search(t)])
        return _Labels([t for t in self.texts if has_text.lower() in t.lower()])

    def count(self):
        return len(self.texts)

    def nth(self, i):
        return _Label(self.texts[i])


class _Label:
    def __init__(self, text):
        self.text, self.clicked = text, False

    def locator(self, _sel):
        return _Box(self.text)

    def click(self):
        _Label.last = self.text


class _Box:
    def __init__(self, text):
        self.text = text

    def count(self):
        return 0 if self.text.startswith("RACI") else 1

    @property
    def first(self):
        return self

    def get_attribute(self, _a):
        return "checkbox"

    def is_checked(self):
        return getattr(_Label, "last", None) == self.text


class _Within:
    def __init__(self, texts):
        self.texts = texts

    def locator(self, _sel):
        return _Labels(self.texts)

    def wait_for_timeout(self, _ms):
        pass


def test_choose_takes_the_label_that_says_exactly_b(monkeypatch):
    """Phase B was completed where its approval gate should have refused it: "choose B" took the first label holding a
    b in any case, the RACI field's (its list says "Per deliverable"), so the gate on B was never ticked."""
    from eax.testing import ui_flows
    page = _Within(["RACI No RACI Per phase Per deliverable Per step", " P", " A", " B", " C"])
    monkeypatch.setattr(ui_flows, "_visible", lambda _l: True)
    monkeypatch.setattr(ui_flows, "_root", lambda pg, _s: pg)
    monkeypatch.setattr(ui_flows, "_in_modal_first", lambda _p, root, _s, fn: fn(root))
    _Label.last = None
    why = ui_flows.step(page, {"choose": "B", "within": ".project-plan details", "checked": True}, lambda *_a: None)
    assert why == "" and _Label.last == " B"
    _Label.last = None                                  # a longer choice that is no label's whole text: as before
    page = _Within(["Full cycle (P, A, B, C, D, E, F, G, H)", "Transition Planning (E, F)"])
    assert ui_flows.step(page, {"choose": "Full cycle", "within": "[role=dialog]"}, lambda *_a: None) == ""
    assert _Label.last.startswith("Full cycle")


def test_the_old_way_took_the_raci_label():
    texts = ["RACI No RACI Per phase Per deliverable Per step", " P", " A", " B"]
    assert [t for t in texts if "b" in t.lower()][0].startswith("RACI")             # what went wrong
    assert [t for t in texts if re.search(r"^\s*B\s*$", t)] == [" B"]                # what is taken now
