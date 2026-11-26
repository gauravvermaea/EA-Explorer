"""Release 14.5, batch 1, the screens (owner, 25 Nov 2026, 12:12: "Please build both API and screens"): the project's
workspace a journey a tab (eax/testing/ui_flows.PROJECT_JOURNEYS). These tests hold each journey to the screens' own code:
every button, field, option and message it names is in the web app's source, so a label typed wrong fails here, not in
the owner's run."""

import re
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax.testing import ui_flows as U  # noqa: E402

WEB = "\n".join(p.read_text(encoding="utf-8") for p in sorted((API.parents[1] / "services/web/src").glob("*.js*")))
SERVER = "\n".join(p.read_text(encoding="utf-8") for p in sorted((API / "eax").glob("*.py")))
P = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
IDS = {"sid": "e4fa1d33dfd8", "model": "11111111-1111-1111-1111-111111111111", "project": P}


def _words(j: dict) -> list[tuple[str, str]]:
    out = []
    for s in j["steps"] + ([j["refused"]] if j.get("refused") else []):
        for k in ("click", "fill", "select", "download", "disabled_or_absent", "expect", "option"):
            v = s.get(k)
            if isinstance(v, str) and v:
                out.append((k, v))
    return out


# labels a screen builds from its data, and the source that builds them
BUILT = {"＋ Log a record": ('＋ Log {kind === "*" ? "a record"',)}


def test_every_label_a_project_journey_names_is_on_its_screen():
    for j in U.PROJECT_JOURNEYS:
        for k, v in _words(j):
            if v in BUILT:
                assert all(x in WEB for x in BUILT[v]), v
                continue
            fixed = re.split(r"self_test_\{sid\}|\{[a-z_]+\}", v)          # the run's own names are made by the steps
            for part in (x.strip() for x in fixed):
                if len(part) < 3 or part in (".", "'s"):
                    continue
                assert part in WEB or part in SERVER, f"{j['name']}: {k} {part!r} is in no screen or message"


def test_each_project_journey_works_in_the_runs_project_and_is_refused_for_the_stakeholder():
    assert len(U.PROJECT_JOURNEYS) == 13
    for j in U.PROJECT_JOURNEYS:
        assert j["name"].startswith("project ")
        assert all(s["open"].startswith("#/projects/{p}") for s in j["steps"] if "open" in s), j["name"]
        if j.get("refused"):
            assert j["refused"]["role"] == "report-viewer" and j["refused"]["open"].startswith("#/projects/{p}/")
        else:
            assert j["why_no_refusal"]
        made = [s["value"] for s in j["steps"] if "fill" in s and "self_test_{sid}" in str(s.get("value"))
                and not s["fill"].startswith("Search")]           # a search may look for part of the name
        for v in made:
            assert v.startswith("self_test_{sid}") and v.endswith("{role}"), (j["name"], v)   # never two roles' clash


def test_what_a_journey_makes_it_takes_out_where_the_screen_can():
    takes_out = ("🗑", "Remove", "Take out", "Take out…", "Delete")
    for j in U.PROJECT_JOURNEYS:
        if j["name"].startswith(("project tabs that show", "project tracking sheet")):
            continue                                       # reads; a sheet has no delete on its screen (goes with the project)
        acts = [s.get("click") or s.get("option") for s in j["steps"]]
        assert any(a and (a.startswith(takes_out) or a.startswith("Remove this")) for a in acts), j["name"]


def test_the_ones_that_ask_window_confirm_run_headless_only():
    confirm = {"project principles: add one, take it out", "project stakeholders: add one, open it, take it out",
               "project journeys: make a journey with a stage, remove it"}
    for j in U.PROJECT_JOURNEYS:
        assert bool(j.get("headless_only")) == (j["name"] in confirm), j["name"]
        if j.get("headless_only"):
            assert "window.confirm" in j["why_headless"]


def test_they_run_with_the_project_and_not_without_it():
    names = [j["name"] for j in U.journeys(IDS)]          # a journey of two roles runs as each ("... as architect")
    for j in U.PROJECT_JOURNEYS:
        assert any(n == j["name"] or n.startswith((j["name"] + " as ", j["name"] + " (part ")) for n in names), j["name"]
    none = {j["name"] for j in U.journeys({k: v for k, v in IDS.items() if k != "project"})}
    assert not any(n.startswith("project ") for n in none)
