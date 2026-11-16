"""R5.5.2 (owner, 15 Nov 2026, 19:59: "when we watch live UI of testing can we make it full screen"; 20:35: "A thin
bar"): the Live browser has a Full screen button; in full screen the picture fills the screen, scaled to fit, with a
thin bar at the top (the step, Pause, Step and Continue in slow motion, Exit full screen) that hides after a few seconds
and comes back when the mouse moves. Nothing more is captured: the same picture as the panel."""
import json
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web" / "src"
SRC = (WEB / "TestWatch.jsx").read_text(encoding="utf-8")


def test_full_screen_button_and_the_browsers_own_full_screen():
    assert "requestFullscreen" in SRC and "exitFullscreen" in SRC and "fullscreenchange" in SRC
    assert ">Full screen</button>" in SRC and ">Exit full screen</button>" in SRC


def test_the_thin_bar_has_the_step_and_the_controls_and_hides():
    bar = SRC[SRC.index('className={`live-bar'):SRC.index("</div>)}", SRC.index('className={`live-bar'))]
    for want in ("tile?.step", '"Continue" : "Pause"', 'control("step")', "Exit full screen"):
        assert want in bar, want
    assert "BAR_HIDE_MS" in SRC and '"mousemove"' in SRC and 'setBar(false)' in SRC
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    assert ".live-bar.hidden { opacity: 0" in css and "object-fit: contain" in css


def test_nothing_more_is_captured():
    assert SRC.count("/live-browser?large=") == 1          # the same one request for the picture


def test_help_for_the_buttons():
    c = json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert c.get("button:Full screen") and c.get("button:Exit full screen")
