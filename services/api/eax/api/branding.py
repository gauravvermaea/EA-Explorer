"""Logo and branding (R5.7-B1, D729): the look of EA Explorer's own screens.

GET    /branding                     what every screen needs: the theme in use, whether people may pick their own, the
                                     product name, the themes offered, which images are set (everyone signed in)
GET    /branding/logo, /favicon      the image (everyone signed in)
GET    /branding/themes/<slug>.css   a theme's CSS, to use or to download and change (everyone signed in)
PUT    /admin/branding               {theme, personal, product_name} (Super Admins)
POST   /admin/branding/logo          the image as a file (multipart "file", or the body); DELETE removes it (Super Admins)
POST   /admin/branding/favicon       the same for the browser tab's icon
POST   /admin/branding/themes        {name, css[, slug]}: add a theme or replace an added one (Super Admins)
DELETE /admin/branding/themes/<slug> remove an added theme (Super Admins)
GET    /branding/fonts/<slug>        an uploaded font's file, which the screens load for the themes (everyone signed in)
POST   /admin/branding/fonts         a font file (multipart "file", with family, weight normal|bold, style normal|italic)
DELETE /admin/branding/fonts/<slug>  remove an uploaded font (Super Admins)
PUT    /branding/my-look              {theme}: my own theme, one offered or one of my own (null: the organisation's) (R9.5)
GET    /branding/my-themes            my own themes, and whether I may make them; POST {name, css} keeps one (R9.5)
DELETE /branding/my-themes/<slug>     removes one of my own themes
GET    /branding/my-themes/<slug>.css one of my own themes' CSS (?download=1 to save it)
GET    /admin/branding/own-themes     who keeps themes of their own (Super Admins); DELETE .../<user>/<slug> removes one
"""

from __future__ import annotations

from flask import Response, g, request
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from .. import audit
from .. import branding as B
from ..auth import require_auth
from ..db import get_engine
from ..metamodel_edit import EditError
from .models import Free, FreeIn

blp = Blueprint("branding", __name__, url_prefix="/api/v1", description="Logo and branding of the screens (R5.7-B1)")
SECURITY = [{"bearerAuth": []}]
SAFE = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "X-Content-Type-Options": "nosniff"}


def _run(fn, write: bool = False, action: str | None = None, details=None):
    try:
        with (get_engine().begin() if write else get_engine().connect()) as conn:
            out = fn(conn)
            if action:
                audit.record(conn, actor=g.user.username, action=action, object_type="branding", object_id="branding",
                             details=details(out) if callable(details) else (details or {}),
                             request_id=getattr(g, "request_id", None))
            return out
    except EditError as exc:
        abort(getattr(exc, "status", 400), message=str(exc))


@blp.route("/branding")
class Branding(MethodView):
    """/api/v1/branding: GET what every screen needs: the theme in use, whether each person may pick their own, the
    product name, the themes offered and which images are set."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """The theme in use, whether each person may pick their own, the product name, the themes, the images set"""
        out = _run(B.state)
        out["may_change"] = g.user.can("settings.manage")
        return out


@blp.route("/branding/<any(logo, favicon):key>")
class BrandingImage(MethodView):
    """/api/v1/branding/{logo|favicon}: GET the image (404 when none is set)."""
    @blp.doc(security=SECURITY)
    @require_auth()
    def get(self, key):
        """The image (404 when none is set)"""
        data, ct = _run(lambda c: B.get_file(c, key))
        return Response(data, mimetype=ct, headers={"Cache-Control": "private, max-age=300", **SAFE})


@blp.route("/branding/themes/<string:slug>.css")
class ThemeCss(MethodView):
    """/api/v1/branding/themes/{slug}.css: GET a theme's CSS, to use it or to download it, change it and add it back."""
    @blp.doc(security=SECURITY)
    @require_auth()
    def get(self, slug):
        """A theme's CSS"""
        name, css = _run(lambda c: B.theme_css(c, slug))
        dl = request.args.get("download") in ("1", "true")
        headers = {"Cache-Control": "no-store", **SAFE}
        if dl:
            headers["Content-Disposition"] = f'attachment; filename="{slug}.css"'
        return Response(css, mimetype="text/css", headers=headers)


@blp.route("/admin/branding")
class BrandingAdmin(MethodView):
    """/api/v1/admin/branding: PUT {theme, personal, product_name}: the organisation's theme, whether each person may
    pick their own from those offered, and the name in the top bar (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def put(self, data):
        """The organisation's theme, whether each person may pick their own, and the name in the top bar"""
        return _run(lambda c: B.set_choice(c, data or {}, g.user.username), write=True, action="branding.set",
                    details=lambda out: out)


@blp.route("/admin/branding/<any(logo, favicon):key>")
class BrandingImageAdmin(MethodView):
    """/api/v1/admin/branding/{logo|favicon}: POST the image (multipart "file", or the body): PNG, JPEG, WebP or SVG;
    DELETE removes it (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self, key):
        """The image: PNG, JPEG, WebP or SVG"""
        f = request.files.get("file")
        limit = B.FILES[key] + 1
        raw = f.read(limit) if f else request.get_data(cache=False)[:limit]
        return _run(lambda c: B.set_file(c, key, raw, g.user.username), write=True, action=f"branding.{key}.set",
                    details=lambda out: out)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def delete(self, key):
        """Removes it"""
        return _run(lambda c: B.delete_file(c, key), write=True, action=f"branding.{key}.remove", details={"key": key})


@blp.route("/admin/branding/themes")
class ThemesAdmin(MethodView):
    """/api/v1/admin/branding/themes: POST {name, css[, slug]}: add a theme, or replace one added before (by its
    slug); its CSS may hold only looks (Super Admins). A multipart file "file" with a field "name" works too."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self):
        """Add a theme, or replace one added before"""
        f = request.files.get("file")
        if f:
            data = {"name": request.form.get("name"), "slug": request.form.get("slug"), "css": f.read(B.MAX_CSS + 1)}
        else:
            data = request.get_json(silent=True) or {}
        return _run(lambda c: B.save_theme(c, data.get("name"), data.get("css"), g.user.username, data.get("slug") or None),
                    write=True, action="branding.theme.save", details=lambda out: out)


@blp.route("/admin/branding/themes/<string:slug>")
class ThemeAdmin(MethodView):
    """/api/v1/admin/branding/themes/{slug}: DELETE an added theme; when it was the organisation's, the standard look
    is used again (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def delete(self, slug):
        """Remove an added theme"""
        return _run(lambda c: B.delete_theme(c, slug, g.user.username), write=True, action="branding.theme.remove",
                    details={"slug": slug})


@blp.route("/branding/fonts/<string:slug>")
class FontFile(MethodView):
    """/api/v1/branding/fonts/{slug}: GET an uploaded font's file; the screens load it so the themes can name it (D736)."""
    @blp.doc(security=SECURITY)
    @require_auth()
    def get(self, slug):
        """An uploaded font's file"""
        data, ct = _run(lambda c: B.get_font(c, slug))
        return Response(data, mimetype=ct, headers={"Cache-Control": "private, max-age=86400", **SAFE})


@blp.route("/admin/branding/fonts")
class FontsAdmin(MethodView):
    """/api/v1/admin/branding/fonts: POST a font file (multipart "file", with family, weight normal | bold and style
    normal | italic): WOFF2, WOFF, TrueType or OpenType, up to 2 MB; the themes then name its family (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def post(self):
        """A font file for the themes"""
        f = request.files.get("file")
        raw = f.read(B.MAX_FONT + 1) if f else b""
        form = request.form
        return _run(lambda c: B.set_font(c, form.get("family", ""), raw, g.user.username, form.get("weight", "normal"),
                                          form.get("style", "normal")), write=True, action="branding.font.set", details=lambda out: out)


@blp.route("/admin/branding/fonts/<string:slug>")
class FontAdmin(MethodView):
    """/api/v1/admin/branding/fonts/{slug}: DELETE an uploaded font; a theme naming it falls back to its next font."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def delete(self, slug):
        """Remove an uploaded font"""
        return _run(lambda c: B.delete_font(c, slug), write=True, action="branding.font.remove", details={"slug": slug})


# ---------------------------------------------------------------- each person's own look (R9.5, D827)
@blp.route("/branding/my-look")
class MyLook(MethodView):
    """/api/v1/branding/my-look: PUT {theme}: my own theme, one the Super Admins offer or one of my own; null or empty
    for the organisation's. A theme that is not mine to pick is refused."""
    @blp.doc(security=SECURITY)
    @blp.arguments(FreeIn)
    @blp.response(200, Free)
    @require_auth()
    def put(self, data):
        """My own theme, one offered or one of my own (null: the organisation's)"""
        return _run(lambda c: B.set_look(c, g.user.username, (data or {}).get("theme") or None), write=True)


@blp.route("/branding/my-themes")
class MyThemes(MethodView):
    """/api/v1/branding/my-themes: GET my own themes and whether I may make them; POST {name, css} (or a multipart file
    "file" with "name") keeps one, checked as an uploaded theme is (R9.5)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def get(self):
        """My own themes, and whether I may make them"""
        def read(c):
            choice = B.get_choice(c)
            return {"own": bool(choice.get("personal") and choice.get("own")), "themes": B.own_themes(c, g.user.username),
                    "max": B.OWN_MAX, "max_kb": B.OWN_MAX_CSS // 1024}
        return _run(read)

    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def post(self):
        """Keep one of my own themes (made in the designer or uploaded)"""
        f = request.files.get("file")
        if f:
            data = {"name": request.form.get("name"), "css": f.read(B.OWN_MAX_CSS + 1)}
        else:
            data = request.get_json(silent=True) or {}
        return _run(lambda c: B.save_own(c, g.user.username, data.get("name"), data.get("css")), write=True)


@blp.route("/branding/my-themes/<string:slug>")
class MyTheme(MethodView):
    """/api/v1/branding/my-themes/{slug}: DELETE one of my own themes (when I used it, the organisation's again)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth()
    def delete(self, slug):
        """Remove one of my own themes"""
        return _run(lambda c: B.delete_own(c, g.user.username, slug), write=True)


@blp.route("/branding/my-themes/<string:slug>.css")
class MyThemeCss(MethodView):
    """/api/v1/branding/my-themes/{slug}.css: GET one of my own themes' CSS, checked again as it is read; ?download=1
    to save it, to share or upload elsewhere."""
    @blp.doc(security=SECURITY)
    @require_auth()
    def get(self, slug):
        """One of my own themes' CSS"""
        name, css = _run(lambda c: B.own_css(c, g.user.username, slug))
        headers = {"Cache-Control": "no-store", **SAFE}
        if request.args.get("download") in ("1", "true"):
            headers["Content-Disposition"] = f'attachment; filename="{slug}.css"'
        return Response(css, mimetype="text/css", headers=headers)


@blp.route("/admin/branding/own-themes")
class OwnThemesAdmin(MethodView):
    """/api/v1/admin/branding/own-themes: GET who keeps themes of their own, each theme's name and size (Super Admins)."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def get(self):
        """Who keeps themes of their own"""
        return {"themes": _run(B.own_in_use)}


@blp.route("/admin/branding/own-themes/<string:username>/<string:slug>")
class OwnThemeAdmin(MethodView):
    """/api/v1/admin/branding/own-themes/{username}/{slug}: DELETE a person's own theme that causes trouble (Super
    Admins); when they used it, they are on the organisation's again."""
    @blp.doc(security=SECURITY)
    @blp.response(200, Free)
    @require_auth("settings.manage")
    def delete(self, username, slug):
        """Remove a person's own theme"""
        return _run(lambda c: B.remove_own_of(c, username.lower(), slug), write=True, action="branding.own_theme.remove",
                    details={"username": username.lower(), "slug": slug})
