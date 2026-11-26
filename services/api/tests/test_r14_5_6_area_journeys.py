"""Release 14.5, the rest of the screens (R14.5.7 to R14.5.18; owner, 25 Nov 2026, 14:12: "build all i will test
everything in one go"): a journey an area (eax/testing/ui_flows.AREA_JOURNEYS) that does at least one real thing on each
screen without changing what others see. These tests hold them to the web app's code and to that promise."""

import re
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax.testing import screen_coverage as S  # noqa: E402
from eax.testing import ui_flows as U  # noqa: E402

WEB = "\n".join(p.read_text(encoding="utf-8") for p in sorted((API.parents[1] / "services/web/src").glob("*.js*")))
SAMPLE = {"Vendor contracts"}                    # the sample data's own sheet: optional where it is not loaded


def _acts(j):
    return [s for s in j["steps"] if any(k in s for k in ("click", "fill", "select", "choose", "download"))]


def test_every_label_is_on_a_screen():
    for j in U.AREA_JOURNEYS:
        for s in _acts(j):
            for k in ("click", "fill", "select", "download", "choose", "option"):
                v = s.get(k)
                for part in (x.strip() for x in re.split(r"\{[a-z_]+\}", v) if isinstance(v, str)) if v else []:
                    if len(part) >= 3 and part not in SAMPLE:
                        assert part in WEB, f"{j['name']}: {k} {part!r} is on no screen"


def test_nothing_risky_is_pressed_and_nothing_is_saved():
    saves = re.compile(r"^(Save|Apply|Send|Delete|Remove|Take out|Restore|Restart|Stop|Run|Deploy|Upload|Connect)\b", re.I)
    for j in U.AREA_JOURNEYS:
        for s in j["steps"]:
            w = s.get("click") or ""
            assert not S.RISKY.search(w), f"{j['name']}: {w!r} is a risky control"
            assert not saves.match(w), f"{j['name']}: {w!r} would save or run something"


def test_a_dialog_opened_is_closed_unsaved():
    for j in U.AREA_JOURNEYS:
        st = j["steps"]
        for i, s in enumerate(st):
            if s.get("press") == "Escape":
                assert "click" in st[i - 1], j["name"]


def test_each_screen_opened_is_acted_on():
    for j in U.AREA_JOURNEYS:
        st = j["steps"]
        for i, s in enumerate(st):
            if "open" in s:
                nxt = st[i + 1] if i + 1 < len(st) else {}
                assert U.acts(nxt), f"{j['name']}: {s['open']} is opened and nothing done there"


def test_they_need_no_project_and_read_only():
    assert len({j['name'].split(' (part ')[0] for j in U.AREA_JOURNEYS}) == 8       # eight areas, each in parts
    opened = [s["open"] for j in U.AREA_JOURNEYS for s in j["steps"] if "open" in s]
    assert len(opened) == len(set(opened)) >= 100                       # each screen once
    assert not any(o.startswith("#/projects/{") for o in opened)      # a project's tabs are the project journeys'
    for j in U.AREA_JOURNEYS:
        assert j["why_no_refusal"] and not j.get("refused")
    names = [j["name"] for j in U.journeys({"sid": "x", "model": "11111111-1111-1111-1111-111111111111"})]
    assert all(any(n.startswith(j["name"]) for n in names) for j in U.AREA_JOURNEYS)


def test_none_opens_a_screen_left_out():
    opened = {S.screen(s["open"].replace("{m}", "11111111-1111-1111-1111-111111111111"))
              for j in U.AREA_JOURNEYS for s in j["steps"] if "open" in s}
    assert not opened & set(S.LEFT_OUT_SCREENS)


def test_each_area_is_cut_into_parts_of_a_few_screens():
    """A failed step ends only its part (owner, 25 Nov 2026, 16:20): no part opens more than four screens, every part
    starts by opening one, and the parts together are the area's steps in the same order."""
    for j in U.AREA_JOURNEYS:
        assert "open" in j["steps"][0], j["name"]
        assert 1 <= sum("open" in st for st in j["steps"]) <= 4, j["name"]
    one = {"name": "x", "roles": ["super-admin"], "smoke": False,
           "steps": [{"open": f"#/{i}"} if i % 2 == 0 else {"click": f"c{i}"} for i in range(20)]}
    parts = U.in_parts([one])
    assert [p["name"] for p in parts] == ["x (part 1 of 3)", "x (part 2 of 3)", "x (part 3 of 3)"]
    assert [st for p in parts for st in p["steps"]] == one["steps"] and all(p["roles"] == ["super-admin"] for p in parts)
    assert U.in_parts([{**one, "steps": one["steps"][:4]}])[0]["name"] == "x"                # small enough: one part
    names = [j["name"] for j in U.journeys({"sid": "x", "model": "11111111-1111-1111-1111-111111111111"})]
    assert len(names) == len(set(names))                                                      # each part named once
