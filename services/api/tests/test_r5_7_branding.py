"""R5.7-B1, logo and branding (owner, 16 Nov 2026; agreed 16:14 and 17 Nov 13:49; D729): Super Admins set the logo,
the browser tab's icon, the name in the top bar and the organisation's theme; four themes ship; Super Admins add their
own as CSS of looks only; each person may pick their own when allowed; nobody is ever locked out. In the database, so
backups, restores and site copies carry it. The database checks run on EAX_MIGRATED_TEST_DSN, rolled back."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from eax import branding as B
from eax.metamodel_edit import EditError

API = Path(__file__).resolve().parents[1]
WEB = API.parent / "web" / "src"
DSN = os.environ.get("EAX_MIGRATED_TEST_DSN", "")
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000")


# ---------------------------------------------------------------- the themes that ship
def test_four_themes_ship_and_each_passes_its_own_check():
    assert list(B.BUILT_IN)[:4] == ["standard", "dark", "high-contrast", "corporate"]
    # and the colour themes (owner, 17 Nov 2026, 15:21: "1. Blue 2. Red 3. Green 4. And around 5-10 more")
    assert {"blue", "red", "green"} <= set(B.BUILT_IN) and 8 <= len(B.BUILT_IN) - 7 <= 13
    assert {p.stem for p in B.THEMES_DIR.glob("*.css")} == set(B.BUILT_IN)
    for slug in B.BUILT_IN:
        assert B.check_css(B.built_in_css(slug))


def test_the_standard_theme_is_todays_look():
    """Standard (light) is today's look (owner, 16:15): its colours are the screens' own, value for value."""
    def colours(css):
        return dict(re.findall(r"(--[a-z-]+):\s*(#[0-9a-f]{3,6})", css.split("}", 1)[0]))
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    assert colours(B.built_in_css("standard")) == colours(styles)


def test_every_shipped_theme_sets_every_colour():
    names = set(re.findall(r"(--[a-z-]+):", B.built_in_css("standard")))
    for slug in B.BUILT_IN:
        assert names <= set(re.findall(r"(--[a-z-]+):", B.built_in_css(slug))), slug


# ---------------------------------------------------------------- an uploaded theme holds only looks
@pytest.mark.parametrize("css", [
    "@import 'https://elsewhere.example/x.css';",
    ":root { background: url(https://elsewhere.example/x.png); }",
    ":root { background: URL ( x.png ); }",
    "@font-face { font-family: X; src: local(Arial); }",
    "div { width: expression(alert(1)); }",
    "a { behavior: url(x.htc); }",
    "a { -moz-binding: none; }",
    "</style><script>alert(1)</script>",
    ":root { --x: \\75rl(x); }",
    "a { background-image: image-set('x.png' 1x); }",
    ":root { color: red; ",
    ":root { color: red; }}",
    "/* not closed :root { color: red; }",
    ":root { font-family: \"Arial; }",
    "",
])
def test_anything_but_looks_is_refused(css):
    with pytest.raises(EditError):
        B.check_css(css)


def test_a_refusal_says_the_line_and_what():
    with pytest.raises(EditError, match=r"line 3: url"):
        B.check_css(":root {\n  --accent: #123456;\n  background: url(x.png);\n}")


def test_looks_are_kept_as_they_are():
    css = ':root { --accent: #0b6e4f; font-family: "Segoe UI", Arial; }\nh1 > span { border-radius: 2px; }  /* ok */'
    assert B.check_css(css) == css
    assert B.check_css(css.encode("utf-8")) == css
    with pytest.raises(EditError):
        B.check_css("x" * (B.MAX_CSS + 1))


def test_which_theme_a_person_sees_is_decided_on_the_screen():
    js = (WEB / "branding.jsx").read_text(encoding="utf-8")
    # break-glass and the rescue link always give the standard look; a removed theme gives the standard look
    assert "if (!data || breakGlass || rescued) return \"standard\";" in js
    assert "if (data.personal && mine) {" in js and "else if (offered.has(mine) && every.has(mine)) return mine;" in js   # only the themes offered (R9.5)
    assert "every.has(data.theme) ? data.theme : \"standard\"" in js
    # the CSS goes in as text, never as HTML
    assert "el.textContent = css;" in js and "innerHTML" not in js


def test_the_screens_wire_it_in():
    app = (WEB / "App.jsx").read_text(encoding="utf-8")
    assert "<BrandMark />" in app and "loadBranding()" in app and "useLookFromRoute(route)" in app
    assert '"#/my-profile?look=standard"' in (WEB / "menu.js").read_text(encoding="utf-8")
    admin = (WEB / "Admin.jsx").read_text(encoding="utf-8")
    assert '["branding", "Branding", () => can("settings.manage"), ["super-admin"]]' in admin
    assert "<MyLook />" in (WEB / "Skills.jsx").read_text(encoding="utf-8")


def test_only_super_admins_change_it():
    src = (API / "eax" / "api" / "branding.py").read_text(encoding="utf-8")
    admin_parts = src.split('@blp.route("/admin/branding")', 1)[1]
    assert admin_parts.count('@require_auth("settings.manage")') == 9          # with the fonts' two (D736) and people's own themes' two (R9.5)
    assert src.split('@blp.route("/admin/branding")', 1)[0].count('@require_auth("settings.manage")') == 0


def test_the_api_is_registered():
    from eax.app import create_app
    rules = {r.rule for r in create_app().url_map.iter_rules()}
    assert {"/api/v1/branding", "/api/v1/admin/branding", "/api/v1/admin/branding/themes",
            "/api/v1/branding/themes/<string:slug>.css"} <= rules


# ---------------------------------------------------------------- on a real database
needs_db = pytest.mark.skipif(not DSN, reason="needs EAX_MIGRATED_TEST_DSN (a database every migration has run on)")


@pytest.fixture
def conn():
    from sqlalchemy import create_engine
    eng = create_engine(DSN)
    with eng.connect() as c:
        tx = c.begin()
        try:
            yield c
        finally:
            tx.rollback()


@needs_db
def test_the_standard_look_until_a_super_admin_chooses(conn):
    from sqlalchemy import text
    conn.execute(text("DELETE FROM core.settings WHERE key = 'branding'"))
    s = B.state(conn)
    assert s["theme"] == "standard" and s["personal"] is False and s["product_name"] == ""
    assert [t["slug"] for t in s["themes"]][:len(B.BUILT_IN)] == list(B.BUILT_IN)


@needs_db
def test_a_super_admin_adds_a_theme_chooses_it_and_removes_it(conn):
    from sqlalchemy import text
    conn.execute(text("DELETE FROM core.settings WHERE key = 'branding'"))
    t = B.save_theme(conn, "Test teal", ":root { --accent: #0b6e4f; }", "tester")
    assert t["slug"] == "test-teal"
    B.set_choice(conn, {"theme": "test-teal", "personal": True, "product_name": "  Our   Atlas "}, "tester")
    s = B.state(conn)
    assert (s["theme"], s["personal"], s["product_name"]) == ("test-teal", True, "Our Atlas")
    assert B.theme_css(conn, "test-teal")[1] == ":root { --accent: #0b6e4f; }"
    B.save_theme(conn, "Test teal", ":root { --accent: #111111; }", "tester", slug="test-teal")   # replaced
    assert "#111111" in B.theme_css(conn, "test-teal")[1]
    B.delete_theme(conn, "test-teal", "tester")
    assert B.state(conn)["theme"] == "standard"           # the organisation's theme gone: the standard look


@needs_db
def test_the_shipped_themes_cannot_be_replaced_or_removed_and_unknown_ones_are_refused(conn):
    with pytest.raises(EditError):
        B.save_theme(conn, "Dark", ":root { --accent: #000; }", "tester", slug="dark")
    with pytest.raises(EditError):
        B.delete_theme(conn, "standard", "tester")
    with pytest.raises(EditError):
        B.set_choice(conn, {"theme": "no-such-theme"}, "tester")
    with pytest.raises(EditError):
        B.save_theme(conn, "Bad", "@import 'x.css';", "tester")


@needs_db
def test_the_logo_is_an_image_kept_in_the_database(conn):
    out = B.set_file(conn, "logo", PNG, "tester")
    assert out["content_type"] == "image/png"
    assert B.get_file(conn, "logo") == (PNG, "image/png")
    assert B.state(conn)["files"]["logo"]["size"] == len(PNG)
    with pytest.raises(EditError):
        B.set_file(conn, "logo", b"<svg><script>alert(1)</script></svg>", "tester")
    with pytest.raises(EditError):
        B.set_file(conn, "favicon", b"x" * (B.FILES["favicon"] + 1), "tester")
    B.delete_file(conn, "logo")
    with pytest.raises(EditError):
        B.get_file(conn, "logo")


def test_a_theme_chosen_is_shown_at_once_and_kept_by_save():
    """Owner, 17 Nov 2026, 15:21: "When we select a theme it should be immediately applied so someone can see what it
    feels like and save makes it permanent"."""
    js = (WEB / "branding.jsx").read_text(encoding="utf-8")
    admin = (WEB / "BrandingAdmin.jsx").read_text(encoding="utf-8")
    assert "export async function previewTheme(" in js and "export async function endPreview(" in js
    assert "previewTheme(e.target.value)" in admin and "await endPreview()" in admin
    assert "useEffect(() => () => { void endPreview(); }, [])" in admin         # leaving unsaved goes back
    assert "apiText(cssUrl(slug)).then(previewCss)" in js and "chooseMine(trying)" in js   # My look: shown at once, Save keeps it (R9.5: own themes too)


def test_the_theme_designer_copies_a_theme_and_changes_colours_fonts_and_corners():
    """Owner, 17 Nov 2026, 15:27 to 15:28: "add theme designer"; "make copy of a theme and change colors using color
    picker"; "change fonts etx" (D735)."""
    td = (WEB / "ThemeDesigner.jsx").read_text(encoding="utf-8")
    assert 'type="color"' in td and "Start from a copy of" in td
    for var in ("--accent", "--accent-soft", "--ink", "--quiet", "--bg", "--card", "--line", "--ok", "--bad"):
        assert f'["{var}",' in td, var
    assert "Text font" in td and "Headings font" in td and "Text size" in td and "Corners" in td
    assert "previewCss(makeCss(base, t, fonts))" in td                                     # every change shows at once
    assert "Save as a new theme" in td and "/api/v1/admin/branding/themes" in td
    fonts = td.split("export const FONTS = {", 1)[1].split("};", 1)[0]
    assert "url(" not in fonts and "@" not in fonts                                   # the computers' own fonts only
    assert "<ThemeDesigner themes={data.themes} fonts={data.fonts || []} />" in (WEB / "BrandingAdmin.jsx").read_text(encoding="utf-8")


# ---------------------------------------------------------------- fonts uploaded for the themes (D736)
def test_a_font_is_known_by_its_first_bytes():
    assert B.font_type(b"wOF2" + b"x" * 20) == "font/woff2" and B.font_type(b"wOFF....") == "font/woff"
    assert B.font_type(b"\x00\x01\x00\x00....") == "font/ttf" and B.font_type(b"OTTO....") == "font/otf"
    for bad in (b"<svg></svg>", b"\x89PNG....", b"@font-face{}"):
        with pytest.raises(EditError):
            B.font_type(bad)


def test_the_screens_load_uploaded_fonts_and_the_designer_offers_them():
    js = (WEB / "branding.jsx").read_text(encoding="utf-8")
    assert "new FontFace(f.family, await apiBytes(" in js and "await loadFonts(data?.fonts)" in js   # bytes from our own API
    td = (WEB / "ThemeDesigner.jsx").read_text(encoding="utf-8")
    assert "export const withUploaded" in td and "(uploaded)" in td
    admin = (WEB / "BrandingAdmin.jsx").read_text(encoding="utf-8")
    assert "<Fonts fonts={data.fonts || []}" in admin and "/api/v1/admin/branding/fonts" in admin
    src = (API / "eax" / "api" / "branding.py").read_text(encoding="utf-8")
    fonts_part = src.split('@blp.route("/admin/branding/fonts")', 1)[1].split("each person's own look", 1)[0]
    assert '@blp.route("/admin/branding/fonts")' in src and fonts_part.count('@require_auth("settings.manage")') == 2


@needs_db
def test_a_font_is_kept_replaced_and_removed(conn):
    ttf = b"\x00\x01\x00\x00" + b"\x00" * 200
    out = B.set_font(conn, "Meridian Sans", ttf, "tester")
    assert out == {"slug": "meridian-sans", "family": "Meridian Sans", "content_type": "font/ttf", "size": 204}
    B.set_font(conn, "Meridian Sans", b"wOF2" + b"\x00" * 50, "tester", weight="bold")
    B.set_font(conn, "Meridian Sans", b"OTTO" + b"\x00" * 60, "tester")                    # the regular one replaced
    fs = {f["slug"]: f for f in B.fonts(conn)}
    assert set(fs) == {"meridian-sans", "meridian-sans-bold"} and fs["meridian-sans"]["content_type"] == "font/otf"
    assert B.get_font(conn, "meridian-sans-bold")[1] == "font/woff2"
    assert [f["family"] for f in B.state(conn)["fonts"]] == ["Meridian Sans", "Meridian Sans"]
    for bad in (("serif", ttf), ("Bad;name", ttf), ("Big", b"wOF2" + b"0" * B.MAX_FONT), ("Not a font", b"<svg/>")):
        with pytest.raises(EditError):
            B.set_font(conn, bad[0], bad[1], "tester")
    with pytest.raises(EditError):
        B.set_font(conn, "Meridian-Sans", ttf, "tester")                                      # too like the one there
    B.delete_font(conn, "meridian-sans-bold")
    assert [f["slug"] for f in B.fonts(conn)] == ["meridian-sans"]
