"""Logo and branding (R5.7-B1; owner, 16 Nov 2026, 09:44: "The users can white lable it by 1. Adding Logo 2. Have skin
3. In this story add 3-4 themes to choose from. Admin can upload download CSS and update and add new CSS for a company
and a logo"). Only EA Explorer's own screens (owner, 09:45; and 17 Nov 13:49: the files EA Explorer makes keep its mark).

  * the choice, in core.settings under the key `branding`: {theme, personal, product_name}; the theme every screen
    uses, whether each person may pick their own from those offered (a switch), and the name in the top bar
  * the logo and the small one for the browser tab, in core.branding_files (PNG, JPEG, WebP or SVG, checked as the
    model icons are)
  * the themes: four ship with EA Explorer (eax/branding_themes/*.css: standard, dark, high contrast, corporate) and
    Super Admins add their own in core.branding_themes, each a CSS file of looks only, checked before it is kept
  * all three are in the database, so a backup, a restore and a site copy carry them

Super Admins change them (settings.manage); everyone signed in reads them. A theme never locks anyone out: the screens
offer the standard look in each person's menu (#/my-profile?look=standard) and a break-glass session always uses it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text

from .metamodel_edit import EditError
from .model_icons import sniff

SETTING = "branding"
# hidden: the themes people may not pick for themselves (R9.5, D827: every theme offered unless taken off, a new one too;
# the organisation's own always offered); own: people may make or upload their own themes (off by default)
DEFAULT = {"theme": "standard", "personal": False, "product_name": "", "hidden": [], "own": False}
OWN_KEY = "own-theme."          # a person's own theme, in their own settings: own-theme.<slug> = {name, css}
OWN_MAX = 10                    # themes a person may keep
OWN_MAX_CSS = 60 * 1024         # a person's theme is kept with their settings (at most 64 KB each)
THEMES_DIR = Path(__file__).resolve().parent / "branding_themes"
# the four agreed first (owner, 16 Nov 2026, 16:15): standard light (today's look), dark, high contrast, muted corporate;
# then twelve colours (17 Nov, 15:21)
BUILT_IN = {"standard": "Standard (light)", "dark": "Dark", "high-contrast": "High contrast", "corporate": "Corporate (muted)",
            # colour themes (owner, 17 Nov 2026, 15:21: "add more themes 1. Blue 2. Red 3. Green 4. And around 5-10 more")
            **{s: s.capitalize() for s in ("blue", "red", "green", "teal", "purple", "orange", "rose", "indigo", "gold",
                                            "graphite", "navy", "sand")}}
FILES = {"logo": 512 * 1024, "favicon": 128 * 1024}      # the logo and the browser tab's icon, and their largest size
MAX_CSS = 128 * 1024
_STYLE_OR_SCRIPT = re.compile(r"style|script", re.I)


def html_in_css(css: str) -> int:
    """Where the first piece of HTML is in a theme's CSS (< or > then style or script, maybe with a / and spaces;
    </; <!--; -->), or -1. String work giving the same answer as the regular expression it replaces (D804)."""
    n = len(css)
    for p, ch in enumerate(css):
        if ch == "-" and css.startswith("-->", p):
            return p
        if ch == "<" and (css.startswith("</", p) or css.startswith("<!--", p)):
            return p
        if ch in "<>":
            q = p + 1
            while q < n and css[q].isspace():
                q += 1
            if q < n and css[q] == "/":
                q += 1
                while q < n and css[q].isspace():
                    q += 1
            if _STYLE_OR_SCRIPT.match(css, q):
                return p
    return -1


SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
# what a theme may not hold: nothing that loads from elsewhere or runs, nothing that hides what it is (owner, 16 Nov:
# "only the look: colours, fonts, spacing; nothing that loads from elsewhere or runs")
REFUSED = [
    (re.compile(r"@import", re.I), "@import (it loads another file)"),
    (re.compile(r"url\s*\(", re.I), "url(...) (it loads from elsewhere; use colours, not pictures)"),
    (re.compile(r"image-set\s*\(|-webkit-image-set", re.I), "image-set(...) (it loads pictures)"),
    (re.compile(r"@font-face", re.I), "@font-face (it loads a font; name fonts the computers already have)"),
    (re.compile(r"@namespace|@charset", re.I), "@namespace or @charset"),
    (re.compile(r"expression\s*\(|javascript:|vbscript:|behavior\s*:|-moz-binding", re.I), "something that runs"),
    (None, "HTML in the CSS"),          # html_in_css below (D804: was a regular expression with slow cases)
    (re.compile(r"\\"), "a backslash escape (write the characters as they are)"),
    (re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]"), "control characters"),
]


class BrandingError(EditError):
    """A branding change refused, with the reason people read (and the HTTP status)."""


def slug_of(name: str) -> str:
    """A theme's short name made from its name: letters, digits and hyphens."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40].strip("-")
    return s or "theme"


def check_css(css: Any) -> str:
    """The theme's CSS when it holds only looks; refuses anything that loads from elsewhere or runs, with the line."""
    if isinstance(css, bytes):
        try:
            css = css.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise BrandingError("The CSS is not UTF-8 text.") from exc
    if not isinstance(css, str) or not css.strip():
        raise BrandingError("The CSS is empty.")
    if len(css.encode("utf-8")) > MAX_CSS:
        raise BrandingError(f"The CSS is larger than {MAX_CSS // 1024} KB.")
    found = []
    for rx, what in REFUSED:
        at = html_in_css(css) if rx is None else (m.start() if (m := rx.search(css)) else -1)
        if at != -1:
            found.append(f"line {css.count(chr(10), 0, at) + 1}: {what}")
    if found:
        raise BrandingError("The CSS may hold only looks (colours, fonts, spacing, corners). Take out: " + "; ".join(found) + ".")
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if "/*" in body:
        raise BrandingError("A comment in the CSS is not closed (/* without */).")
    body = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', '""', body)
    depth = 0
    for i, ch in enumerate(body):
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0:
            raise BrandingError(f"Line {body.count(chr(10), 0, i) + 1}: a }} with no {{ before it.")
    if depth:
        raise BrandingError("A { in the CSS is not closed.")
    if '"' in body.replace('""', "") or "'" in body:
        raise BrandingError("A quote in the CSS is not closed on its line.")
    return css


def built_in_css(slug: str) -> str:
    """The CSS of a theme that ships with EA Explorer."""
    return (THEMES_DIR / f"{slug}.css").read_text(encoding="utf-8")


def get_choice(conn) -> dict:
    """The organisation's choice: its theme, whether people pick their own, the product name."""
    v = conn.execute(text("SELECT value FROM core.settings WHERE key = :k"), {"k": SETTING}).scalar()
    out = dict(DEFAULT)
    if isinstance(v, dict):
        out.update({k: v[k] for k in DEFAULT if k in v})
    return out


def themes(conn) -> list[dict]:
    """Every theme offered: the four that ship, then those the Super Admins added."""
    rows = conn.execute(text("""SELECT slug, name, set_by, set_at, length(css) AS size FROM core.branding_themes
                                ORDER BY lower(name)""")).mappings().all()
    out = [{"slug": s, "name": n, "built_in": True} for s, n in BUILT_IN.items()]
    out += [{"slug": r["slug"], "name": r["name"], "built_in": False, "set_by": r["set_by"],
             "set_at": r["set_at"].isoformat() if r["set_at"] else None, "size": r["size"]} for r in rows]
    return out


def theme_css(conn, slug: str) -> tuple[str, str]:
    """(name, css) of a theme, built in or added."""
    if slug in BUILT_IN:
        return BUILT_IN[slug], built_in_css(slug)
    r = conn.execute(text("SELECT name, css FROM core.branding_themes WHERE slug = :s"), {"s": slug}).first()
    if not r:
        raise BrandingError(f"There is no theme {slug!r}.", 404)
    return r[0], r[1]


def files(conn) -> dict:
    """Which images are set (logo, browser tab's icon), with their type, size and when."""
    rows = conn.execute(text("SELECT key, content_type, length(data) AS size, set_at FROM core.branding_files")).mappings().all()
    return {r["key"]: {"content_type": r["content_type"], "size": r["size"],
                       "v": int(r["set_at"].timestamp()) if r["set_at"] else 0} for r in rows}


# ---------------------------------------------------------------- fonts uploaded for the themes (D736)
MAX_FONT = 2 * 1024 * 1024
FONT_TYPES = [(b"wOF2", "font/woff2"), (b"wOFF", "font/woff"), (b"\x00\x01\x00\x00", "font/ttf"), (b"true", "font/ttf"),
              (b"OTTO", "font/otf")]
FAMILY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,59}$")


def font_type(data: bytes) -> str:
    """A font file's type from its first bytes (never from its name): WOFF2, WOFF, TrueType or OpenType."""
    for magic, ct in FONT_TYPES:
        if data[:4] == magic:
            return ct
    raise BrandingError("The font must be a WOFF2, WOFF, TrueType (.ttf) or OpenType (.otf) file.")


def fonts(conn) -> list[dict]:
    """The fonts uploaded for the themes: the family a theme names, its weight and style, its size."""
    rows = conn.execute(text("""SELECT slug, family, weight, style, content_type, length(data) AS size, set_by, set_at
                                  FROM core.branding_fonts ORDER BY lower(family), weight, style""")).mappings().all()
    return [{**dict(r), "set_at": r["set_at"].isoformat() if r["set_at"] else None,
             "v": int(r["set_at"].timestamp()) if r["set_at"] else 0} for r in rows]


def set_font(conn, family: str, data: bytes, by: str, weight: str = "normal", style: str = "normal") -> dict:
    """Keeps a font file under a family name: one file for each family, weight and style (regular, bold, italic, bold
    italic); uploading one again replaces it."""
    family = re.sub(r"\s+", " ", str(family or "")).strip()
    if not FAMILY.match(family):
        raise BrandingError("Name the font family in letters, digits, spaces and hyphens (at most 60).")
    if family.lower() in {"system-ui", "serif", "sans-serif", "monospace", "inherit", "initial"}:
        raise BrandingError(f"{family} is a name the browser keeps for itself: choose another.")
    weight = weight if weight in ("normal", "bold") else "normal"
    style = style if style in ("normal", "italic") else "normal"
    if not data:
        raise BrandingError("Send the font as a file.")
    if len(data) > MAX_FONT:
        raise BrandingError(f"The font is larger than {MAX_FONT // (1024 * 1024)} MB.")
    ct = font_type(data)
    slug = slug_of(" ".join(x for x in (family, "" if weight == "normal" else weight, "" if style == "normal" else style) if x))
    other = conn.execute(text("SELECT family FROM core.branding_fonts WHERE slug = :s AND family <> :f"), {"s": slug, "f": family}).scalar()
    if other:
        raise BrandingError(f"{family} is too like the font {other} already here: remove that one, or name this one differently.", 409)
    conn.execute(text("""INSERT INTO core.branding_fonts (slug, family, weight, style, content_type, data, set_by)
                         VALUES (:s, :f, :w, :st, :c, :d, :b)
                         ON CONFLICT (family, weight, style) DO UPDATE SET content_type = EXCLUDED.content_type, data = EXCLUDED.data,
                             set_by = EXCLUDED.set_by, set_at = now()"""),
                 {"s": slug, "f": family, "w": weight, "st": style, "c": ct, "d": data, "b": by})
    return {"slug": slug, "family": family, "content_type": ct, "size": len(data)}


def get_font(conn, slug: str) -> tuple[bytes, str]:
    """A font file and its type; refused when there is none."""
    r = conn.execute(text("SELECT data, content_type FROM core.branding_fonts WHERE slug = :s"), {"s": slug}).first()
    if not r:
        raise BrandingError("There is no such font.", 404)
    return bytes(r[0]), r[1]


def delete_font(conn, slug: str) -> dict:
    """Removes a font; a theme that names it falls back to the next font in its list."""
    n = conn.execute(text("DELETE FROM core.branding_fonts WHERE slug = :s"), {"s": slug}).rowcount
    if not n:
        raise BrandingError("There is no such font.", 404)
    return {"removed": slug}


def offered(choice: dict, every: list[dict]) -> list[str]:
    """The themes people may pick for themselves (pure): every theme but those taken off, the organisation's always."""
    hidden = set(choice.get("hidden") or [])
    return [t["slug"] for t in every if t["slug"] not in hidden or t["slug"] == choice.get("theme")]


def state(conn) -> dict:
    """What every screen needs: the theme in use, whether people may pick (and which), whether they may make their own,
    the name, the logo, the themes."""
    c = get_choice(conn)
    every = themes(conn)
    have = {t["slug"] for t in every}
    if c["theme"] not in have:          # a theme removed: the standard look, never nothing
        c["theme"] = "standard"
    return {**c, "themes": every, "offered": offered(c, every), "files": files(conn), "fonts": fonts(conn)}


# ---------------------------------------------------------------- each person's own look (R9.5, D827)
def may_use(conn, username: str, slug: str) -> bool:
    """Whether a person may use this theme now: one offered (when people may pick), or one of their own (when people
    may make their own)."""
    c = get_choice(conn)
    if not c.get("personal"):
        return False
    if slug.startswith(OWN_KEY):
        return bool(c.get("own")) and slug[len(OWN_KEY):] in {t["slug"] for t in own_themes(conn, username)}
    return slug in offered(c, themes(conn))


def set_look(conn, username: str, slug: str | None) -> dict:
    """A person's own choice of theme (None: the organisation's); refused when it is not theirs to pick."""
    from . import personal as P
    if not slug:
        P.delete_setting(conn, username, "theme")
        return {"theme": None}
    if not may_use(conn, username, slug):
        raise BrandingError("That theme is not one you may pick: choose one offered on My look.", 403)
    P.put_setting(conn, username, "theme", slug)
    return {"theme": slug}


def own_themes(conn, username: str) -> list[dict]:
    """A person's own themes: slug, name, size (theirs only)."""
    from . import personal as P
    out = []
    for k, v in P.get_settings(conn, username).items():
        if k.startswith(OWN_KEY) and isinstance(v, dict):
            out.append({"slug": k[len(OWN_KEY):], "name": str(v.get("name") or k[len(OWN_KEY):]),
                        "size": len(str(v.get("css") or "").encode("utf-8"))})
    return sorted(out, key=lambda t: t["name"].lower())


def own_css(conn, username: str, slug: str) -> tuple[str, str]:
    """(name, css) of one of a person's own themes, checked again as it is read (a value put there by other means is
    never served unchecked)."""
    from . import personal as P
    v = P.get_settings(conn, username).get(OWN_KEY + slug)
    if not isinstance(v, dict):
        raise BrandingError("You have no such theme.", 404)
    return str(v.get("name") or slug), check_css(v.get("css"))


def save_own(conn, username: str, name: Any, css: Any) -> dict:
    """Keeps a theme of a person's own (made in the designer or uploaded): checked as an uploaded theme is, small, at
    most OWN_MAX of them; saving under the same name replaces it."""
    from . import personal as P
    c = get_choice(conn)
    if not (c.get("personal") and c.get("own")):
        raise BrandingError("Making your own themes is not switched on (System Admin > Branding).", 403)
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not name or len(name) > 60:
        raise BrandingError("Name the theme (at most 60 characters).")
    css = check_css(css)
    if len(css.encode("utf-8")) > OWN_MAX_CSS:
        raise BrandingError(f"Your own theme is at most {OWN_MAX_CSS // 1024} KB.")
    slug = slug_of(name)
    have = {t["slug"] for t in own_themes(conn, username)}
    if slug not in have and len(have) >= OWN_MAX:
        raise BrandingError(f"You keep at most {OWN_MAX} themes of your own: remove one first.")
    P.put_setting(conn, username, OWN_KEY + slug, {"name": name, "css": css})
    return {"slug": slug, "name": name, "size": len(css.encode("utf-8"))}


def delete_own(conn, username: str, slug: str) -> dict:
    """Removes a theme of a person's own; when they were using it, they are back on the organisation's."""
    from . import personal as P
    if OWN_KEY + slug not in P.get_settings(conn, username):
        raise BrandingError("You have no such theme.", 404)
    P.delete_setting(conn, username, OWN_KEY + slug)
    if P.get_settings(conn, username).get("theme") == OWN_KEY + slug:
        P.delete_setting(conn, username, "theme")
    return {"removed": slug}


def own_in_use(conn) -> list[dict]:
    """Super Admins: who keeps themes of their own, each with its name and size (to remove one that causes trouble)."""
    from . import personal as P
    rows = P.rows(conn, "SELECT username, key, value FROM personal.settings WHERE key LIKE :k ORDER BY username, key",
                  k=OWN_KEY + "%")
    return [{"username": r["username"], "slug": r["key"][len(OWN_KEY):], "name": str((r["value"] or {}).get("name") or ""),
             "size": len(str((r["value"] or {}).get("css") or "").encode("utf-8"))} for r in rows]


def remove_own_of(conn, username: str, slug: str) -> dict:
    """Super Admins: a person's own theme removed (they are back on the organisation's if they used it)."""
    return delete_own(conn, username, slug)


def set_choice(conn, data: dict, by: str) -> dict:
    """Changes the organisation's theme, the switch for each person's own, or the product name."""
    c = get_choice(conn)
    if "theme" in data:
        slug = str(data.get("theme") or "standard")
        theme_css(conn, slug)                   # refuses one that does not exist
        c["theme"] = slug
    if "personal" in data:
        c["personal"] = bool(data.get("personal"))
    if "own" in data:
        c["own"] = bool(data.get("own"))
    if "hidden" in data:
        have = {t["slug"] for t in themes(conn)}
        hidden = [str(x) for x in (data.get("hidden") or []) if str(x) in have and str(x) != c["theme"]]
        c["hidden"] = sorted(set(hidden))
    if "product_name" in data:
        name = re.sub(r"\s+", " ", str(data.get("product_name") or "")).strip()
        if len(name) > 60:
            raise BrandingError("The product name is at most 60 characters.")
        c["product_name"] = name
    conn.execute(text("""INSERT INTO core.settings (key, value, name) VALUES (:k, CAST(:v AS jsonb), 'Logo and branding')
                         ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, modified_at = now(),
                             modified_by = :by, row_version = core.settings.row_version + 1"""),
                 {"k": SETTING, "v": json.dumps(c), "by": by})
    return c


def save_theme(conn, name: str, css: Any, by: str, slug: str | None = None) -> dict:
    """Adds a theme, or replaces an added one (its slug); the four that ship cannot be replaced (download one, change it
    and add it under a name of its own)."""
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not name or len(name) > 60:
        raise BrandingError("Give the theme a name of at most 60 characters.")
    css = check_css(css)
    slug = slug or slug_of(name)
    if not SLUG.match(slug):
        raise BrandingError("The theme's short name is letters, digits and hyphens.")
    if slug in BUILT_IN:
        raise BrandingError(f"{BUILT_IN[slug]} ships with EA Explorer and cannot be replaced: add yours under another name.", 409)
    conn.execute(text("""INSERT INTO core.branding_themes (slug, name, css, set_by) VALUES (:s, :n, :c, :b)
                         ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, css = EXCLUDED.css, set_by = EXCLUDED.set_by,
                             set_at = now()"""), {"s": slug, "n": name, "c": css, "b": by})
    return {"slug": slug, "name": name, "size": len(css)}


def delete_theme(conn, slug: str, by: str) -> dict:
    """Removes a theme the Super Admins added; the standard look when it was the organisation's."""
    if slug in BUILT_IN:
        raise BrandingError("The themes that ship with EA Explorer cannot be removed.", 409)
    n = conn.execute(text("DELETE FROM core.branding_themes WHERE slug = :s"), {"s": slug}).rowcount
    if not n:
        raise BrandingError(f"There is no theme {slug!r}.", 404)
    c = get_choice(conn)
    if c["theme"] == slug:                  # the organisation's theme gone: back to the standard look
        set_choice(conn, {"theme": "standard"}, by)
    return {"removed": slug}


def set_file(conn, key: str, data: bytes, by: str) -> dict:
    """Keeps the logo or the browser tab's icon, once it is checked to be a safe image."""
    if key not in FILES:
        raise BrandingError("Only the logo and the browser tab's icon.", 404)
    if not data:
        raise BrandingError("Send the image as a file.")
    if len(data) > FILES[key]:
        raise BrandingError(f"The image is larger than {FILES[key] // 1024} KB.")
    ct = sniff(data)
    conn.execute(text("""INSERT INTO core.branding_files (key, content_type, data, set_by) VALUES (:k, :c, :d, :b)
                         ON CONFLICT (key) DO UPDATE SET content_type = EXCLUDED.content_type, data = EXCLUDED.data,
                             set_by = EXCLUDED.set_by, set_at = now()"""), {"k": key, "c": ct, "d": data, "b": by})
    return {"key": key, "content_type": ct, "size": len(data)}


def get_file(conn, key: str) -> tuple[bytes, str]:
    """The logo or the browser tab's icon, with its type; refused when none is set."""
    r = conn.execute(text("SELECT data, content_type FROM core.branding_files WHERE key = :k"), {"k": key}).first()
    if not r:
        raise BrandingError("None is set.", 404)
    return bytes(r[0]), r[1]


def delete_file(conn, key: str) -> dict:
    """Removes the logo or the browser tab's icon."""
    n = conn.execute(text("DELETE FROM core.branding_files WHERE key = :k"), {"k": key}).rowcount
    return {"removed": key if n else None}
