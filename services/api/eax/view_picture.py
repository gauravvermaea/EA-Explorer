"""A view as a picture for the AI (R5.7-P1, D731; owner, 17 Nov 2026, 13:52: "In png and svg format, also give them raw
data if they want so they can build there own"): drawn by EA Explorer as on its screens, the ArchiMate boxes and
icons included (R5.7-V1), and the raw data behind the picture when asked.

  * a view (VP-<n> or an organisation's own, by code): its elements in the bands of their domains, laid out as the
    screen lays them out (services/web/src/EntityGraph.jsx, bandsLayout), with the relationships the view shows
  * a drawn view (draw.io, by name or id): its objects where they were drawn, with its lines
  * data: every object (type, notation, name, code, domain, position, size, colour), every relationship (type, verb,
    source, target, from and to points) and the bands; svg: the picture as SVG text; png: the picture as a PNG

The icons are the same drawings as the screens' (services/web/src/archimateIcons.jsx); tests/test_r5_7_view_picture.py
keeps the two the same. Nothing is stored: the picture is drawn each time from the model as it is now.
"""

from __future__ import annotations

import io
import math
import re
from typing import Any
from xml.sax.saxutils import escape

from . import repository as repo
from .metamodel_edit import EditError

H, MIN_W, MAX_W = 44, 110, 220                       # a box, as the screen draws it
BAND_LABEL, BAND_MAX, GAP = 150, 1500, 16
REL_COLOURS = {"Composition": "#1f5fb8", "Aggregation": "#5b8fd6", "Assignment": "#7a3db8", "Realization": "#1e7b3c",
               "Serving": "#c26a00", "Access": "#8a6d00", "Influence": "#b3261e", "Association": "#6b7785",
               "Triggering": "#00838f", "Flow": "#2e9e8f", "Specialization": "#4a4a4a"}
INK, QUIET = "#1d2733", "#5b6775"


# ---------------------------------------------------------------- the icons (the screens' archimateIcons.jsx, in Python)
def L(d, **extra):  # noqa: N802 - the same names as the screens' drawings
    """A path of an icon, in the screens' own words (archimateIcons.jsx)."""
    return ("path", {"d": d, **extra})


def C(cx, cy, r, dot=False):  # noqa: N802
    """A circle of an icon (a filled dot when dot is true)."""
    return ("circle", {"cx": cx, "cy": cy, "r": r, "dot": dot})


def R(x, y, w, h, rx=0):  # noqa: N802
    """A rectangle of an icon, its corners rounded by rx."""
    return ("rect", {"x": x, "y": y, "width": w, "height": h, "rx": rx})


def E(cx, cy, rx, ry):  # noqa: N802
    """An ellipse of an icon."""
    return ("ellipse", {"cx": cx, "cy": cy, "rx": rx, "ry": ry})


ROLE = [L("M4,4 H11 A3,4 0 0 1 11,12 H4"), E(4, 8, 2, 4)]
INTERFACE = [C(11, 8, 3.5), L("M1,8 H7.5")]
OBJECT = [R(2, 3, 12, 10), L("M2,6 H14")]
GLYPHS: dict[str, list] = {
    "BusinessActor": [C(8, 3.5, 2.5), L("M8,6 V11 M4,8 H12 M8,11 L5,15 M8,11 L11,15")],
    "Role": ROLE, "Stakeholder": ROLE,
    "Collaboration": [C(6, 8, 4), C(10, 8, 4)],
    "BusinessInterface": INTERFACE, "ApplicationInterface": INTERFACE, "TechnologyInterface": INTERFACE,
    "Process": [L("M1,6 H9 V3 L15,8 L9,13 V10 H1 Z")],
    "Function": [L("M3,15 V5 L8,1 L13,5 V15 L8,11 Z")],
    "Event": [L("M1,4 H11 A4,4 0 0 1 11,12 H1 L4,8 Z")],
    "Service": [R(1, 4, 14, 8, 4)],
    "BusinessObject": OBJECT, "DataObject": OBJECT,
    "Product": [R(2, 3, 12, 10), R(2, 3, 6, 3)],
    "ApplicationComponent": [R(4, 2, 10, 12), R(2, 4, 4, 2), R(2, 9, 4, 2)],
    "Node": [L("M2,5 L5,2 H14 V11 L11,14 H2 Z M2,5 H11 V14 M11,5 L14,2")],
    "Device": [R(2, 2, 12, 8, 1), L("M5,14 H11 M8,10 V14")],
    "SystemSoftware": [C(7, 9, 5), L("M5,4.5 A5,5 0 1 1 12.5,11.5")],
    "CommunicationNetwork": [L("M3,11 L7,4 L13,5 L9,12 Z"), C(3, 11, 1.5, True), C(7, 4, 1.5, True), C(13, 5, 1.5, True), C(9, 12, 1.5, True)],
    "DistributionNetwork": [L("M1,8 H15 M4,5 L1,8 L4,11 M12,5 L15,8 L12,11")],
    "Path": [L("M1,8 H15", dash="2 2"), L("M4,5 L1,8 L4,11 M12,5 L15,8 L12,11")],
    "Equipment": [C(6, 10, 3.5), C(11, 5, 2.5), L("M6,5.5 V6.5 M6,13.5 V14.5 M1.5,10 H2.5 M9.5,10 H10.5")],
    "Facility": [L("M1,15 V7 L5,10 V7 L9,10 V3 H12 V15 Z")],
    "Material": [L("M4,2 H12 L15,8 L12,14 H4 L1,8 Z")],
    "Artifact": [L("M3,1 H10 L13,4 V15 H3 Z M10,1 V4 H13")],
    "Resource": [R(1, 5, 12, 7, 2), R(13, 7, 2, 3), L("M4,7 V10 M7,7 V10 M10,7 V10")],
    "Capability": [L("M1,15 H15 V1 H11 V5 H6 V10 H1 Z M6,10 H11 V5 M6,15 V10 M11,15 V10 M11,10 H15")],
    "ValueStream": [L("M1,4 H12 L15,8 L12,12 H1 L4,8 Z")],
    "CourseOfAction": [C(10, 6, 4.5), C(10, 6, 1.5, True), L("M1,15 L7.5,8.5 M1,11 V15 H5")],
    "Driver": [C(8, 8, 5.5), C(8, 8, 1.5, True), L("M8,1 V15 M1,8 H15 M3,3 L13,13 M13,3 L3,13")],
    "Assessment": [C(6.5, 6.5, 4.5), L("M10,10 L15,15")],
    "Goal": [C(8, 8, 6.5), C(8, 8, 3.5), C(8, 8, 1, True)],
    "Outcome": [C(7, 9, 5.5), C(7, 9, 2.8), C(7, 9, 0.9, True), L("M7,9 L15,1 M11,1 H15 V5")],
    "Principle": [R(3, 1, 10, 14, 1), L("M8,4 V10"), C(8, 12.5, 0.9, True)],
    "Requirement": [L("M4,4 H15 L12,12 H1 Z")],
    "Meaning": [L("M4,12 A3,3 0 0 1 4,6 A4,4 0 0 1 11,5 A3,3 0 0 1 12,12 Z")],
    "Value": [E(8, 8, 7, 4)],
    "WorkPackage": [L("M13,8 A5,5 0 1 1 8,3"), L("M6,1 L8.5,3 L6,5")],
    "Deliverable": [L("M2,2 H14 V12 C11,10 6,15 2,12 Z")],
    "Plateau": [L("M5,4 H15 M3,8 H13 M1,12 H11", width=2)],
    "Location": [L("M8,15 C3,9 3,2 8,2 C13,2 13,9 8,15 Z"), C(8, 6.5, 1.8)],
    "Grouping": [],
    "Junction": [C(8, 8, 4, True)],
}
ROUNDED = {"Service", "Process", "Function", "Event", "Capability", "ValueStream", "CourseOfAction", "WorkPackage"}
CUT = {"Stakeholder", "Driver", "Assessment", "Goal", "Outcome", "Principle", "Requirement", "Meaning", "Value"}


def corners(notation: str | None) -> str:
    """A path of an icon, in the screens' own words (archimateIcons.jsx)."""
    if not notation or notation not in GLYPHS:
        return "plain"
    return "rounded" if notation in ROUNDED else "cut" if notation in CUT else "square"


# ---------------------------------------------------------------- text widths
_FONTS: dict[tuple[int, bool], Any] = {}


def _font(size: int, bold: bool = False):
    key = (size, bold)
    if key not in _FONTS:
        try:
            from PIL import ImageFont
            _FONTS[key] = ImageFont.load_default(size=size)
        except Exception:  # noqa: BLE001 - no Pillow: widths are estimated
            _FONTS[key] = None
    return _FONTS[key]


def text_width(s: str, size: int = 12, bold: bool = False) -> float:
    """How wide a text is in pixels at that size, measured with the font, else estimated."""
    f = _font(size, bold)
    if f is not None:
        try:
            return f.getlength(s) * (1.06 if bold else 1.0)
        except Exception:  # noqa: BLE001
            pass
    return len(s) * size * (0.58 if bold else 0.54)


def box_width(o: dict) -> int:
    """A box's width as the screen works it out from its name and its type line."""
    sub = f"{o['type']} · {o.get('display_id') or ''}"
    return int(max(MIN_W, min(MAX_W, math.ceil(max(text_width(o["name"], 12, True), text_width(sub, 10))) + 24)))


def shorten(s: str, width: float) -> str:
    """The name cut short with an ellipsis so it fits the width."""
    if text_width(s, 12, True) <= width:
        return s
    while len(s) > 3 and text_width(s + "…", 12, True) > width:
        s = s[:-1]
    return s + "…"


# ---------------------------------------------------------------- the data behind the picture
def bands_layout(objects: list[dict]) -> tuple[list[dict], int, int]:
    """Every element in the band of its domain, grouped by type, long bands wrapped: the screen's bandsLayout."""
    groups: list[dict] = []
    for o in sorted(objects, key=lambda o: (o.get("domain_order") or 0, o["type"], o["name"])):
        if not groups or groups[-1]["domain"] != o["domain"]:
            groups.append({"domain": o["domain"], "colour": o.get("colour"), "items": []})
        groups[-1]["items"].append(o)
    bands, y = [], 0
    for g in groups:
        x, row_y, last = BAND_LABEL, y + GAP, None
        for o in g["items"]:
            w = box_width(o)
            if last and last != o["type"]:
                x += 12
            if x + w > BAND_LABEL + BAND_MAX:
                x, row_y = BAND_LABEL, row_y + H + 14
            o.update(x=x, y=row_y, width=w, height=H)
            x += w + GAP
            last = o["type"]
        h = row_y + H + GAP - y
        bands.append({"label": g["domain"], "colour": g["colour"], "y": y, "height": h})
        y += h + 10
    width = max([o["x"] + o["width"] for o in objects] or [1]) + (GAP if bands else 0)
    for b in bands:
        b["width"] = width
    return bands, width, max([b["y"] + b["height"] for b in bands] or [1])


def ends(s: dict, t: dict, offset: float = 0) -> tuple[tuple[float, float], tuple[float, float]]:
    """Where a straight line between two boxes leaves the one and meets the other (the screen's straightSection)."""
    sc = (s["x"] + s["width"] / 2, s["y"] + s["height"] / 2)
    tc = (t["x"] + t["width"] / 2, t["y"] + t["height"] / 2)
    dx, dy = tc[0] - sc[0], tc[1] - sc[1]
    n = math.hypot(dx, dy) or 1
    dx, dy = dx / n, dy / n

    def border(c, b, ux, uy):
        k = min(b["width"] / 2 / max(abs(ux), 1e-6), b["height"] / 2 / max(abs(uy), 1e-6))
        return (round(c[0] + ux * k - dy * offset, 1), round(c[1] + uy * k + dx * offset, 1))
    return border(sc, s, dx, dy), border(tc, t, -dx, -dy)


def _lines(objects: list[dict], rels: list[dict]) -> list[dict]:
    by = {o["id"]: o for o in objects}
    pairs = {(r["source"], r["target"]) for r in rels}
    out = []
    for r in rels:
        s, t = by.get(r["source"]), by.get(r["target"])
        if not s or not t or s is t:
            continue
        a, b = ends(s, t, 5 if (r["target"], r["source"]) in pairs else 0)
        out.append({**r, "from": a, "to": b})
    return out


def from_view(conn, model: Any, code: str) -> dict:
    """A view (VP-<n> or the organisation's own) of a model, laid out in bands as on the screen."""
    from . import views
    d = views.render(conn, model, views.get_view(conn, code))
    nota = {r["code"]: r["notation"] for r in repo._rows(conn, """SELECT t.code, t.notation FROM core.entity_types t
                                                                  JOIN core.models m ON m.id = t.model_id
                                                                 WHERE m.guid = CAST(:m AS uuid) AND NOT t.is_deleted""",
                                                          m=d["model"]["id"])}
    objects = [{"id": str(e["id"]), "display_id": e["display_id"], "name": e["name"], "type": e["entity_type"], "type_code": e["type_code"],
                "notation": nota.get(e["type_code"]) or None, "domain": e["domain"], "domain_order": e["domain_order"],
                "colour": "#" + (e["colour"] or "eeeeee")} for e in d["entities"]]
    bands, width, height = bands_layout(objects)
    rels = [{"id": str(r["id"]), "type": r["relationship_type_code"], "name": r["relationship_type"], "verb": r["verb"],
             "source": str(r["source"]), "target": str(r["target"])} for r in d["relationships"]]
    v = d["view"]
    return {"title": f"{v['code']} {v['name']}", "kind": "view", "model": d["model"], "view": {"code": v["code"], "name": v["name"],
            "purpose": v.get("purpose") or ""}, "width": width, "height": height, "bands": bands,
            "objects": [{k: o[k] for k in ("id", "display_id", "name", "type", "notation", "domain", "colour", "x", "y", "width", "height")}
                        for o in objects], "relationships": _lines(objects, rels)}


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def from_drawn(conn, model: Any, view: str) -> dict:
    """A drawn view (draw.io), its objects where they were drawn and its lines, with the model as it is now."""
    from defusedxml import ElementTree as SafeET

    from . import drawn_views as dv
    from . import views_client as vc
    m = repo.get_model(conn, model)
    got = vc.get_view(m["id"], view, None, with_xml=True, marker=dv.marker(conn, m["_id"]))
    root = SafeET.fromstring(got["xml"])
    ents = {r["id"]: r for r in repo._rows(conn, """
        SELECT e.guid::text AS id, e.display_id, e.name, t.name AS type, t.notation, l.name AS domain, l.colour
          FROM core.entities e JOIN core.entity_types t ON t.id = e.entity_type_id JOIN core.domains l ON l.id = t.domain_id
         WHERE e.model_id = :m AND NOT e.is_deleted""", m=m["_id"])}
    objects, cells, edges = [], {}, []
    for gm in dv._graph_models(root):
        r = gm.find("root")
        if r is None:
            continue
        for el in list(r):
            attrs = dict(el.attrib)
            cell = el.find("mxCell") if el.tag in ("object", "UserObject") else el
            if cell is None:
                continue
            ca = dict(cell.attrib)
            cid = attrs.get("id") or ca.get("id")
            geo = cell.find("mxGeometry")
            if ca.get("vertex") == "1" and geo is not None and ca.get("parent", "1") == "1":
                e = ents.get(attrs.get("ea_id") or "")
                label = re.sub(r"<[^>]+>", " ", attrs.get("label") or ca.get("value") or "").strip()
                o = {"id": e["id"] if e else cid, "display_id": e["display_id"] if e else "", "name": e["name"] if e else label,
                     "type": e["type"] if e else (attrs.get("ea_type") or ""), "notation": (e or {}).get("notation") or None,
                     "domain": e["domain"] if e else "", "colour": "#" + ((e or {}).get("colour") or "eeeeee"),
                     "x": _num(geo.get("x")), "y": _num(geo.get("y")), "width": _num(geo.get("width"), 120), "height": _num(geo.get("height"), H),
                     "placeholder": not e}
                if not o["name"] and not e:
                    continue
                cells[cid] = o
                objects.append(o)
            elif ca.get("edge") == "1":
                edges.append({"id": attrs.get("ea_rel_id") or cid, "type": attrs.get("ea_rel") or "Association",
                              "source": ca.get("source"), "target": ca.get("target")})
    if objects:                                              # start at (0, 0), with a margin
        mx, my = min(o["x"] for o in objects) - 20, min(o["y"] for o in objects) - 20
        for o in objects:
            o["x"], o["y"] = o["x"] - mx, o["y"] - my
    rels = []
    for ed in edges:
        s, t = cells.get(ed["source"]), cells.get(ed["target"])
        if s and t:
            rels.append({"id": ed["id"], "type": ed["type"], "name": ed["type"], "verb": "", "source": s["id"], "target": t["id"]})
    width = max([o["x"] + o["width"] for o in objects] or [1]) + 20
    height = max([o["y"] + o["height"] for o in objects] or [1]) + 20
    return {"title": got.get("name") or view, "kind": "drawn view", "model": {"id": str(m["id"]), "name": m["name"]},
            "view": {"name": got.get("name") or view, "version": got.get("version")}, "width": width, "height": height,
            "bands": [], "objects": objects, "relationships": _lines(objects, rels)}


def view_data(conn, model: Any, view: str) -> dict:
    """The data behind the picture: a view by its code (VP-11), else a drawn view by its name or id."""
    from . import views
    try:
        views.get_view(conn, view)
        return from_view(conn, model, view)
    except EditError as exc:
        if getattr(exc, "status", 400) != 404:
            raise
    try:
        return from_drawn(conn, model, view)
    except EditError:
        raise
    except Exception as exc:  # noqa: BLE001 - not a view, nor a drawn view that could be read
        raise EditError(f"No view or drawn view {view!r} in this model (list_views and list_drawn_views show them): {exc}", 404) from exc


# ---------------------------------------------------------------- SVG
def _glyph_svg(notation: str | None, x: float, y: float, size: float = 14) -> str:
    parts = GLYPHS.get(notation or "") or []
    if not parts:
        return ""
    out = []
    for tag, a in parts:
        if tag == "path":
            extra = (f' stroke-dasharray="{a["dash"]}"' if a.get("dash") else "") + (f' stroke-width="{a["width"]}"' if a.get("width") else "")
            out.append(f'<path d="{a["d"]}"{extra}/>')
        elif tag == "circle":
            fill = f' fill="{INK}" stroke="none"' if a["dot"] else ""
            out.append(f'<circle cx="{a["cx"]}" cy="{a["cy"]}" r="{a["r"]}"{fill}/>')
        elif tag == "rect":
            out.append(f'<rect x="{a["x"]}" y="{a["y"]}" width="{a["width"]}" height="{a["height"]}" rx="{a["rx"]}"/>')
        elif tag == "ellipse":
            out.append(f'<ellipse cx="{a["cx"]}" cy="{a["cy"]}" rx="{a["rx"]}" ry="{a["ry"]}"/>')
    return (f'<g transform="translate({x},{y}) scale({size / 16})" fill="none" stroke="{INK}" stroke-width="1.2" '
            f'stroke-linejoin="round" stroke-linecap="round">' + "".join(out) + "</g>")


def _box_svg(o: dict) -> str:
    kind, w, h = corners(o.get("notation")), o["width"], o["height"]
    grouping = o.get("notation") == "Grouping"
    common = f'fill="{"none" if grouping else o["colour"]}" stroke="#8a96a3" stroke-width="1"' + (' stroke-dasharray="6 4"' if grouping else "")
    if kind == "cut":
        c = min(8, h / 4)
        return f'<path d="M{c},0 H{w - c} L{w},{c} V{h - c} L{w - c},{h} H{c} L0,{h - c} V{c} Z" {common}/>'
    rx = 10 if kind == "rounded" else 1 if kind == "square" else 6
    return f'<rect width="{w}" height="{h}" rx="{rx}" {common}/>'


def to_svg(d: dict) -> str:
    """The picture as SVG, as the screen draws it."""
    w, h = math.ceil(d["width"]), math.ceil(d["height"])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           'font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif">',
           f'<title>{escape(d["title"])}</title><rect width="{w}" height="{h}" fill="#ffffff"/>', "<defs>"]
    for code in sorted({r["type"] for r in d["relationships"]}):
        out.append(f'<marker id="a-{escape(code)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                   f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{REL_COLOURS.get(code, "#6b7785")}"/></marker>')
    out.append("</defs>")
    for b in d["bands"]:
        out.append(f'<rect x="0" y="{b["y"]}" width="{b["width"]}" height="{b["height"]}" rx="8" fill="#f6f7f9" stroke="#d9dee5" stroke-dasharray="4 3"/>'
                   f'<rect x="0" y="{b["y"]}" width="8" height="{b["height"]}" rx="3" fill="#{(b.get("colour") or "cccccc").lstrip("#")}"/>'
                   f'<text x="18" y="{b["y"] + 24}" font-size="14" font-weight="700" fill="{QUIET}">{escape(b["label"] or "")}</text>')
    for r in d["relationships"]:
        col = REL_COLOURS.get(r["type"], "#6b7785")
        (x1, y1), (x2, y2) = r["from"], r["to"]
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="1.4" marker-end="url(#a-{escape(r["type"])})">'
                   f'<title>{escape(r.get("name") or r["type"])}</title></line>')
    for o in d["objects"]:
        glyph = bool(GLYPHS.get(o.get("notation") or ""))
        out.append(f'<g transform="translate({o["x"]},{o["y"]})"><title>{escape(o["name"])} ({escape(o.get("display_id") or "")}, {escape(o["type"])})</title>'
                   + _box_svg(o) + _glyph_svg(o.get("notation"), o["width"] - 19, 5) +
                   f'<text x="10" y="18" font-size="12" font-weight="600" fill="{INK}">{escape(shorten(o["name"], o["width"] - (34 if glyph else 20)))}</text>'
                   f'<text x="10" y="34" font-size="10" fill="{QUIET}">{escape(o["type"])}{" · " + escape(o["display_id"]) if o.get("display_id") else ""}</text></g>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- PNG (Pillow)
def _flatten(d: str) -> list[list[tuple[float, float]]]:
    """An SVG path of absolute M, L, H, V, A, C and Z as polylines."""
    toks = re.findall(r"[MLHVACZ]|-?(?:\d+(?:\.\d+)?|\.\d+)", d)
    subs: list[list[tuple[float, float]]] = []
    cur, start, cmd, i = (0.0, 0.0), (0.0, 0.0), "", 0

    def nums(n):
        nonlocal i
        vals = [float(x) for x in toks[i:i + n]]
        i += n
        return vals
    while i < len(toks):
        if re.match(r"[A-Z]", toks[i]):
            cmd = toks[i]
            i += 1
        if cmd == "M":
            x, y = nums(2)
            cur = start = (x, y)
            subs.append([cur])
            cmd = "L"
        elif cmd == "L":
            x, y = nums(2)
            cur = (x, y)
            subs[-1].append(cur)
        elif cmd == "H":
            (x,) = nums(1)
            cur = (x, cur[1])
            subs[-1].append(cur)
        elif cmd == "V":
            (y,) = nums(1)
            cur = (cur[0], y)
            subs[-1].append(cur)
        elif cmd == "Z":
            subs[-1].append(start)
            cur = start
        elif cmd == "C":
            x1, y1, x2, y2, x, y = nums(6)
            p0 = cur
            for k in range(1, 13):
                t = k / 12
                subs[-1].append(((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3 * x,
                                 (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3 * y))
            cur = (x, y)
        elif cmd == "A":
            rx, ry, rot, large, sweep, x, y = nums(7)
            subs[-1].extend(_arc(cur, (x, y), rx, ry, rot, bool(large), bool(sweep)))
            cur = (x, y)
        else:
            i += 1
    return subs


def _arc(p1, p2, rx, ry, rot, large, sweep) -> list[tuple[float, float]]:
    """An SVG arc as points (the endpoint to centre conversion of the SVG specification)."""
    if rx == 0 or ry == 0 or p1 == p2:
        return [p2]
    phi = math.radians(rot)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (p1[0] - p2[0]) / 2, (p1[1] - p2[1]) / 2
    x1, y1 = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    cx, cy = cp * cx1 - sp * cy1 + (p1[0] + p2[0]) / 2, sp * cx1 + cp * cy1 + (p1[1] + p2[1]) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    out = []
    for k in range(1, 17):
        t = t1 + dt * k / 16
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return out


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 238, 238, 238


def _dashed(draw, a, b, fill, width, dash=(6, 4)):
    (x1, y1), (x2, y2) = a, b
    n = math.hypot(x2 - x1, y2 - y1) or 1
    ux, uy, t, on = (x2 - x1) / n, (y2 - y1) / n, 0.0, True
    while t < n:
        seg = dash[0] if on else dash[1]
        if on:
            draw.line([(x1 + ux * t, y1 + uy * t), (x1 + ux * min(n, t + seg), y1 + uy * min(n, t + seg))], fill=fill, width=width)
        t += seg
        on = not on


def to_png(d: dict, scale: float = 2.0) -> bytes:
    """The picture as a PNG, as the screen draws it, `scale` pixels to a screen pixel (1 to 3)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise EditError("Pictures as PNG need Pillow in the API (a clean rebuild installs it); ask for svg or data.", 503) from exc
    s = max(1.0, min(3.0, float(scale or 2)))
    w, h = math.ceil(d["width"] * s), math.ceil(d["height"] * s)
    if w * h > 40_000_000:
        s = math.sqrt(40_000_000 / (d["width"] * d["height"]))
        w, h = math.ceil(d["width"] * s), math.ceil(d["height"] * s)
    img = Image.new("RGB", (max(1, w), max(1, h)), "white")
    dr = ImageDraw.Draw(img)
    f12, f10, f14 = _font(round(12 * s), True), _font(round(10 * s)), _font(round(14 * s), True)
    for b in d["bands"]:
        box = [0, b["y"] * s, b["width"] * s, (b["y"] + b["height"]) * s]
        dr.rounded_rectangle(box, radius=8 * s, fill=(246, 247, 249), outline=(217, 222, 229), width=max(1, round(s)))
        dr.rounded_rectangle([0, b["y"] * s, 8 * s, (b["y"] + b["height"]) * s], radius=3 * s, fill=_rgb(b.get("colour") or "cccccc"))
        dr.text((18 * s, (b["y"] + 12) * s), b["label"] or "", fill=_rgb(QUIET), font=f14)
    for r in d["relationships"]:
        col = _rgb(REL_COLOURS.get(r["type"], "#6b7785"))
        (x1, y1), (x2, y2) = r["from"], r["to"]
        dr.line([(x1 * s, y1 * s), (x2 * s, y2 * s)], fill=col, width=max(1, round(1.4 * s)))
        ang = math.atan2(y2 - y1, x2 - x1)
        tip, size = (x2 * s, y2 * s), 7 * s
        dr.polygon([tip, (tip[0] - size * math.cos(ang - 0.45), tip[1] - size * math.sin(ang - 0.45)),
                    (tip[0] - size * math.cos(ang + 0.45), tip[1] - size * math.sin(ang + 0.45))], fill=col)
    for o in d["objects"]:
        x, y, bw, bh = o["x"] * s, o["y"] * s, o["width"] * s, o["height"] * s
        kind = corners(o.get("notation"))
        line = (138, 150, 163)
        if o.get("notation") == "Grouping":
            for a, b in (((x, y), (x + bw, y)), ((x + bw, y), (x + bw, y + bh)), ((x + bw, y + bh), (x, y + bh)), ((x, y + bh), (x, y))):
                _dashed(dr, a, b, line, max(1, round(s)), (6 * s, 4 * s))
        elif kind == "cut":
            c = min(8, o["height"] / 4) * s
            dr.polygon([(x + c, y), (x + bw - c, y), (x + bw, y + c), (x + bw, y + bh - c), (x + bw - c, y + bh), (x + c, y + bh),
                        (x, y + bh - c), (x, y + c)], fill=_rgb(o["colour"]), outline=line, width=max(1, round(s)))
        else:
            rad = {"rounded": 10, "square": 1, "plain": 6}[kind] * s
            dr.rounded_rectangle([x, y, x + bw, y + bh], radius=rad, fill=_rgb(o["colour"]), outline=line, width=max(1, round(s)))
        _glyph_png(dr, o.get("notation"), x + bw - 19 * s, y + 5 * s, 14 * s)
        glyph = bool(GLYPHS.get(o.get("notation") or ""))
        dr.text((x + 10 * s, y + 6 * s), shorten(o["name"], o["width"] - (34 if glyph else 20)), fill=_rgb(INK), font=f12)
        sub = o["type"] + (f" · {o['display_id']}" if o.get("display_id") else "")
        dr.text((x + 10 * s, y + 24 * s), sub, fill=_rgb(QUIET), font=f10)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _glyph_png(dr, notation: str | None, x: float, y: float, size: float) -> None:
    k = size / 16
    ink, wd = _rgb(INK), max(1, round(1.2 * k))
    pt = lambda px, py: (x + px * k, y + py * k)  # noqa: E731
    for tag, a in GLYPHS.get(notation or "") or []:
        if tag == "path":
            for sub in _flatten(a["d"]):
                pts = [pt(*p) for p in sub]
                if len(pts) < 2:
                    continue
                if a.get("dash"):
                    for p1, p2 in zip(pts, pts[1:], strict=False):
                        _dashed(dr, p1, p2, ink, wd, (2 * k, 2 * k))
                else:
                    dr.line(pts, fill=ink, width=max(wd, round(a.get("width", 1.2) * k)), joint="curve")
        elif tag == "circle":
            cx, cy, r = a["cx"], a["cy"], a["r"]
            box = [*pt(cx - r, cy - r), *pt(cx + r, cy + r)]
            dr.ellipse(box, fill=ink if a["dot"] else None, outline=ink, width=0 if a["dot"] else wd)
        elif tag == "ellipse":
            box = [*pt(a["cx"] - a["rx"], a["cy"] - a["ry"]), *pt(a["cx"] + a["rx"], a["cy"] + a["ry"])]
            dr.ellipse(box, outline=ink, width=wd)
        elif tag == "rect":
            box = [*pt(a["x"], a["y"]), *pt(a["x"] + a["width"], a["y"] + a["height"])]
            if a["rx"]:
                dr.rounded_rectangle(box, radius=a["rx"] * k, outline=ink, width=wd)
            else:
                dr.rectangle(box, outline=ink, width=wd)
