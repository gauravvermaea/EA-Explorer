"""Settings and admin configuration, exported and imported (Release 6.7, D755; the owner, 17 Nov 2026, 22:06: "we need
another release for import and export of settings and admin configs"; built 18 Nov 2026, 11:55: "Please build 6.5.4 6.7").

One file carries every admin setting, in parts the admin chooses on export and on import:

  application   System settings: currency, time zone, date and number formats, the financial year
  system        System settings: upload sizes, keep-for times, the parts used, the site's purpose and the rest
  security      Security settings: multi-factor sign-in, session time-outs
  branding      the theme chosen, the added themes, the fonts, the logo and the browser tab's icon, the product name
  alerts        the alert checks' levels and the custom checks
  retention     the keep-for rules
  audiences     the report audiences and which reports each sees
  webhooks      the webhooks' names, addresses and kinds (never their signing secrets: a new one is made here)
  pairings      the settings of the site pairings already here (never their keys; a pairing is made on its own screen)
  banner        the banner under the top bar
  allow_lists   the IP allow lists (never one that locks out the person importing)
  schedules     the Command centre's schedules (never one that deletes everything: that is made on the Command centre)

Never content (models, projects: those have their packages), never people, never a password, key or certificate.

Import: first a preview of every difference, by part (the value here and in the file); the admin ticks what to take;
a safety copy of the current settings is kept first (undo puts it back), and every change is in the audit trail. Nothing
here is ever removed by an import: what is only here is shown, and kept. A file from a newer release is refused; one
from an older release is brought up to date (UPGRADES).

Used by the API (System Admin > Settings import and export), by `eax settings export|import` (python -m
eax.settings_transfer, in the api container) and by the Jenkins pipelines of those commands; git is one more place for
the file (eax/gitpackages.py).
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets as _random
import sys
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from . import __version__

FORMAT = "eax-settings/1"
SECRET_WORDS = re.compile(r"(password|secret|token|private|key_enc|key_hash|credential)", re.I)

# part: (title, what it carries)
PARTS: dict[str, tuple[str, str]] = {
    "application": ("Application settings", "currency, time zone, date and number formats, week and financial year"),
    "system": ("System settings", "upload sizes, keep-for times, the parts used, the site's purpose and the rest"),
    "security": ("Security settings", "multi-factor sign-in and session time-outs"),
    "branding": ("Branding", "the theme chosen, added themes, fonts, the logo and the browser tab's icon"),
    "alerts": ("Alerts", "the alert checks' levels and the custom checks"),
    "retention": ("Keep-for rules", "how long each kind of record is kept"),
    "audiences": ("Report audiences", "the audiences and which reports each sees"),
    "webhooks": ("Webhooks", "names, addresses and kinds; never their signing secrets"),
    "pairings": ("Site pairings' settings", "how the pairings already here send and commit; never their keys"),
    "banner": ("Banner", "the message under the top bar"),
    "allow_lists": ("IP allow lists", "who may reach the site, the sign-in pages, System Admin, MCP and machines"),
    "schedules": ("Command centre schedules", "the eax commands run on a schedule"),
}
OPS_PARTS = ("banner", "allow_lists", "schedules")


class TransferError(Exception):
    """A file or a choice refused, in words."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- the operations helper (banner, allow lists, schedules)
def ops_call(method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
    """The operations helper's answer (the api container's address and token); raises on any failure."""
    url, token = os.environ.get("EAX_OPS_URL", "http://ops:8090"), os.environ.get("EAX_OPS_TOKEN", "")
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    req = urllib.request.Request(f"{url}{path}", method=method, data=data,
                                 headers={"X-Ops-Token": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            msg = json.load(exc).get("message")
        except Exception:  # noqa: BLE001
            msg = exc.reason
        raise TransferError(f"The operations helper refused: {msg}", 502) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TransferError(f"The operations helper is not reachable ({exc}): is the ops container running?", 503) from exc


# ---------------------------------------------------------------- reading each part: {item key: value}
def _b64(data) -> str:
    return base64.b64encode(bytes(data)).decode("ascii")


def _registry_part(conn, group: str) -> dict:
    from . import settings
    v = settings.values(conn)
    return {f"setting:{k}": v[k] for k, spec in settings.REGISTRY.items() if spec[0] == group}


def _branding(conn) -> dict:
    from . import branding
    out: dict[str, Any] = {"choice": branding.get_choice(conn)}
    for r in conn.execute(text("SELECT slug, name, css FROM core.branding_themes ORDER BY slug")).mappings():
        out[f"theme:{r['slug']}"] = {"name": r["name"], "css": r["css"]}
    for r in conn.execute(text("SELECT slug, family, weight, style, data FROM core.branding_fonts ORDER BY slug")).mappings():
        out[f"font:{r['slug']}"] = {"family": r["family"], "weight": r["weight"], "style": r["style"], "data": _b64(r["data"])}
    for r in conn.execute(text("SELECT key, data FROM core.branding_files ORDER BY key")).mappings():
        out[f"file:{r['key']}"] = {"data": _b64(r["data"])}
    return out


def _alerts(conn) -> dict:
    out: dict[str, Any] = {}
    for r in conn.execute(text("SELECT key, warning, critical, enabled, hold FROM core.alert_config ORDER BY key")).mappings():
        out[f"check:{r['key']}"] = {"warning": r["warning"], "critical": r["critical"], "enabled": r["enabled"], "hold": r["hold"]}
    for r in conn.execute(text("""SELECT key, name, kind, target, warning, critical, enabled, hold FROM core.alert_custom
                                  ORDER BY key""")).mappings():
        out[f"custom:{r['key']}"] = {k: r[k] for k in ("name", "kind", "target", "warning", "critical", "enabled", "hold")}
    return out


def _retention(conn) -> dict:
    return {f"rule:{r['code']}": {"action": r["action"], "after_days": r["after_days"]}
            for r in conn.execute(text("SELECT code, action, after_days FROM core.retention_rules ORDER BY code")).mappings()}


def _audiences(conn) -> dict:
    links: dict[str, list[str]] = {}
    for r in conn.execute(text("SELECT audience_code, report_code FROM core.report_audience_links ORDER BY 1, 2")):
        links.setdefault(r[0], []).append(r[1])
    return {f"audience:{r['code']}": {"name": r["name"], "group": r["audience_group"], "sort_order": r["sort_order"],
                                      "reports": links.get(r["code"], [])}
            for r in conn.execute(text("SELECT code, name, audience_group, sort_order FROM core.report_audiences ORDER BY code")).mappings()}


def _webhooks(conn) -> dict:
    return {f"webhook:{r['name']}": {"url": r["url"], "kinds": sorted(r["kinds"] or []), "enabled": r["enabled"]}
            for r in conn.execute(text("SELECT name, url, kinds, enabled FROM core.webhooks ORDER BY name")).mappings()}


PAIRING_FIELDS = ("commit_mode", "send_mode", "every_minutes", "scope", "note")


def _pairings(conn) -> dict:
    return {f"pairing:{r['side']}:{r['name']}": {k: r[k] for k in PAIRING_FIELDS}
            for r in conn.execute(text(f"SELECT side, name, {', '.join(PAIRING_FIELDS)} FROM core.site_pairings "
                                       "ORDER BY side, name")).mappings()}


BANNER_FIELDS = ("text", "link", "link_text", "level", "audience", "dismissible", "starts", "ends")


def _banner(ops: Callable) -> dict:
    b = (ops("GET", "/banner/all") or {}).get("banner")
    return {"banner": {k: b.get(k) for k in BANNER_FIELDS} if isinstance(b, dict) and b.get("text") else None}


def _allow_lists(ops: Callable) -> dict:
    cur = ops("GET", "/allow") or {}
    out = {f"place:{p}": sorted(({"address": e.get("address"), "name": e.get("name") or "", "why": e.get("why") or ""}
                                 for e in entries or []), key=lambda e: e["address"])
           for p, entries in (cur.get("lists") or {}).items()}
    out["trusted"] = sorted(({"address": e.get("address"), "name": e.get("name") or ""} for e in cur.get("trusted") or []),
                            key=lambda e: e["address"])
    return out


SCHEDULE_FIELDS = ("argv", "cron", "enabled", "backup_first", "keep", "banner")


def _schedules(ops: Callable) -> dict:
    out = {}
    for s in (ops("GET", "/commands/schedules") or {}).get("schedules") or []:
        if s.get("wipe") or s.get("once_at"):
            continue                    # deletes everything, or ran once: made on the Command centre, never carried
        out[f"schedule:{s.get('name')}"] = {k: s[k] for k in SCHEDULE_FIELDS if k in s and s[k] is not None}
    return out


READERS: dict[str, Callable] = {
    "application": lambda c, o: _registry_part(c, "application"), "system": lambda c, o: _registry_part(c, "system"),
    "security": lambda c, o: _registry_part(c, "security"), "branding": lambda c, o: _branding(c),
    "alerts": lambda c, o: _alerts(c), "retention": lambda c, o: _retention(c), "audiences": lambda c, o: _audiences(c),
    "webhooks": lambda c, o: _webhooks(c), "pairings": lambda c, o: _pairings(c), "banner": lambda c, o: _banner(o),
    "allow_lists": lambda c, o: _allow_lists(o), "schedules": lambda c, o: _schedules(o),
}


def chosen(parts) -> list[str]:
    """The parts asked for (all when none), refused when one is unknown."""
    if isinstance(parts, str):
        parts = [p for p in re.split(r"[,\s]+", parts) if p]
    parts = list(parts or PARTS)
    bad = [p for p in parts if p not in PARTS]
    if bad:
        raise TransferError(f"No part called {', '.join(bad)}: choose from {', '.join(PARTS)}.")
    return [p for p in PARTS if p in parts]


def read_parts(conn, parts, ops: Callable = ops_call) -> tuple[dict, dict]:
    """({part: items}, {part: why it could not be read}) for the parts asked for."""
    out, missing = {}, {}
    for p in chosen(parts):
        try:
            out[p] = READERS[p](conn, ops)
        except TransferError as exc:
            missing[p] = str(exc)
    return out, missing


def no_secrets(parts: dict) -> None:
    """Refused when any item carries a field named like a secret (a guard: the readers never read one)."""
    for p, items in parts.items():
        for key, v in items.items():
            for field in (v or {}) if isinstance(v, dict) else ():
                if SECRET_WORDS.search(field):
                    raise TransferError(f"{p} {key}: {field} would be a secret; nothing exported.", 500)


def export(conn, parts=None, by: str = "?", site: str = "", ops: Callable = ops_call) -> dict:
    """The settings file: format, release, when, by whom, from which site, the parts and their items."""
    got, missing = read_parts(conn, parts, ops)
    no_secrets(got)
    return {"format": FORMAT, "release": __version__, "made_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "made_by": by, "site": site, "parts": got, "not_read": missing}


# ---------------------------------------------------------------- the file checked, older ones brought up to date
def _release(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:3]) or (0,)


UPGRADES: list[tuple[tuple[int, ...], Callable[[dict], dict]]] = []   # (made before this release, how to bring it up)


def load(raw) -> dict:
    """The file read and checked: refused when it is not a settings file or comes from a newer release; one from an older
    release brought up to date."""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8-sig", errors="replace")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError as exc:
            raise TransferError("This is not an EA Explorer settings file (it is not JSON).") from exc
    if not isinstance(raw, dict) or raw.get("format") != FORMAT or not isinstance(raw.get("parts"), dict):
        raise TransferError("This is not an EA Explorer settings file (made by Export settings or eax settings export).")
    if _release(raw.get("release")) > _release(__version__):
        raise TransferError(f"This file comes from release {raw.get('release')}, newer than this one ({__version__}): "
                            "update this installation first.", 409)
    for before, up in UPGRADES:
        if _release(raw.get("release")) < before:
            raw = up(raw)
    raw["parts"] = {p: items for p, items in raw["parts"].items() if p in PARTS and isinstance(items, dict)}
    no_secrets(raw["parts"])
    return raw


# ---------------------------------------------------------------- the preview
def _norm(v):
    return json.loads(json.dumps(v, sort_keys=True, default=str))


def _shown(v):
    """A value as the preview shows it: file contents by their size, not their bytes."""
    if isinstance(v, dict) and "data" in v:
        return {**{k: x for k, x in v.items() if k != "data"}, "data": f"{len(base64.b64decode(v['data'] or '')) // 1024} KB file"}
    if isinstance(v, dict) and "css" in v:
        return {**{k: x for k, x in v.items() if k != "css"}, "css": f"{len(v['css'] or '')} characters of CSS"}
    return v


def maintenance_of(part: str, key: str, value) -> str:
    """When taking this item would put the maintenance page up later (a schedule turned on that does): what it says."""
    if part != "schedules" or not isinstance(value, dict) or not value.get("enabled"):
        return ""
    try:
        from .api.maintenance_gate import argv_says
    except Exception:  # noqa: BLE001 - outside the API (the command line is not asked)
        return ""
    said = argv_says(value.get("argv") or [])
    return said[0] if said else ""


def cannot_take(part: str, key: str, here, there) -> str:
    """Why a difference cannot be taken (shown, never taken), or ''."""
    if part == "pairings" and here is None:
        return "There is no such pairing here: pair the sites on Site pairings first."
    return ""


def diff(here: dict, file: dict) -> dict:
    """Every difference, by part: {part: [{key, change: changed|new, here, file, cannot, maintenance}], ...} with
    `only_here` (kept, never removed) and `same` counts."""
    out: dict[str, Any] = {}
    for part, items in file.items():
        mine = here.get(part, {})
        rows = []
        for key in sorted(items):
            a, b = mine.get(key), items[key]
            if key in mine and _norm(a) == _norm(b):
                continue
            rows.append({"key": key, "change": "changed" if key in mine else "new", "here": _shown(a), "file": _shown(b),
                         "cannot": cannot_take(part, key, a if key in mine else None, b),
                         "maintenance": maintenance_of(part, key, b)})
        out[part] = {"title": PARTS[part][0], "differences": rows,
                     "only_here": sorted(k for k in mine if k not in items),
                     "same": sum(1 for k in items if k in mine and _norm(mine[k]) == _norm(items[k]))}
    return out


def preview(conn, raw, parts=None, ops: Callable = ops_call) -> dict:
    """What an import would change: the file's details and every difference, by part."""
    f = load(raw)
    want = [p for p in chosen(parts) if p in f["parts"]]
    here, missing = read_parts(conn, want, ops)
    return {"file": {k: f.get(k) for k in ("release", "made_at", "made_by", "site")}, "parts_in_file": list(f["parts"]),
            "differences": diff(here, {p: f["parts"][p] for p in want if p in here}), "not_read": missing}


# ---------------------------------------------------------------- taking the differences
class _Admin:
    def __init__(self, username: str):
        self.username, self.roles = username, ["super-admin"]


def _apply_registry(conn, items: dict, by: str) -> None:
    from . import settings
    settings.update(conn, _Admin(by), {k.split(":", 1)[1]: v for k, v in items.items()})


def _apply_branding(conn, items: dict, by: str) -> None:
    from . import branding
    for key, v in items.items():
        kind, _, name = key.partition(":")
        if kind == "theme":
            branding.save_theme(conn, v["name"], v["css"], by, slug=name)
        elif kind == "font":
            branding.set_font(conn, v["family"], base64.b64decode(v["data"]), by, v.get("weight", "normal"), v.get("style", "normal"))
        elif kind == "file":
            branding.set_file(conn, name, base64.b64decode(v["data"]), by)
    if "choice" in items:                       # last: a theme it names may have come in just now
        branding.set_choice(conn, items["choice"], by)


def _apply_alerts(conn, items: dict, by: str) -> None:
    from . import alerts
    for key, v in items.items():
        kind, _, name = key.partition(":")
        if kind == "custom":
            if not conn.execute(text("SELECT 1 FROM core.alert_custom WHERE key = :k"), {"k": name}).first():
                alerts.add_custom(conn, {**v, "key": name}, by)
            else:                               # what it checks, held to the same rules as a new one
                target = str(v.get("target") or "").strip()
                if v.get("kind") not in ("url", "sql"):
                    raise TransferError(f"Custom check {name}: its kind is url or sql.")
                if v.get("kind") == "url" and not target.startswith(("http://", "https://")):
                    raise TransferError(f"Custom check {name}: a url check needs an address starting with http:// or https://.")
                if v.get("kind") == "sql" and not re.match(r"(?is)^\s*select\b", target):
                    raise TransferError(f"Custom check {name}: a sql check is one SELECT that returns a number.")
                conn.execute(text("UPDATE core.alert_custom SET name = :n, kind = :t, target = :g WHERE key = :k"),
                             {"n": str(v.get("name") or name)[:120], "t": v["kind"], "g": target[:2000], "k": name})
            alerts.set_config(conn, f"custom:{name}", v)
        elif kind == "check":
            alerts.set_config(conn, name, v)


def _apply_retention(conn, items: dict, by: str) -> None:
    from . import operations
    for key, v in items.items():
        operations.set_rule(conn, by, key.split(":", 1)[1], v["action"], v["after_days"])


def _apply_audiences(conn, items: dict, by: str) -> None:
    for key, v in items.items():
        code = key.split(":", 1)[1]
        if not re.match(r"^[a-z][a-z0-9_]{1,40}$", code):
            raise TransferError(f"{code} is not an audience's code.")
        conn.execute(text("""INSERT INTO core.report_audiences (code, name, audience_group, sort_order) VALUES (:c, :n, :g, :o)
                             ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, audience_group = EXCLUDED.audience_group,
                                 sort_order = EXCLUDED.sort_order"""),
                     {"c": code, "n": str(v.get("name") or code)[:120], "g": str(v.get("group") or "")[:120],
                      "o": int(v.get("sort_order") or 1000)})
        conn.execute(text("DELETE FROM core.report_audience_links WHERE audience_code = :c"), {"c": code})
        for rep in v.get("reports") or []:
            conn.execute(text("INSERT INTO core.report_audience_links (report_code, audience_code) VALUES (:r, :c)"),
                         {"r": str(rep)[:120], "c": code})


def _apply_webhooks(conn, items: dict, by: str) -> list[str]:
    said = []
    for key, v in items.items():
        name = key.split(":", 1)[1]
        url = str(v.get("url") or "")
        if not re.match(r"^https?://", url, re.I):
            raise TransferError(f"Webhook {name}: its address must start with https:// or http://.")
        kinds = [str(k) for k in v.get("kinds") or []]
        n = conn.execute(text("""UPDATE core.webhooks SET url = :u, kinds = :k, enabled = :e, modified_at = now()
                                 WHERE name = :n"""), {"u": url, "k": kinds, "e": bool(v.get("enabled", True)), "n": name}).rowcount
        if not n:
            conn.execute(text("""INSERT INTO core.webhooks (name, url, secret, kinds, enabled, created_by)
                                 VALUES (:n, :u, :s, :k, :e, :b)"""),
                         {"n": name, "u": url, "s": _random.token_hex(32), "k": kinds, "e": bool(v.get("enabled", True)), "b": by})
            said.append(f"Webhook {name} was made with a new signing secret: give it to the receiving system "
                        "(System Admin > Webhooks).")
    return said


def _apply_pairings(conn, items: dict, by: str) -> None:
    for key, v in items.items():
        _, side, name = key.split(":", 2)
        conn.execute(text("""UPDATE core.site_pairings SET commit_mode = :c, send_mode = :s, every_minutes = :m,
                                 scope = CAST(:sc AS jsonb), note = :n, modified_at = now() WHERE side = :side AND name = :name"""),
                     {"c": v.get("commit_mode"), "s": v.get("send_mode"), "m": int(v.get("every_minutes") or 60),
                      "sc": json.dumps(v.get("scope") or {"all": True}), "n": str(v.get("note") or ""), "side": side, "name": name})


def _apply_banner(items: dict, by: str, ops: Callable) -> None:
    b = items.get("banner")
    if b:
        ops("POST", "/banner", {"banner": b, "by": by})
    else:
        ops("POST", "/banner/clear", {"by": by})


def _apply_allow(items: dict, by: str, ops: Callable, caller: str) -> None:
    from . import ip_allow
    cur = ops("GET", "/allow") or {}
    lists = {p: list(v) for p, v in (cur.get("lists") or {}).items()}
    trusted = list(cur.get("trusted") or [])
    for key, v in items.items():
        if key == "trusted":
            trusted = v
        else:
            lists[key.split(":", 1)[1]] = v
    try:
        clean = ip_allow.clean({"lists": lists, "trusted": trusted})
        if caller:
            ip_allow.guard(clean["lists"], caller, cur.get("internal") or [])
    except ip_allow.Refused as exc:
        raise TransferError(f"IP allow lists: {exc}", 409) from exc
    ops("POST", "/allow", clean | {"by": by})


def _apply_schedules(items: dict, by: str, ops: Callable, roles: list[str]) -> None:
    have = {s.get("name"): s for s in (ops("GET", "/commands/schedules") or {}).get("schedules") or []}
    for key, v in items.items():
        name = key.split(":", 1)[1]
        old = have.get(name)
        same_job = old and old.get("argv") == v.get("argv") and old.get("cron") == v.get("cron")
        if old and (same_job or old.get("system")):          # only on or off (EA Explorer's own: never remade)
            if bool(old.get("enabled")) != bool(v.get("enabled")):
                ops("POST", f"/commands/schedules/{old['id']}/{'on' if v.get('enabled') else 'off'}", {"by": by, "roles": roles})
            continue
        if old:
            ops("POST", f"/commands/schedules/{old['id']}/remove", {"by": by, "roles": roles})
        if not v.get("cron"):
            raise TransferError(f"The schedule {name} has no repeating time (a cron line): make it on the Command centre.")
        ops("POST", "/commands/schedules", {"name": name, "argv": v.get("argv"), "cron": v["cron"], "enabled": bool(v.get("enabled", True)),
                                            "backup_first": v.get("backup_first", False), "keep": v.get("keep", 3),
                                            "banner": v.get("banner", False), "by": by, "roles": roles})


def take(conn, raw, picks: dict, by: str, ops: Callable = ops_call, caller: str = "", roles: list[str] | None = None,
         record: Callable | None = None, why: str = "import", keep: Callable | None = None) -> dict:
    """Takes the differences picked ({part: [keys]} or {part: "all"}): a safety copy first, then each part; every change
    recorded. Returns what was taken, what could not be, the safety copy's id and anything to tell.

    The safety copy is kept by `keep(body, parts)` (its own transaction, so it stays if the import then fails; by default
    in conn). The database's parts go first, the operations helper's last (banner, allow lists, schedules: they cannot
    be rolled back with the database), so a failure in the database's parts changes nothing at all."""
    f = load(raw)
    parts = [p for p in chosen(list(picks)) if p in f["parts"]]
    here, _missing = read_parts(conn, parts, ops)
    differences = diff(here, {p: f["parts"][p] for p in parts if p in here})
    todo: dict[str, dict] = {}
    refused: list[str] = []
    for p in parts:
        wanted = picks.get(p)
        for row in differences.get(p, {}).get("differences", []):
            if wanted != "all" and row["key"] not in (wanted or []):
                continue
            if row["cannot"]:
                refused.append(f"{PARTS[p][0]} {row['key']}: {row['cannot']}")
                continue
            todo.setdefault(p, {})[row["key"]] = f["parts"][p][row["key"]]
    if not todo:
        return {"taken": {}, "refused": refused, "copy": None, "said": ["Nothing to take: this installation already has it."]}
    body = export(conn, list(todo), by=by, ops=ops)
    copy = (keep or (lambda b, ps: keep_copy(conn, b, ps, by, why)))(body, list(todo))
    said: list[str] = []
    done_ops: list[str] = []
    for p in sorted(todo, key=lambda x: x in OPS_PARTS):         # the database first, the operations helper last
        try:
            said += _apply(conn, p, todo[p], by, ops, caller, roles)
        except Exception as exc:  # noqa: BLE001 - said in words, with what was already taken
            msg = f"{PARTS[p][0]} could not be taken: {exc}. Nothing in the database was changed"
            if done_ops:
                msg += (f"; {', '.join(done_ops)} had already been taken: put them back with Undo on the safety copy "
                        f"just kept ({copy})")
            raise TransferError(msg + ".", getattr(exc, "status", 400)) from exc
        if p in OPS_PARTS:
            done_ops.append(PARTS[p][0])
        for key, v in todo[p].items():
            before = here.get(p, {}).get(key)
            (record or _record)(conn, by, f"settings.{why}", p, key,
                                {"before": _shown(before), "after": _shown(v), "copy": copy, "from": f.get("site") or ""})
    return {"taken": {p: sorted(v) for p, v in todo.items()}, "refused": refused, "copy": copy, "said": said}


def _apply(conn, p: str, items: dict, by: str, ops: Callable, caller: str, roles: list[str] | None) -> list[str]:
    """One part's differences taken; anything to tell."""
    said: list[str] = []
    if p in ("application", "system", "security"):
        _apply_registry(conn, items, by)
    elif p == "branding":
        _apply_branding(conn, items, by)
    elif p == "alerts":
        _apply_alerts(conn, items, by)
    elif p == "retention":
        _apply_retention(conn, items, by)
    elif p == "audiences":
        _apply_audiences(conn, items, by)
    elif p == "webhooks":
        said += _apply_webhooks(conn, items, by)
    elif p == "pairings":
        _apply_pairings(conn, items, by)
    elif p == "banner":
        _apply_banner(items, by, ops)
    elif p == "allow_lists":
        _apply_allow(items, by, ops, caller)
    elif p == "schedules":
        _apply_schedules(items, by, ops, roles or ["super-admin"])
    return said


def _record(conn, by: str, action: str, part: str, key: str, details: dict) -> None:
    from . import audit
    audit.record(conn, actor=by, action=action, object_type=f"settings.{part}", object_id=key[:200], details=details)


# ---------------------------------------------------------------- the safety copies and undo
def keep_copy(conn, body: dict, parts: list[str], by: str, why: str) -> str:
    """The settings as they were (an export of the parts an import changes) kept; its id (undo puts them back)."""
    return str(conn.execute(text("""INSERT INTO core.settings_copies (made_by, why, parts, body)
                                    VALUES (:b, :w, :p, CAST(:j AS jsonb)) RETURNING guid"""),
                            {"b": by, "w": why[:60], "p": parts, "j": json.dumps(body)}).scalar())


def copies(conn, limit: int = 30) -> list[dict]:
    """The safety copies, newest first (without their contents)."""
    return [{**dict(r), "id": str(r["id"]), "made_at": r["made_at"].isoformat() if r["made_at"] else None,
             "parts": list(r["parts"] or [])}
            for r in conn.execute(text("""SELECT guid AS id, made_at, made_by, why, parts, undone_at IS NOT NULL AS undone
                                          FROM core.settings_copies ORDER BY made_at DESC LIMIT :n"""), {"n": limit}).mappings()]


def undo(conn, copy_id: str, by: str, ops: Callable = ops_call, caller: str = "", roles: list[str] | None = None,
         keep: Callable | None = None) -> dict:
    """Puts back the settings a safety copy kept (its parts; every difference taken); itself undoable."""
    r = conn.execute(text("SELECT body, parts FROM core.settings_copies WHERE guid::text = :g"), {"g": str(copy_id)}).first()
    if not r:
        raise TransferError("There is no such safety copy.", 404)
    out = take(conn, r[0], {p: "all" for p in r[1] or []}, by, ops, caller, roles, why="undo", keep=keep)
    conn.execute(text("UPDATE core.settings_copies SET undone_at = now(), undone_by = :b WHERE guid::text = :g"),
                 {"b": by, "g": str(copy_id)})
    return out


# ---------------------------------------------------------------- the command line: python -m eax.settings_transfer
def _cli(argv: list[str]) -> int:
    """export [--parts a,b] | preview [--parts a,b] | import [--parts a,b] --yes | copies | undo <id>: one JSON line on
    stdout (the settings file comes and goes on stdin and stdout; eaxcli/settings_cli.py writes and reads the file)."""
    from .db import get_engine
    action = argv[0] if argv else ""
    parts = argv[argv.index("--parts") + 1] if "--parts" in argv and argv.index("--parts") + 1 < len(argv) else None
    by = argv[argv.index("--by") + 1] if "--by" in argv and argv.index("--by") + 1 < len(argv) else "eax"
    site = os.environ.get("EAX_INSTALLATION_NAME", "")
    engine = get_engine()

    def keep(why: str):
        def kept(body: dict, ps: list[str]) -> str:
            with engine.begin() as c:              # its own transaction: it stays if the import then fails
                return keep_copy(c, body, ps, by, why)
        return kept
    try:
        if action == "export":
            with engine.connect() as conn:
                print(json.dumps(export(conn, parts, by=by, site=site), sort_keys=True))
            return 0
        if action == "copies":
            with engine.connect() as conn:
                print(json.dumps({"copies": copies(conn)}, default=str))
            return 0
        if action == "undo":
            with engine.begin() as conn:
                print(json.dumps(undo(conn, argv[1] if len(argv) > 1 else "", by, keep=keep("undo")), default=str))
            return 0
        if action in ("preview", "import"):
            raw = sys.stdin.read()
            if action == "preview" or "--yes" not in argv:
                with engine.connect() as conn:
                    print(json.dumps(preview(conn, raw, parts), default=str))
                return 0
            with engine.begin() as conn:
                print(json.dumps(take(conn, raw, {p: "all" for p in chosen(parts)}, by, keep=keep("import")), default=str))
            return 0
    except TransferError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    except Exception as exc:  # noqa: BLE001 - a setting's own check (EditError, ValueError ...): in words
        print(json.dumps({"error": f"Nothing was changed: {exc}"}))
        return 2
    print(json.dumps({"error": "export | preview | import --yes | copies | undo <id>"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
