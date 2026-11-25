"""The self-test's browser journeys (phase 36.1, D367, D524, D529): the main journeys through the screens, in the run's
own fixtures, signed in as the run's test accounts.

Two ways, the same journeys (journeys()):
  * **headless on the server** (the default): Chromium in the test runner opens the installation's own screens through
    the front door (the proxy container, reached by its Docker name: the public host name is mapped to it inside the
    browser), each journey in its own context with a video; a failed one keeps a screenshot and its video;
  * **watched in the admin's own browser** (Self-test > Watch it in this browser): the Self-test page opens the same
    screens in a frame of its own and drives them (TestRuns.jsx), recording each journey with the browser's name and
    version; no extension is needed.
Either way the screens are opened with ?eaxselftest=<ticket>&eaxrole=<role>: the app then signs in with the run's own
token for that role (auth.js, D529) instead of Keycloak, so the admin's sign-in is never used and the journeys can only
see and change what the role may: the run's own fixtures (and read standard screens)."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path


def _csp(kind: str, text: str) -> bool:
    from .ui_pages import csp_blocked
    return csp_blocked(kind, text)

Record = Callable[..., None]


def base_url() -> str:
    """The address the test's browser opens (EAX_TEST_BASE_URL, else the installation's)."""
    explicit = os.environ.get("EAX_TEST_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    host, port = os.environ.get("EAX_HOSTNAME", "localhost"), os.environ.get("EAX_HTTPS_PORT", "443")
    return f"https://{host}" + ("" if port == "443" else f":{port}")


def journeys(ids: dict[str, str], role: str = "") -> list[dict]:
    """[{name, role, steps: [{route, expect}]}]: each step opens a route and waits for its text (empty: the page settles).
    With a role, each journey runs as that role."""
    m, p = ids.get("model", ""), ids.get("project", "")
    out = [
        {"name": "sign in and the start page", "role": "architect", "steps": [{"route": "#/", "expect": "Start"}]},
        {"name": "a model: overview, grid and quality", "role": "model-admin",
         "steps": [{"route": f"#/metamodel/{m}", "expect": ids.get("model_name", "")}, {"route": f"#/metamodel/{m}/grid", "expect": ""},
                   {"route": f"#/metamodel/{m}/quality", "expect": "Quality"}]},
        {"name": "the models list", "role": "architect", "steps": [{"route": "#/metamodel", "expect": "Models"}]},
        {"name": "System admin: health and machine access", "role": "super-admin",
         "steps": [{"route": "#/admin/health", "expect": "Health"}, {"route": "#/admin/machine-access", "expect": "Machine access"}]},
    ]
    if p:
        out.insert(2, {"name": "a project and its tasks", "role": "super-admin",
                       "steps": [{"route": f"#/projects/{p}", "expect": ids.get("project_name", "")}, {"route": f"#/projects/{p}/tasks", "expect": ""}]})
    if not m:
        out = [j for j in out if "model:" not in j["name"]]
    if role:
        out = [{**j, "role": role} for j in out]
    return out


def run(ids: dict[str, str], ticket: str, folder: Path, record: Record, role: str = "", only: list[str] | None = None) -> None:
    """The simple journeys: each opens its pages as its role, in a browser of its own."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        record("browser journeys", "skipped", "Playwright is not in this image (the test runner image has it)", 0)
        return
    base = base_url()
    host = base.split("//", 1)[1].split("/")[0].split(":")[0]
    proxy = os.environ.get("EAX_TEST_PROXY_HOST", "proxy")
    videos = folder / "videos"
    videos.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP {host} {proxy}, MAP *.{host} {proxy}", "--disable-dev-shm-usage"])
        version = f"Chromium {browser.version} (headless, on the server)"
        for j in journeys(ids, role):
            if only and j["name"] not in only:
                continue
            t0 = time.time()
            ctx = browser.new_context(ignore_https_errors=True, record_video_dir=str(videos), viewport={"width": 1400, "height": 900})
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e, errs=errors: errs.append(str(e)))
            page.on("console", lambda m, errs=errors: errs.append(f"blocked by the Content-Security-Policy: {m.text[:200]}")
                    if _csp(m.type, m.text) else None)   # R3.12, D672
            page.on("response", lambda r, errs=errors: errs.append(f"{r.request.method} {r.url.split('?')[0]}: {r.status}")
                    if "/api/" in r.url and r.status >= 500 else None)
            outcome, detail, shot = "passed", "", None
            try:
                for step in j["steps"]:
                    page.goto(f"{base}/?eaxselftest={ticket}&eaxrole={j['role']}{step['route']}", wait_until="domcontentloaded",
                              timeout=60000)
                    page.wait_for_selector("text=EA Explorer", timeout=60000)
                    if step["expect"]:
                        page.wait_for_selector(f"text={step['expect']}", timeout=30000)
                    page.wait_for_timeout(1500)
                if errors:
                    outcome, detail = "failed", "; ".join(errors[:20])
                else:
                    detail = f"{len(j['steps'])} page(s) as {j['role']}"
            except Exception as exc:  # noqa: BLE001 - a journey that breaks is a failed journey
                outcome = "failed"
                detail = str(exc).splitlines()[0][:500] + (f"; also: {'; '.join(errors[:5])}" if errors else "")
            if outcome == "failed":
                try:
                    shot = page.screenshot(full_page=False)
                except Exception:  # noqa: BLE001
                    shot = None
            video = page.video.path() if page.video else None
            ctx.close()
            kept = ""
            if video:
                v = Path(video)
                if outcome == "failed":
                    kept = f"{''.join(c if c.isalnum() else '-' for c in j['name'])[:60]}.webm"
                    v.rename(videos / kept)
                else:
                    v.unlink(missing_ok=True)
            record(f"journey: {j['name']}", outcome, detail, int((time.time() - t0) * 1000), screenshot=shot,
                   video=f"videos/{kept}" if kept else "", browser=version)
        browser.close()


def run_all(ids: dict[str, str], ticket: str, folder: Path, record: Record, role: str = "", smoke: bool = False,
            journeys: list[str] | None = None, pages_only: bool = False, routes: list[str] | None = None,
            names: set[str] | None = None, live: dict | None = None) -> dict[str, int]:
    """The browser suite (D575, D576): the page sweep (every page, group, tab and sub-tab, as Super Admin) and the journeys
    that click, type and save (each as the roles allowed, and refused to one that is not), headless. Returns the counts
    for the report's coverage summary. A repeat (R2.36) gives names (the "journey: …" results to run again) and routes
    (the pages to open again, no crawl): only those run. live (R5.20): {engine, run_id, slow, keep}: every page can be
    watched on Self-test > Watch > Live browser (streamed only while someone watches, screencast.py); slow: Playwright's
    slow motion and pause after each step; keep: every journey's video and Playwright trace kept, passed or not."""
    repeat = names is not None
    from . import ui_flows, ui_pages
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        record("browser", "skipped", "Playwright is not in this image (the test runner image has it)", 0)
        return {}
    base = base_url()
    host = base.split("//", 1)[1].split("/")[0].split(":")[0]
    proxy = os.environ.get("EAX_TEST_PROXY_HOST", "proxy")
    videos = folder / "videos"
    videos.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    live = live or {}
    from . import screencast
    n_browser = [0]
    from . import screen_coverage
    # the screens' coverage (R14.5.1, D924): only in a whole browser suite, the page sweep and every journey
    whole = not repeat and not journeys and not pages_only
    screens = screen_coverage.Collector() if whole else None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP {host} {proxy}, MAP *.{host} {proxy}", "--disable-dev-shm-usage"],
                                     **({"slow_mo": screencast.SLOW_MS} if live.get("slow") else {}))
        version = f"Chromium {browser.version} (headless, on the server)"

        def context(as_role: str, video: bool = True, label: str = ""):
            ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900},
                                      **({"record_video_dir": str(videos)} if video else {}))
            page = ctx.new_page()
            page.on("dialog", lambda d: d.accept())
            caster = None
            if live.get("engine") is not None:          # watchable live (R5.20): nothing is captured unless watched
                n_browser[0] += 1
                try:
                    caster = screencast.Caster(live["engine"], live["run_id"], f"{n_browser[0]:03d}",
                                               label or f"as {as_role}", page)
                    caster.hold = lambda: _hold(live, caster)
                except Exception:  # noqa: BLE001 - no live view: the run goes on as before
                    caster = None
            page._eax_caster = caster                    # ui_flows ticks it at each step
            page._eax_screens = screens                  # ui_flows notes each action's screen (R14.5.1)

            def open_route(route: str, r=as_role) -> None:
                if caster is not None:
                    caster.tick(f"open {route}")
                page.goto(f"{base}/?eaxselftest={ticket}&eaxrole={r}{route}", wait_until="domcontentloaded", timeout=60000)
            return ctx, page, open_route

        def rec(name, outcome, detail="", ms=0, **kw):
            record(name, outcome, detail, ms, browser=version, **kw)

        if (not repeat and not journeys) or (repeat and routes):          # the page sweep (or the failed pages again)
            ctx, page, open_route = context(role if role else "super-admin", video=False, label="the page sweep")
            counts.update({f"pages_{k}" if k != "pages" else k: v
                           for k, v in ui_pages.sweep(page, open_route, ids, rec, role=role or "super-admin",
                                                      routes=list(routes) if repeat else None, screens=screens).items()})
            _close_caster(page)
            ctx.close()
            if not repeat or "#/break-glass" in (routes or []):        # in a browser of its own (R3.13)
                alone = browser.new_context(ignore_https_errors=True, viewport={"width": 1400, "height": 900})
                ui_pages.break_glass_page(alone.new_page(), base, rec)
                alone.close()
        if not pages_only and (not repeat or names):                      # the journeys
            def factory(as_role: str, name: str = ""):
                ctx, page, open_route = context(as_role, label=f"journey: {name}" if name else "")
                if live.get("keep"):                     # a run started to be watched: its trace too (R5.20 (4))
                    try:
                        ctx.tracing.start(screenshots=True, snapshots=True)
                    except Exception:  # noqa: BLE001
                        pass

                def close(outcome: str, c=ctx, p=page) -> str:
                    _close_caster(p)
                    stem = f"journey-{int(time.time() * 1000)}"
                    if live.get("keep"):
                        try:
                            c.tracing.stop(path=str(videos / f"{stem}.trace.zip"))
                        except Exception:  # noqa: BLE001
                            pass
                    video = p.video.path() if p.video else None
                    c.close()
                    if not video:
                        return ""
                    v = Path(video)
                    if outcome == "failed" or live.get("keep"):   # kept: every journey of a watched run (R5.20)
                        kept = f"{stem}.webm"
                        v.rename(videos / kept)
                        return f"videos/{kept}"
                    v.unlink(missing_ok=True)
                    return ""
                return page, open_route, close
            js = ui_flows.journeys(ids, role=role, only=journeys, smoke=smoke)
            if repeat:
                js = [j for j in js if f"journey: {j['name']}" in names]
            jc = ui_flows.run(factory, js, rec)
            counts.update({f"journeys_{k}" if k != "journeys" else k: v for k, v in jc.items()})
        browser.close()
    if screens is not None:
        counts.update(screens_result(screens, folder, rec, risky=bool(ids.get("risky"))))
    return counts


def screens_result(screens, folder: Path, rec, risky: bool = False) -> dict[str, float]:
    """The screens' coverage (R14.5.1, D924): screens-coverage.json in the run's folder and one result line."""
    from . import screen_coverage
    t0 = time.time()
    got = screen_coverage.summarise(screens, risky=risky)
    try:
        screen_coverage.save(folder, got)
    except OSError:
        pass
    outcome, detail = screen_coverage.line(got)
    rec("coverage: the screens used by the journeys", outcome, detail, int((time.time() - t0) * 1000))
    return {"screens %": got["percent"]} if got.get("percent") is not None else {}


def _close_caster(page) -> None:
    caster = getattr(page, "_eax_caster", None)
    if caster is not None:
        try:
            caster.close()
        except Exception:  # noqa: BLE001
            pass


def _hold(live: dict, caster) -> None:
    """After a step of a run started to be watched (R5.20 (3)): while someone watches and it is paused, wait for Step
    or Continue."""
    from . import screencast
    if not (live.get("slow") and caster.watched):
        return
    if screencast.controls(live["engine"], live["run_id"]).get("paused"):
        caster.tick("paused: Step or Continue on the Live browser panel")
        screencast.hold(live["engine"], live["run_id"])
