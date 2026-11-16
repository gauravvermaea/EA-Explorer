"""R5.42: on the Logs page the containers were a small list box with arrows that did not look like a choice (owner,
16 Nov 2026, 07:36: "can the api be made into drop down. Not sure how to use this screen. Please put guidance in help in
more detail"). Now a drop-down with a tick per container (one or several, never none), labelled From and to, and the
Container logs help walks through the screen step by step."""
import json
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web" / "src"
SRC = (WEB / "ContainerConsole.jsx").read_text(encoding="utf-8")


def test_containers_are_a_drop_down_of_ticks():
    assert "<select multiple" not in SRC
    assert "<ContainerPick all={all} pick={pick}" in SRC
    pick = SRC[SRC.index("function ContainerPick"):SRC.index("function LogLine")]
    assert '<details className="pick-drop"' in pick and 'type="checkbox"' in pick
    assert "if (next.length) setPick(next)" in pick          # never none
    assert ".pick-drop" in (WEB / "styles.css").read_text(encoding="utf-8")


def test_the_time_window_is_labelled():
    assert "From <input type=\"time\"" in SRC and "to <input type=\"time\"" in SRC


def test_the_help_walks_through_the_screen():
    c = json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))
    tab = c["tab:Container logs"]
    assert len(tab["how"]) >= 6 and "request id" in " ".join(tab["how"]) and "UTC" in " ".join(tab["how"])
    assert "tick" in c["field:Containers"] and "Ctrl" not in c["field:Containers"]
    for k in ("field:Since", "field:Live", "button:Clean logs…"):
        assert c.get(k), k
