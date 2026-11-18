"""The website's pictures (Release 7.1, D777): one picture of the screen each How do I page is done on, for the pages, the
PDFs printed from them and the videos made from them (the owner, 18 Nov 2026, 13:48: "a seperate how do I file per task
with screenshots. This will help in future pdf generations and making videos").

Run by `eax site shots` in the test runner (Chromium is there), never by `eax test`:

    python -m eax.testing.site_shots [--only PAGE,PAGE] [--missing] [--width 1280] [--height 800]

It reads /site-src/shots/screens.json (docs/site/shots, made by tools/build_website.py: each page, its screen and its
picture's file), signs in through Keycloak as the installation's first Super Admin (EAX_FIRST_ADMIN_USER, eaadmin unless
set, with its password; the owner, 18 Nov 2026, 15:24: "use the existing super admin"), finds the demo model and project
by their names, opens each screen and saves its picture in /site-src/shots. It only opens pages: the Sign in button and
the sign-in form are the only things it clicks or fills; it never changes anything. What it did is written to
/results/site-shots.log (work/tests).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from ..config import secret
from .ui_journeys import base_url

SRC = Path(os.environ.get("EAX_SITE_SRC", "/site-src"))
RESULTS = Path(os.environ.get("EAX_TEST_RESULTS", "/results"))
USER = os.environ.get("EAX_SHOTS_USER") or os.environ.get("EAX_FIRST_ADMIN_USER") or "eaadmin"
MODEL = os.environ.get("EAX_SHOTS_MODEL", "Protea Insurance (demo estate)")
PROJECT = os.environ.get("EAX_SHOTS_PROJECT", "Protea Claims Transformation 2028 (sample)")


def args(argv: list[str]) -> dict:
    """--only a,b (those pages), --missing (only pictures not taken yet), --width and --height (the window)."""
    out = {"only": set(), "missing": False, "width": 1280, "height": 800}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--missing":
            out["missing"] = True
        elif a in ("--only", "--width", "--height") and i + 1 < len(argv):
            i += 1
            out[a[2:]] = {s.strip() for s in argv[i].split(",") if s.strip()} if a == "--only" else int(argv[i])
        else:
            raise SystemExit(f"Not understood: {a}. Usage: site_shots [--only PAGE,PAGE] [--missing] [--width N] [--height N]")
        i += 1
    return out


def wanted(rows: list[dict], only: set[str], missing: bool, folder: Path) -> list[dict]:
    """The screens to take: those pages only, and with --missing those with no picture yet."""
    return [r for r in rows if (not only or r["page"] in only) and not (missing and (folder / r["file"]).is_file())]


def fill(screen: str, ids: dict[str, str]) -> str | None:
    """The screen's address with the demo model's and project's ids put in; None when one it needs was not found."""
    for key, name in (("{m}", "model"), ("{p}", "project")):
        if key in screen:
            if not ids.get(name):
                return None
            screen = screen.replace(key, ids[name])
    return screen


def id_from(links: list[list[str]], name: str, kind: str) -> str:
    """The id in the link that best names it: #/metamodel/<id> for a model, #/projects/<id> for a project. Its words
    exactly the name first (a tile also names other models: "merges into Protea Insurance (demo estate)" picked the
    clean-up model, 18 Nov 2026), then words starting with it, then holding it, then the name without "(...)". A project
    is also found in Project admin's list (#/project-admin/<id>): the Super Admin is on no project, so the other list is
    empty for it (18 Nov 2026, all 48 project pictures skipped)."""
    pattern = r"#/metamodel/([A-Za-z0-9-]+)" if kind == "model" else r"#/project(?:s|-admin)/([A-Za-z0-9-]+)"
    not_ids = ("new", "hierarchy", "drafts", "list", "bases", "template-setup", "principles", "wizards")
    found = []
    for words, href in links:
        m = re.match(pattern + r"/?$", href or "")
        if m and m.group(1) not in not_ids:
            found.append((" ".join((words or "").split()).lower(), m.group(1)))
    want = name.lower()
    short = re.sub(r"\s*\([^)]*\)\s*$", "", want)
    for test in (lambda w: w == want, lambda w: w.startswith(want)):
        for words, ident in found:
            if test(words):
                return ident
    # holding it: the one where it comes nearest the start (a tile starts with its kind mark; another model's tile names
    # it only at its end, "merges into ...", 18 Nov 2026)
    for part in (want, short):
        holding = [(words.index(part), len(words), ident) for words, ident in found if part in words]
        if holding:
            return min(holding)[2]
    return ""


def main(argv: list[str]) -> int:
    """Takes the pictures; returns 1 when the sign-in or every picture failed."""
    opts = args(argv)
    folder = SRC / "shots"
    listed = folder / "screens.json"
    if not listed.is_file():
        print(f"No {listed}: run python tools/build_website.py first (eax site build).")
        return 1
    rows = wanted(json.loads(listed.read_text(encoding="utf-8")), opts["only"], opts["missing"], folder)
    if not rows:
        print("Nothing to take: every picture asked for is there.")
        return 0
    password = secret("EAX_FIRST_ADMIN_PASSWORD")
    if not password:
        print("No password for the first Super Admin (EAX_FIRST_ADMIN_PASSWORD) in the test runner.")
        return 1
    from playwright.sync_api import sync_playwright
    base = base_url()
    host = base.split("//", 1)[1].split("/")[0].split(":")[0]
    proxy = os.environ.get("EAX_TEST_PROXY_HOST", "proxy")
    RESULTS.mkdir(parents=True, exist_ok=True)
    log = (RESULTS / "site-shots.log").open("w", encoding="utf-8")

    def say(line: str) -> None:
        print(line, flush=True)
        log.write(line + "\n")
    taken, failed = 0, 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP {host} {proxy}, MAP *.{host} {proxy}"])
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": opts["width"], "height": opts["height"]},
                                  color_scheme="light", locale="en-GB")
        page = ctx.new_page()
        # sign in through Keycloak, as a person does: the app's Sign in button, then Keycloak's form
        page.goto(f"{base}/#/", wait_until="domcontentloaded", timeout=90000)
        try:
            page.wait_for_selector("#username, button:has-text('Sign in')", timeout=90000)
            if not page.query_selector("#username"):
                page.get_by_role("button", name="Sign in", exact=True).first.click()
                page.wait_for_selector("#username", timeout=60000)
            page.fill("#username", USER)
            page.fill("#password", password)
            page.click("#kc-login")
            page.wait_for_url(lambda u: u.startswith(base) and "/realms/" not in u, timeout=60000)
            page.wait_for_selector("text=EA Explorer", timeout=60000)
        except Exception as exc:  # noqa: BLE001 - the sign-in is the one thing everything needs
            say(f"Could not sign in as {USER} at {page.url.split('?')[0]}: {str(exc).splitlines()[0]}")
            try:
                page.screenshot(path=str(RESULTS / "site-shots-sign-in.png"))
                say("What the browser showed: work/tests/site-shots-sign-in.png")
            except Exception:  # noqa: BLE001
                pass
            browser.close()
            log.close()
            return 1
        # the demo model and project, by their names, from the lists a person opens
        ids: dict[str, str] = {}
        lists = {"model": ("#/work?tab=models", "#/metamodel", "#/model-admin/list"),
                 "project": ("#/work?tab=projects", "#/project-admin/list")}
        for kind, name in (("model", MODEL), ("project", PROJECT)):
            for route in lists[kind]:
                page.goto(f"{base}/{route}", wait_until="domcontentloaded", timeout=60000)
                for _wait in range(5):   # a list can show "Loading..." for a while
                    page.wait_for_timeout(3000)
                    # a tile's or row's bold name, else all its words (a tile also holds its kind mark and "merges into")
                    links = page.eval_on_selector_all(
                        "a", "els => els.map(e => [(e.querySelector('b') || e).textContent, e.getAttribute('href')])")
                    ids[kind] = id_from(links, name, kind)
                    if ids[kind]:
                        break
                if ids[kind]:
                    break
            say(f"The {kind} {name}: " + (ids[kind] or "not found (its pages are left out)"))
        for r in rows:
            address = fill(r["screen"], ids)
            if address is None:
                say(f"  skipped {r['file']}: {r['screen']} needs the demo {'model' if '{m}' in r['screen'] else 'project'}")
                failed += 1
                continue
            t0 = time.time()
            try:
                page.goto(f"{base}/{address}" if address.startswith("#") else f"{base}{address}",
                          wait_until="domcontentloaded", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:  # noqa: BLE001 - a page that keeps a connection open is still drawn
                pass
            page.wait_for_timeout(1500)
            try:
                page.screenshot(path=str(folder / r["file"]), full_page=False)
                taken += 1
                say(f"  {r['file']}  {address}  ({time.time() - t0:.1f}s)")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                say(f"  failed {r['file']}: {str(exc).splitlines()[0]}")
        browser.close()
    say(f"{taken} picture(s) taken, {failed} not, in docs/site/shots. Then: eax site build (the pages show them).")
    log.close()
    return 0 if taken else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
