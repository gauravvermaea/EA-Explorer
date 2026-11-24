"""The website's pictures (Release 7.1, D777): one picture of the screen each How do I page is done on, for the pages, the
PDFs printed from them and the videos made from them (the owner, 18 Nov 2026, 13:48: "a seperate how do I file per task
with screenshots. This will help in future pdf generations and making videos").

Run by `eax site shots` in the test runner (Chromium is there), never by `eax test`:

    python -m eax.testing.site_shots [--only PAGE,PAGE] [--missing] [--width 1280] [--height 800]

It reads /site-src/shots/screens.json (docs/site/shots, made by tools/build_website.py: each page, its screen, the
things to open on it and its picture's file), signs in through Keycloak as the installation's first Super Admin
(EAX_FIRST_ADMIN_USER, eaadmin unless set, with its password; the owner, 18 Nov 2026, 15:24: "use the existing super
admin"), finds the demo model and project by their names, opens each screen and saves its picture in /site-src/shots.
What it did is written to /results/site-shots.log (work/tests).

It waits for the screen to have drawn before it takes the picture (D781): a screen that polls (the heartbeat every 20
seconds) never goes quiet, so waiting for the network was ending early and four pictures showed only "Loading..."
(18 Nov 2026). It now waits until nothing in the main panel still says it is working, and says in the log when a screen
never settled.

It still changes nothing (D777, widened by D781). Besides the Sign in button and the sign-in form it clicks only what a
page's `do:` line names, and only these four things:

  tab "Deliveries"       a tab or sub-tab, by the words on it: it only shows another part of the same screen
  open "Make a key..."   a button whose label ends in ... (the product's own mark for "this opens a dialog, it does not
                         do it"), or one of the few in OPENERS, each read in the web code and known only to open a dialog
                         or a guide: the dialog is what the task is about. Any other label is refused.
  follow "Claims Platform"   a link, by its words: the browser goes to where it points (a search result, a drawn view),
                         as typing its address would. Nothing is clicked.
  pick "Backups"         a card in a list of cards (the setup guides), by the words it starts with: it only shows that
                         card's page, as a tab does.

After the picture the dialog is closed with Escape, so nothing is left open for the next page.
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



def without_last_brackets(name: str) -> str:
    """A name without its closing "(...)" and the spaces around it ("Retail (sample)" -> "Retail"). String work giving the
    same answer as the regular expression it replaces (SonarQube python:S8786, D804)."""
    t = name.rstrip()
    if not t.endswith(")"):
        return name
    k = t.rfind(")", 0, len(t) - 1)
    i = t.find("(", k + 1, len(t) - 1)
    if i == -1:
        return name
    while i > 0 and name[i - 1].isspace():
        i -= 1
    return name[:i]

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


WORKING = re.compile(r"^(loading|reading|comparing|looking|working out|asking|running|saving|starting|building|"
                     r"fetching|checking|measuring|preparing|opening)\b", re.IGNORECASE)
OPENS_A_DIALOG = re.compile(r"(\.\.\.|…)\s*$")
# buttons with no ... that only open a dialog or a guide, each read in services/web/src (D781): nothing is saved until
# the dialog's own Save, which the picture taker never presses
OPENERS = {"Bring data in", "Take data out",            # Sheets.jsx: setWizard, the two guides (ImportWizards.jsx)
           "+ Add a source",                             # Deliveries.jsx: setEditing({}), the source form
           "Copy as my model's view"}                    # Views.jsx: opens the Copy as my model's view dialog
VERBS = ("tab", "open", "follow", "pick")


def actions(line: str) -> list[tuple[str, str]]:
    """A page's `do:` line as the things to open, in order: tab "Deliveries"; open "Make a key..."; follow "Claims
    Platform"; pick "Backups".

    Only these four verbs exist, and `open` only takes a label that ends in ... (the product's mark for a button that
    opens a dialog instead of doing the thing) or one in OPENERS, so the pictures can never change anything (D781).
    Anything else raises, so a page saying something this cannot do is a build problem, not a silent miss."""
    out: list[tuple[str, str]] = []
    for part in [s.strip() for s in (line or "").split(";") if s.strip()]:
        m = re.fullmatch(r"(tab|open|follow|pick)\s+\"([^\"]+)\"", part)
        if not m:
            raise ValueError(f'do: not understood: {part} (tab, open, follow or pick "words", separated by ;)')
        verb, label = m.group(1), m.group(2).strip()
        if verb == "open" and not OPENS_A_DIALOG.search(label) and label not in OPENERS:
            raise ValueError(f'do: open "{label}" is refused: only a label ending in ... or one in OPENERS (D781)')
        out.append((verb, label))
    return out


def same_words(verb: str, words: str, label: str) -> bool:
    """Whether an element's words are the label's: the same, or with an icon before them ("⬇ Bring data in"); a tab may
    carry a count after ("Relations (8)"); a card or a link starts with them (a card goes on to say what it is for)."""
    if words == label or words.endswith(" " + label):
        return True
    if verb == "tab":
        return bool(re.fullmatch(re.escape(label) + r"\s*\(\d+\)", words))
    return verb in ("pick", "follow") and words.startswith(label)


def settle(page, seconds: int = 25) -> bool:
    """Waits until the main panel has drawn: no line in it still says it is working. True when it settled."""
    for _ in range(seconds * 2):
        try:
            busy = page.eval_on_selector_all(
                "main p, main div.loading, main h1, main td",
                "els => els.slice(0, 40).map(e => (e.textContent || '').trim()).filter(Boolean)")
        except Exception:  # noqa: BLE001 - the page is still being replaced: wait and look again
            busy = ["Loading"]
        if not any(WORKING.match(t) for t in busy):
            return True
        page.wait_for_timeout(500)
    return False


def do_actions(page, line: str, say) -> None:
    """Opens what the page's `do:` line names, before the picture is taken. A step that finds nothing is said in the
    log and the rest go on: a part-right picture is better than none, and the log says which page to look at."""
    for verb, label in actions(line):
        where = {"tab": "[role=tab], .tabs button, .tabs a, .seg button, .cf-view", "open": "button, a.button, .actions button",
                 "follow": "a[href]", "pick": ".cc-card, .cards button, .tile a, .tile button"}[verb]
        found = False
        for el in page.query_selector_all(where):
            if not same_words(verb, " ".join((el.text_content() or "").split()), label) or not el.is_visible():
                continue
            if verb == "follow":   # go where it points, as typing the address would (a link may open a new tab)
                href = el.get_attribute("href") or ""
                if href.startswith("#"):
                    href = page.url.split("#")[0] + href
                page.goto(href, wait_until="domcontentloaded", timeout=60000)
                settle(page, 20)
            else:
                el.click()
                page.wait_for_timeout(700)
                settle(page, 10)
            found = True
            break
        if not found:
            say(f"    nothing called {label!r} to {verb} on this screen")


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
    short = without_last_brackets(want)
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
        browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP {host} {proxy}, MAP *.{host} {proxy}", "--disable-dev-shm-usage"])
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
            # the screen has to have drawn: waiting for the network to go quiet is not enough on a screen that polls
            # (the heartbeat every 20 seconds), which gave four pictures of "Loading..." on 18 Nov 2026 (D781)
            drawn = settle(page)
            if not drawn:
                say(f"    {r['file']}: still loading after 25s; the picture may show it")
            page.wait_for_timeout(800)
            if r.get("do"):
                try:
                    do_actions(page, r["do"], say)
                except ValueError as exc:
                    say(f"  failed {r['file']}: {exc}")
                    failed += 1
                    continue
            try:
                page.screenshot(path=str(folder / r["file"]), full_page=False)
                taken += 1
                say(f"  {r['file']}  {address}{'  ' + r['do'] if r.get('do') else ''}  ({time.time() - t0:.1f}s)")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                say(f"  failed {r['file']}: {str(exc).splitlines()[0]}")
            if r.get("do"):
                try:   # close a dialog that was opened, so nothing is left over for the next page
                    page.keyboard.press("Escape")
                except Exception:  # noqa: BLE001
                    pass
        browser.close()
    say(f"{taken} picture(s) taken, {failed} not, in docs/site/shots. Then: eax site build (the pages show them).")
    log.close()
    return 0 if taken else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
