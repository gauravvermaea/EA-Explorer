"""The self-test's reports suite (Release 4, R4.1; owner, 13 Nov 2026: "Add detailed report testing in phase 4"; 14 Nov
2026, 18:03: "add more test cases for reports"; 18:05: "Browser with test users").

The run's service accounts cannot sign in to Reports (Superset signs people in through Keycloak), so this suite makes
**Keycloak test users** for the run, one per kind of person Reports tells apart, with the same names as the run's
service accounts (so EA Explorer's model access, rpt.model_access, is theirs too), signs each in to Reports in
Chromium as a person would, and deletes them at the end (and any a stopped run left, older than a day):

  super-admin    eax-super-admin   Superset Admin: every model
  report-viewer  eax-user          Gamma + "EA Explorer reports": only the models they have (the run's test model)
  it-admin       eax-it-admin      Gamma only: no report content (D98)

  every report opens          each dashboard, as the Super Admin and as the Report Viewer: every chart's query answers
                              without an error; slower than 30 seconds a warning, not done after 60 a failure (the
                              owner's decision, 13 Nov 2026: every report is critical)
  only their own models       the Report Viewer's charts show no model they do not have, and do show the run's model
  committed content only      an element committed in the run shows; one left uncommitted never does
  refused                     the IT Admin sees no report dashboard
  the reports are all there   as many report dashboards as EA Explorer makes (eax.report_defs.REPORTS)
  from the screens            a model's Reports tab (GET /models/{m}/reports, as the Report Viewer) links every report to
                              Reports, and opening one of its links in the browser lands on that report, signed in as
                              the same person (single sign-on), its charts answering
  the files reports make      the model's quality report as PDF and Excel and its tree as Excel, as the Report Viewer:
                              each a file that opens (a PDF, a workbook) with the model's name in the workbooks
  the import at start-up      Reports' log says what the report import did: imported, unchanged, failed (none failed)
  not automated               a report deleted in Reports coming back at the next start: it needs Reports restarted, so
                              the restore suite and the owner's checks cover it (said as a skipped check, with why)

Charts are checked by what Superset answers (every /api/v1/chart/data response), not by its page's markup, so the
check does not depend on Superset's version. The page is tall (4000 pixels) so every chart loads at once (Superset
loads only the charts in view). A failed dashboard keeps its screenshot. One result each: "reports: ..."."""

from __future__ import annotations

import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime

from .negative import send as _send_part


def _send(base: str, method: str, path: str, token: str, raw: bytes | None) -> tuple[int, str]:
    return _send_part(base, method, path, token, raw, limit=None)   # parsed as JSON: the whole answer (R4.16)

Record = Callable[..., None]
PEOPLE = {"super-admin": "eax-super-admin", "report-viewer": "eax-user", "it-admin": "eax-it-admin"}
WARN_MS, FAIL_MS = 30000, 60000          # the owner's limits (13 Nov 2026)
QUIET_MS = 2500                          # no chart query for this long: the dashboard has finished loading
PREFIX = "svc-self-test-"


# ---------------------------------------------------------------- Keycloak test users
class Keycloak:
    """Keycloak's admin API with the installation's own administrator (EAX_KC_ADMIN, in the runner's environment)."""

    def __init__(self, base: str | None = None, realm: str | None = None, user: str | None = None, password: str | None = None,
                 opener=urllib.request.urlopen):
        self.base = (base or os.environ.get("EAX_KEYCLOAK_INTERNAL_URL") or "http://keycloak:8080/auth").rstrip("/")
        self.realm = realm or os.environ.get("EAX_KEYCLOAK_REALM", "eaexplorer")
        self.user = user if user is not None else os.environ.get("EAX_KC_ADMIN", "kcadmin")
        self.password = password if password is not None else os.environ.get("EAX_KC_ADMIN_PASSWORD", "")
        self.open, self.token = opener, ""

    def _call(self, method: str, path: str, body=None, form: dict | None = None) -> tuple[int, object, dict]:
        url = path if path.startswith("http") else f"{self.base}/admin/realms/{self.realm}{path}"
        data = urllib.parse.urlencode(form).encode() if form else json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
        if self.token and not form:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            with self.open(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=20) as r:
                raw = r.read().decode() or "null"
                return r.status, json.loads(raw), dict(r.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, {"error": exc.read().decode()[:300]}, dict(exc.headers or {})

    def sign_in(self) -> None:
        if not self.password:
            raise RuntimeError("EAX_KC_ADMIN_PASSWORD is not in the test runner's settings")
        s, d, _ = self._call("POST", f"{self.base}/realms/master/protocol/openid-connect/token",
                             form={"grant_type": "password", "client_id": "admin-cli", "username": self.user,
                                   "password": self.password})
        if s != 200 or not isinstance(d, dict) or not d.get("access_token"):
            raise RuntimeError(f"Keycloak's administrator could not sign in ({s})")
        self.token = d["access_token"]

    def make(self, username: str, password: str, role: str) -> str:
        """A user with a password that never has to be changed and one realm role; returns its id."""
        s, d, h = self._call("POST", "/users", {
            "username": username, "enabled": True, "emailVerified": True, "email": f"{username}@self-test.invalid",
            "firstName": "Self-test", "lastName": username.rsplit("-", 1)[-1], "requiredActions": [],
            "attributes": {"eax_self_test": [datetime.now(UTC).isoformat(timespec="seconds")]},
            "credentials": [{"type": "password", "value": password, "temporary": False}]})
        if s not in (201, 409):
            raise RuntimeError(f"Keycloak refused the test user {username} ({s}: {d})")
        s, found, _ = self._call("GET", f"/users?exact=true&username={urllib.parse.quote(username)}")
        uid = (found[0] if isinstance(found, list) and found else {}).get("id", "")
        if not uid:
            raise RuntimeError(f"Keycloak did not keep the test user {username}")
        self._call("PUT", f"/users/{uid}/reset-password", {"type": "password", "value": password, "temporary": False})
        s, r, _ = self._call("GET", f"/roles/{urllib.parse.quote(role)}")
        if s != 200:
            raise RuntimeError(f"Keycloak has no realm role {role} ({s})")
        self._call("POST", f"/users/{uid}/role-mappings/realm", [r])
        return uid

    def remove(self, uid: str) -> bool:
        return self._call("DELETE", f"/users/{uid}")[0] in (204, 404)

    def stale(self, sid: str, now: float | None = None) -> list[str]:
        """Test users a stopped run left behind: a self-test name, not this run's, made more than a day ago."""
        s, found, _ = self._call("GET", f"/users?search={PREFIX}&max=200&briefRepresentation=false")
        out = []
        for u in found if s == 200 and isinstance(found, list) else []:
            name = u.get("username", "")
            made = (u.get("attributes") or {}).get("eax_self_test") or []
            if not name.startswith(PREFIX) or name.startswith(f"{PREFIX}{sid}-") or not made:
                continue
            try:
                age = (now or time.time()) - datetime.fromisoformat(made[0]).timestamp()
            except ValueError:
                continue
            if age > 86400:
                out.append(u["id"])
        return out


def password() -> str:
    """A long random password that satisfies the usual realm policies (upper, lower, digit, symbol)."""
    return f"St{secrets.token_urlsafe(18)}9!a"


# ---------------------------------------------------------------- what Superset answered
def chart_answer(status: int, body: str) -> tuple[bool, str, list[dict]]:
    """One /api/v1/chart/data response: (ok, why not, its rows)."""
    if status != 200:
        return False, f"HTTP {status}: {body[:200]}", []
    try:
        data = json.loads(body)
    except ValueError:
        return False, "not JSON", []
    rows: list[dict] = []
    for res in data.get("result") or []:
        if res.get("error") or (res.get("status") not in (None, "success")):
            return False, str(res.get("error") or res.get("status"))[:300], []
        if isinstance(res.get("data"), list):
            rows += [r for r in res["data"] if isinstance(r, dict)]
    return True, "", rows


def models_in(rows: list[dict]) -> set[str]:
    return {str(r["model_name"]) for r in rows if r.get("model_name")}


def names_in(rows: list[dict]) -> set[str]:
    out = set()
    for r in rows:
        for v in r.values():
            if isinstance(v, str) and v.startswith("Self-test "):
                out.add(v)
    return out


def verdict(ms: int, errors: list[str], charts: int) -> tuple[str, str]:
    if errors:
        return "failed", "; ".join(errors[:5])
    if charts == 0:
        return "failed", "no chart answered"
    if ms >= FAIL_MS:
        return "failed", f"not loaded after {FAIL_MS // 1000} seconds"
    if ms >= WARN_MS:
        return "warning", f"{charts} charts in {ms / 1000:.0f} seconds (slower than {WARN_MS // 1000})"
    return "passed", f"{charts} charts in {ms / 1000:.1f} seconds"


def expected_dashboards() -> set[str]:
    """The slugs of the report dashboards EA Explorer makes (one per standard report, eax.report_defs)."""
    from ..report_defs import REPORTS
    return {r["slug"] for r in REPORTS}


def reports_url() -> str:
    host, port = os.environ.get("EAX_HOSTNAME", "localhost"), os.environ.get("EAX_HTTPS_PORT", "443")
    return f"https://reports.{host}" + ("" if port == "443" else f":{port}")


# ---------------------------------------------------------------- the browser
class Session:
    """One person signed in to Reports in their own browser context."""

    def __init__(self, browser, who: str, user: str, pw: str, base: str):
        self.who, self.base = who, base
        self.ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1600, "height": 4000})
        self.page = self.ctx.new_page()
        self.user, self.pw = user, pw
        self.pending: set = set()
        self.answers: list[tuple[int, str]] = []
        self.last = time.time()
        self.page.on("request", self._sent)
        self.page.on("requestfinished", self._done)
        self.page.on("requestfailed", self._failed)

    @staticmethod
    def _is_chart(req) -> bool:
        return "/api/v1/chart/data" in req.url

    def _sent(self, req) -> None:
        if self._is_chart(req):
            self.pending.add(req)
            self.last = time.time()

    def _done(self, req) -> None:
        if self._is_chart(req):
            self.pending.discard(req)
            self.last = time.time()
            try:
                resp = req.response()
                self.answers.append((resp.status, resp.text()) if resp else (0, "no response"))
            except Exception as exc:  # noqa: BLE001 - kept as a failed chart
                self.answers.append((0, str(exc)))

    def _failed(self, req) -> None:
        if self._is_chart(req):
            self.pending.discard(req)
            self.answers.append((0, f"request failed: {req.failure}"))
            self.last = time.time()

    def sign_in(self) -> None:
        self.page.goto(f"{self.base}/login/keycloak?next=%2Fdashboard%2Flist%2F", wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_selector("#username", timeout=60000)
        self.page.fill("#username", self.user)
        self.page.fill("#password", self.pw)
        self.page.click("#kc-login")
        self.page.wait_for_url(lambda u: u.startswith(self.base) and "/login" not in u, timeout=60000)

    def api(self, path: str) -> tuple[int, dict]:
        r = self.page.request.get(f"{self.base}{path}")
        try:
            return r.status, r.json()
        except Exception:  # noqa: BLE001
            return r.status, {}

    def dashboards(self) -> list[dict]:
        s, d = self.api("/api/v1/dashboard/?q=(page_size:500)")
        return [x for x in (d.get("result") or []) if isinstance(x, dict)] if s == 200 else []

    def open(self, dash: dict) -> tuple[int, list[tuple[int, str]]]:
        """Opens a dashboard and waits until its charts have answered (quiet for QUIET_MS) or FAIL_MS has passed."""
        self.pending.clear()
        self.answers = []
        t0 = time.time()
        self.last = t0
        url = dash.get("url") or f"/superset/dashboard/{dash.get('slug') or dash.get('id')}/"
        self.page.goto(f"{self.base}{url}", wait_until="domcontentloaded", timeout=FAIL_MS)
        while (time.time() - t0) * 1000 < FAIL_MS + 5000:
            quiet = (time.time() - self.last) * 1000
            if self.answers and not self.pending and quiet >= QUIET_MS:
                break
            if not self.answers and (time.time() - t0) * 1000 > FAIL_MS:
                break
            self.page.wait_for_timeout(250)
        ms = int((self.last - t0) * 1000) if self.answers else int((time.time() - t0) * 1000)
        return ms, list(self.answers)

    def shot(self) -> bytes | None:
        try:
            return self.page.screenshot(full_page=False)
        except Exception:  # noqa: BLE001
            return None

    def close(self) -> None:
        try:
            self.ctx.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- the suite
def run(base: str, tokens: dict[str, str], ids: dict[str, str], record: Record, log: Callable[[str], None] = print,
        send=_send, keycloak: Keycloak | None = None, playwright=None) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "warning": 0, "skipped": 0}

    def rec(name: str, outcome: str, detail: str, ms: int = 0, **kw) -> None:
        counts[outcome] = counts.get(outcome, 0) + 1
        record(f"reports: {name}", outcome, detail, ms, **kw)

    sid, model = ids.get("sid", ""), ids.get("model", "")
    if not sid or not model:
        rec("Keycloak test users", "skipped", "no test model in this run", 0)
        return counts
    if playwright is None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            rec("every report opens", "skipped", "Playwright is not in this image (the test runner image has it)", 0)
            return counts
        playwright = sync_playwright
    # what the run itself puts in its model: one element committed, one left uncommitted
    tag = f"Self-test reports {sid}"
    committed, uncommitted = f"{tag} committed", f"{tag} uncommitted"
    _content(base, tokens, model, committed, uncommitted, send, log)
    allowed = _readable(base, tokens.get("report-viewer", ""), send)
    kc = keycloak or Keycloak()
    made: dict[str, str] = {}
    t0 = time.time()
    try:
        kc.sign_in()
        for uid in kc.stale(sid):
            kc.remove(uid)
        secret = {}
        for who, role in PEOPLE.items():
            name, pw = f"{PREFIX}{sid}-{who}", password()
            made[who] = kc.make(name, pw, role)
            secret[who] = (name, pw)
    except Exception as exc:  # noqa: BLE001 - nothing else of this suite can run without them
        rec("Keycloak test users", "failed", str(exc)[:300], int((time.time() - t0) * 1000))
        _remove(kc, made, log)
        return counts
    rec("Keycloak test users", "passed", f"{len(made)} made for this run: {', '.join(PEOPLE)}", int((time.time() - t0) * 1000))
    base_r = reports_url()
    host = base_r.split("//", 1)[1].split("/")[0].split(":")[0].removeprefix("reports.")
    proxy = os.environ.get("EAX_TEST_PROXY_HOST", "proxy")
    try:
        with playwright() as pw:
            browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP {host} {proxy}, MAP *.{host} {proxy}"])
            sessions: dict[str, Session] = {}
            for who in PEOPLE:
                t1 = time.time()
                s = Session(browser, who, *secret[who], base_r)
                try:
                    s.sign_in()
                    sessions[who] = s
                    rec(f"{who} signs in to Reports through Keycloak", "passed", "single sign-on", int((time.time() - t1) * 1000))
                except Exception as exc:  # noqa: BLE001
                    rec(f"{who} signs in to Reports through Keycloak", "failed", str(exc).splitlines()[0][:300],
                        int((time.time() - t1) * 1000), screenshot=s.shot())
                    s.close()
            admin, viewer, it = sessions.get("super-admin"), sessions.get("report-viewer"), sessions.get("it-admin")
            dashboards = admin.dashboards() if admin else []
            want = expected_dashboards()
            if admin:
                slugs = {d.get("slug") for d in dashboards}
                missing = sorted(want - slugs)
                rec("the reports are all there", "failed" if missing else "passed",
                    f"missing: {', '.join(missing[:20])}" if missing else f"{len(want)} report dashboards in Reports")
            if it:
                seen = it.dashboards()
                rec("refused: an IT Admin sees no report", "failed" if seen else "passed",
                    f"sees {len(seen)}: {', '.join(str(d.get('dashboard_title')) for d in seen[:5])}" if seen
                    else "no report dashboard (IT Admins see no content, D98)")
            ours = [d for d in dashboards if d.get("slug") in want] or dashboards
            viewer_rows: list[dict] = []
            for who, s in (("super-admin", admin), ("report-viewer", viewer)):
                if s is None:
                    continue
                for d in ours:
                    ms, answers = s.open(d)
                    errors, rows = [], []
                    for status, body in answers:
                        ok, why, got = chart_answer(status, body)
                        if not ok:
                            errors.append(why)
                        rows += got
                    if who == "report-viewer":
                        viewer_rows += rows
                    outcome, detail = verdict(ms, errors, len(answers))
                    rec(f"{d.get('dashboard_title') or d.get('slug')} as {who}", outcome, detail, ms,
                        screenshot=s.shot() if outcome != "passed" else None)
            if viewer is not None and ours:
                seen_models = models_in(viewer_rows)
                other = sorted(seen_models - allowed) if allowed else []
                rec("only their own models: the Report Viewer", "failed" if other else "passed",
                    f"shows models they do not have: {', '.join(other[:10])}" if other
                    else f"{len(seen_models)} model(s) shown, all theirs")
                name = ids.get("model_name", "")
                rec("the run's own model is in the reports", "passed" if name in seen_models else "failed",
                    f"{name} shown" if name in seen_models else f"{name} in no chart (shown: {', '.join(sorted(seen_models)[:10])})")
                found = names_in(viewer_rows)
                rec("committed content shows", "passed" if committed in found else "failed",
                    f"{committed} shown" if committed in found else f"{committed} in no chart")
                rec("uncommitted content never shows", "failed" if uncommitted in found else "passed",
                    f"{uncommitted} shown" if uncommitted in found else "not in any chart")
            if viewer is not None:
                _from_screens(base, tokens, model, viewer, want, rec, send)
            _remove_superset_users(admin, [secret[w][0] for w in PEOPLE if w != "super-admin"], log)
            for s in sessions.values():
                s.close()
            browser.close()
    except Exception as exc:  # noqa: BLE001 - the rest of the run goes on
        rec("every report opens", "failed", str(exc).splitlines()[0][:300], 0)
    finally:
        _remove(kc, made, log)
    files(base, tokens, ids, rec)
    import_log(base, tokens.get("super-admin", ""), rec, send)
    rec("a report deleted in Reports comes back at the next start", "skipped",
        "needs Reports restarted, which a run never does; checked by hand after a restart (fixed 13 Nov 2026)")
    return counts


def _from_screens(base: str, tokens: dict[str, str], model: str, viewer: Session, want: set[str], rec, send) -> None:
    """A model's Reports tab links every report to Reports; one link opened lands on that report, single sign-on."""
    status, text_ = send(base, "get", f"/api/v1/models/{model}/reports", tokens.get("report-viewer", ""), None)
    try:
        data = json.loads(text_) if status == 200 else {}
    except ValueError:
        data = {}
    links = [r.get("url", "") for r in data.get("reports") or []]
    slugs = {u.split("/superset/dashboard/", 1)[1].strip("/") for u in links if "/superset/dashboard/" in u}
    bad = sorted(slugs - want) + ([] if links and all(u.startswith(reports_url()) for u in links) else ["a link not to Reports"])
    rec("from the screens: a model's Reports tab links every report", "failed" if bad or not links else "passed",
        f"{len(links)} links" if links and not bad else f"HTTP {status}; wrong: {', '.join(bad[:5]) or 'none listed'}")
    if not links:
        return
    t0 = time.time()
    first = links[0]
    ms, answers = viewer.open({"url": first[len(reports_url()):]})
    landed = viewer.page.url
    errors = [why for ok, why, _ in (chart_answer(s, b) for s, b in answers) if not ok]
    ok = "/superset/dashboard/" in landed and "/login" not in landed and not errors and answers
    rec("from the screens: a report's link opens it, signed in as the same person", "passed" if ok else "failed",
        f"{len(answers)} charts, no second sign-in" if ok else f"landed on {landed[:120]}; {'; '.join(errors[:3])}",
        int((time.time() - t0) * 1000), screenshot=None if ok else viewer.shot())


def fetch(base: str, path: str, token: str, timeout: int = 120) -> tuple[int, bytes]:
    from ..service_split import route
    req = urllib.request.Request(route(base, path) + path, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:500]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 599, str(exc).encode()


def opens_as(data: bytes, kind: str, name: str = "") -> tuple[bool, str]:
    """Whether the bytes are a file of this kind that opens: a PDF (header and end), a workbook (a zip with its sheets,
    the model's name in it)."""
    if kind == "pdf":
        ok = data.startswith(b"%PDF") and b"%%EOF" in data[-2048:]
        return ok, f"a PDF of {len(data):,} bytes" if ok else "not a PDF"
    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            if "xl/workbook.xml" not in names:
                return False, "a zip, but not a workbook"
            text_ = " ".join(z.read(n).decode("utf-8", "replace") for n in names if n.startswith("xl/") and n.endswith(".xml"))
    except zipfile.BadZipFile:
        return False, "not a workbook"
    sheets = len([n for n in names if n.startswith("xl/worksheets/sheet")])
    if name and name not in text_:
        return False, f"a workbook of {sheets} sheets without the model's name"
    return True, f"a workbook of {sheets} sheets with the model's name"


def files(base: str, tokens: dict[str, str], ids: dict[str, str], rec) -> None:
    """The files a model's reports make, as the Report Viewer (the person who reads them)."""
    m, name, token = ids.get("model", ""), ids.get("model_name", ""), tokens.get("report-viewer", "")
    if not m or not token:
        rec("the files reports make", "skipped", "no test model or Report Viewer in this run")
        return
    for what, path, kind in (("the quality report as PDF", f"/api/v1/models/{m}/quality/pdf", "pdf"),
                             ("the quality report as Excel", f"/api/v1/models/{m}/quality/xlsx", "xlsx"),
                             ("the model's tree as Excel", f"/api/v1/models/{m}/tree/xlsx?scope=entities", "xlsx")):
        t0 = time.time()
        status, data = fetch(base, path, token)
        ok, why = opens_as(data, kind, name) if status == 200 else (False, f"HTTP {status}: {data[:200]!r}")
        rec(f"files: {what}", "passed" if ok else "failed", why, int((time.time() - t0) * 1000))


def import_log(base: str, token: str, rec, send) -> None:
    """What the report import at Reports' start said (eax_import_reports.py): imported, unchanged and failed."""
    status, text_ = send(base, "get", "/api/v1/admin/containers/reports/logs?tail=5000", token, None)
    try:
        lines = json.loads(text_).get("lines") or [] if status == 200 else []
    except ValueError:
        lines = []
    said = [ln for ln in lines if "report dashboards imported:" in ln]
    if not said:
        rec("the import at start-up says what it did", "warning",
            f"HTTP {status}: no import line in Reports' last 5,000 log lines (started long ago, or still loading)")
        return
    last = said[-1].split("report dashboards imported:", 1)[1].strip()
    m = re.search(r"(\d+) failed", last)
    none_failed = bool(m) and m.group(1) == "0"
    rec("the import at start-up says what it did", "passed" if none_failed else "failed", last[:200])


def _content(base: str, tokens: dict[str, str], model: str, committed: str, uncommitted: str, send, log) -> None:
    """An element committed by the Super Admin, and one the Model Admin leaves uncommitted."""
    admin, owner = tokens.get("super-admin", ""), tokens.get("model-admin", "")
    path = f"/api/v1/models/{model}/content/entities"
    try:
        send(base, "post", path, admin, json.dumps({"entity_type": "ApplicationComponent", "name": committed}).encode())
        send(base, "post", f"/api/v1/models/{model}/changes/commit", admin,
             json.dumps({"message": "self-test reports: committed content"}).encode())
        if owner:
            send(base, "post", path, owner, json.dumps({"entity_type": "ApplicationComponent", "name": uncommitted}).encode())
    except Exception as exc:  # noqa: BLE001 - the checks then say what is missing
        log(f"reports: the run's content was not made ({exc})")


def _readable(base: str, token: str, send) -> set[str]:
    """The names of the models a person may read, as EA Explorer says (the same name signs in to Reports)."""
    if not token:
        return set()
    status, text_ = send(base, "get", "/api/v1/models", token, None)
    try:
        data = json.loads(text_)
    except ValueError:
        return set()
    items = data if isinstance(data, list) else data.get("items") or data.get("models") or []
    return {str(m.get("name")) for m in items if isinstance(m, dict) and m.get("name")} if status == 200 else set()


def _remove(kc: Keycloak, made: dict[str, str], log) -> None:
    for who, uid in made.items():
        try:
            if not kc.remove(uid):
                log(f"reports: the Keycloak test user {who} was not deleted")
        except Exception as exc:  # noqa: BLE001
            log(f"reports: the Keycloak test user {who} was not deleted ({exc})")


def _remove_superset_users(admin: Session | None, names: list[str], log) -> None:
    """The Superset users the sign-ins made (Superset keeps a user after their first sign-in), but the Super Admin's own,
    who is signed in; deleted through Superset's security API (FAB_ADD_SECURITY_API)."""
    if admin is None:
        return
    try:
        s, d = admin.api("/api/v1/security/csrf_token/")
        token = (d or {}).get("result", "")
        for name in names:
            q = urllib.parse.quote(json.dumps({"filters": [{"col": "username", "opr": "eq", "value": name}]}))
            s, d = admin.api(f"/api/v1/security/users/?q={q}")
            for u in (d or {}).get("result") or []:
                admin.page.request.delete(f"{admin.base}/api/v1/security/users/{u.get('id')}",
                                          headers={"X-CSRFToken": token, "Referer": admin.base})
    except Exception as exc:  # noqa: BLE001 - a user left in Superset has no role once Keycloak no longer has them
        log(f"reports: the Superset test users were not deleted ({exc})")
