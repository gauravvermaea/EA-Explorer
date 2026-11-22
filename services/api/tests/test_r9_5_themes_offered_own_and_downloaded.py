"""R9.5 (D827; owner, 21 Nov 2026: "if we choose people to pick themes, then we should be able to limit what they
choose. Another setting is we can allow everyone to make there own theme ... We also need the ability to download a
theme CSS so that people can download and share"; "This is for custom themes too"): which themes people may pick, their
own themes when allowed, and any theme downloaded as CSS."""

from __future__ import annotations

from pathlib import Path

import pytest

from eax import branding as B
from eax import personal as P

REPO = Path(__file__).resolve().parents[3]
EVERY = [{"slug": s, "name": s, "built_in": True} for s in ("standard", "dark", "high-contrast")] + \
        [{"slug": "acme", "name": "Acme", "built_in": False}]
GOOD = ":root { --accent: #0a7; }\n.top { border-color: var(--accent); }\n"


@pytest.fixture()
def store(monkeypatch):
    """The organisation's choice and each person's settings, in memory."""
    choice = dict(B.DEFAULT, personal=True)
    mine: dict[tuple[str, str], object] = {}
    monkeypatch.setattr(B, "get_choice", lambda conn: dict(choice))
    monkeypatch.setattr(B, "themes", lambda conn: list(EVERY))
    monkeypatch.setattr(P, "get_settings", lambda conn, u: {k: v for (who, k), v in mine.items() if who == u})
    monkeypatch.setattr(P, "put_setting", lambda conn, u, k, v: mine.__setitem__((u, k), v) or {"key": k, "value": v})
    monkeypatch.setattr(P, "delete_setting", lambda conn, u, k: mine.pop((u, k), None) or {"deleted": k})
    monkeypatch.setattr(P, "rows", lambda conn, sql, **p: [{"username": u, "key": k, "value": v} for (u, k), v in
                                                           sorted(mine.items()) if k.startswith(B.OWN_KEY)])
    return choice, mine


def test_every_theme_is_offered_unless_taken_off_and_the_organisations_always():
    assert B.offered({"theme": "standard", "hidden": []}, EVERY) == ["standard", "dark", "high-contrast", "acme"]
    assert B.offered({"theme": "dark", "hidden": ["dark", "acme"]}, EVERY) == ["standard", "dark", "high-contrast"]


def test_a_theme_not_offered_is_refused_and_the_organisations_is_always_fine(store):
    choice, mine = store
    choice["hidden"] = ["acme"]
    assert B.set_look(None, "thandi", "dark") == {"theme": "dark"} and mine[("thandi", "theme")] == "dark"
    with pytest.raises(B.BrandingError) as exc:
        B.set_look(None, "thandi", "acme")                     # a custom one taken off (owner: "for custom themes too")
    assert exc.value.status == 403
    assert B.set_look(None, "thandi", None) == {"theme": None} and ("thandi", "theme") not in mine
    choice["personal"] = False
    with pytest.raises(B.BrandingError):
        B.set_look(None, "thandi", "dark")                     # nobody picks when the Super Admins do not allow it


def test_own_themes_only_when_switched_on_checked_and_theirs_alone(store):
    choice, mine = store
    with pytest.raises(B.BrandingError, match="not switched on"):
        B.save_own(None, "thandi", "Mine", GOOD)
    choice["own"] = True
    assert B.save_own(None, "thandi", "My Blue", GOOD) == {"slug": "my-blue", "name": "My Blue", "size": len(GOOD)}
    assert [t["slug"] for t in B.own_themes(None, "thandi")] == ["my-blue"] and B.own_themes(None, "sipho") == []
    assert B.may_use(None, "thandi", B.OWN_KEY + "my-blue") and not B.may_use(None, "sipho", B.OWN_KEY + "my-blue")
    assert B.set_look(None, "thandi", B.OWN_KEY + "my-blue")["theme"] == B.OWN_KEY + "my-blue"
    for bad in ("@import url(x.css);", ".a { background: url(https://x/y.png); }", "@font-face { font-family: x; }"):
        with pytest.raises(B.BrandingError):
            B.save_own(None, "thandi", "Bad", bad)
    with pytest.raises(B.BrandingError, match="KB"):
        B.save_own(None, "thandi", "Big", ":root{--a:#000}" + " " * (B.OWN_MAX_CSS + 1))


def test_at_most_ten_and_switching_off_falls_back_without_losing_them(store):
    choice, mine = store
    choice["own"] = True
    for n in range(B.OWN_MAX):
        B.save_own(None, "thandi", f"T{n}", GOOD)
    with pytest.raises(B.BrandingError, match="at most"):
        B.save_own(None, "thandi", "One more", GOOD)
    B.save_own(None, "thandi", "T0", GOOD + "/* again */")          # the same name replaces
    B.set_look(None, "thandi", B.OWN_KEY + "t0")
    choice["own"] = False
    assert not B.may_use(None, "thandi", B.OWN_KEY + "t0")           # the screens fall back (themeFor)
    assert len(B.own_themes(None, "thandi")) == B.OWN_MAX             # kept, unused


def test_a_value_put_there_by_other_means_is_never_served_unchecked(store):
    _, mine = store
    mine[("thandi", B.OWN_KEY + "sneaky")] = {"name": "Sneaky", "css": "@import url(https://evil/x.css);"}
    with pytest.raises(B.BrandingError):
        B.own_css(None, "thandi", "sneaky")
    mine[("thandi", B.OWN_KEY + "fine")] = {"name": "Fine", "css": GOOD}
    assert B.own_css(None, "thandi", "fine") == ("Fine", GOOD)        # the download is the same bytes as kept


def test_removing_ones_own_theme_and_a_super_admin_removing_one(store):
    choice, mine = store
    choice["own"] = True
    B.save_own(None, "thandi", "Mine", GOOD)
    B.set_look(None, "thandi", B.OWN_KEY + "mine")
    assert [(t["username"], t["slug"]) for t in B.own_in_use(None)] == [("thandi", "mine")]
    B.remove_own_of(None, "thandi", "mine")
    assert ("thandi", "theme") not in mine and B.own_in_use(None) == []   # back on the organisation's


def test_the_choice_keeps_the_offered_list_and_the_switch(monkeypatch):
    saved = {}

    class Conn:
        def execute(self, sql, params=None):
            saved.update(params or {})

            class R:
                def scalar(self):
                    return None
            return R()
    monkeypatch.setattr(B, "themes", lambda conn: list(EVERY))
    monkeypatch.setattr(B, "theme_css", lambda conn, slug: (slug, ""))
    out = B.set_choice(Conn(), {"theme": "dark", "own": True, "hidden": ["acme", "dark", "nope"]}, "sa")
    assert out["own"] is True and out["hidden"] == ["acme"]          # never the organisation's own, never an unknown one


def test_the_screens_offer_only_those_and_download_every_one():
    js = (REPO / "services/web/src/branding.jsx").read_text(encoding="utf-8")
    assert 'apiFetch("/api/v1/branding/my-look", { method: "PUT"' in js and "data.offered" in js
    assert "Download CSS" in js and "Upload a theme" in js and "<ThemeDesigner mine" in js
    assert "The theme you chose is no longer one you may use" in js
    admin = (REPO / "services/web/src/BrandingAdmin.jsx").read_text(encoding="utf-8")
    assert "People may pick it" in admin and "People may make their own themes" in admin and "/api/v1/admin/branding/own-themes" in admin
    td = (REPO / "services/web/src/ThemeDesigner.jsx").read_text(encoding="utf-8")
    assert '"/api/v1/branding/my-themes", { method: "POST"' in td
    api = (REPO / "services/api/eax/api/branding.py").read_text(encoding="utf-8")
    for route in ('"/branding/my-look"', '"/branding/my-themes"', '"/branding/my-themes/<string:slug>.css"',
                  '"/admin/branding/own-themes"'):
        assert f"@blp.route({route})" in api, route
    assert "/me/" not in api.split("each person's own look", 1)[1]   # never under /me (the personal service's prefix)
