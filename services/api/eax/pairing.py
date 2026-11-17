"""Site pairings and sync (Release 6.5, D749; owner, 17 Nov 2026, 19:30 to 19:40).

Two EA Explorer sites are paired one way: **Site 1 sends, Site 2 takes**.

* **Pairing.** On Site 2 a Super Admin makes a pairing key (System Admin › Site pairings › Make a key). On Site 1 a Super
  Admin gives Site 2's address and that key, and chooses content sync or DR sync. Site 1 introduces itself; Site 2's
  Super Admin accepts (or refuses). Nothing is sent before that.
* **One way only, over HTTPS, from a queue in the database.** Each batch has a sequence number for its pairing; Site 2
  answers every one (received, already had it, or the number it expects next, so a gap is sent again). The batches are
  rows of core.sync_batches with their zip files beside them under the backups folder.
* **Content sync**: models, projects (with their documents) and the organisation's content: the entire site or chosen
  models and projects. On Site 2 what arrives overrides what is there. Site 2 commits by hand (the admin looks first) or by
  itself.
* **DR sync**: the same plus the users and their roles; always committed by itself; Site 2 is read only while the pairing
  holds (DR copy). Taking over (a failover) stops the pairing on Site 2 and lifts the read only; failing back is pairing
  the other way.
* **Sending**: by hand (Sync now), or by itself every so many minutes: then only what changed since the last send goes.
* **Promotion** is not here: a model's or a project's package is downloaded and uploaded where it was already (Import and
  export, Back up), and a git repository is one more place to put it and take it from (eax/gitpackages.py; owner, 17 Nov
  2026, 20:51: "github being just one more item ... zip is already there").
* **Site purpose**: a label only (PROD by default), shown at the top of every screen (setting site_purpose).

A batch file (eax-sync/1):
  batch.json                       what it is: from which site, the pairing, its number, what it holds
  items/model-<guid>.zip           a model backup (as Model admin makes)
  items/project-<guid>.zip         a project backup (as the project's Back up makes), its models named, not carried
  items/organisation.zip           the organisation's content (as the application backup carries it)
  items/users.json                 DR only: the people and their roles (from Keycloak)

Users and roles come across without their passwords (Keycloak does not give them out): on the DR site people sign in
through the organisation's own directory, or set a password with "Forgot password" (docs/site-pairings.md).
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
import socket
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from . import __version__
from .metamodel_edit import EditError

FORMAT = "eax-sync/1"
KEY_PREFIX = "eaxp_"
KINDS = ("content", "dr")
PURPOSES = ("PROD", "PRE-PROD", "UAT", "TEST", "DEV", "DR", "TRAINING")
BATCH_MB = 50                       # items are grouped into batches of about this size
TIMEOUT = 120
FIELDS = ("guid AS id, side, name, peer_url, peer_name, peer_guid, peer_pin, kind, status, commit_mode, send_mode, "
          "every_minutes, scope, (key_enc IS NOT NULL OR key_hash IS NOT NULL) AS has_key, next_seq, last_seq, "
          "last_sent_at, last_received_at, last_auto_at, last_error, note, created_by, created_at, modified_at")
BATCH_FIELDS = ("b.guid AS id, b.direction, b.seq, b.status, b.items, b.size, b.attempts, b.reply, b.error, "
                "b.notes, b.created_by, b.created_at, b.sent_at, b.committed_at, b.committed_by")
_URL = re.compile(r"^https?://[^\s/]+[^\s]*$")


class SyncUser:
    """Who a commit is done as: the pairing (a Super Admin's rights, recorded under its own name)."""
    def __init__(self, name: str):
        self.username = name[:60]
        self.roles = ["super-admin"]
        self.email = None
        self.machine = None

    def has_role(self, role: str) -> bool:
        """Whether the pairing's user has this global role (a Super Admin's only)."""
        return role in self.roles

    def can(self, permission: str, model_roles=None) -> bool:
        """A pairing's commit may do anything a Super Admin may (it puts the sending site's content in place)."""
        return True


# ---------------------------------------------------------------- small helpers
def _rows(conn, sql: str, **p) -> list[dict]:
    return [dict(r) for r in conn.execute(text(sql), p).mappings().all()]


def _need_super(user) -> None:
    if "super-admin" not in (getattr(user, "roles", ()) or ()):
        raise EditError("Only a Super Admin pairs sites, sends or commits.", 403)


def folder() -> Path:
    """Where the batch files are: <backups>/sync (the backups volume, so a DR pack and backups never hold them twice)."""
    from . import backups as bk
    return bk.root() / "sync"


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def sha256(data: bytes) -> str:
    """The SHA-256 of some bytes, as hex (a batch's and an item's check)."""
    return hashlib.sha256(data).hexdigest()


def hash_key(key: str) -> str:
    """The SHA-256 a pairing key is kept as on the receiving site (the key itself is never kept there)."""
    return hashlib.sha256(key.strip().encode()).hexdigest()


def new_key(pairing_guid: str) -> str:
    """A pairing key: eaxp_<the receiving pairing's id, without dashes>_<40 random characters>."""
    return f"{KEY_PREFIX}{pairing_guid.replace('-', '')}_{secrets.token_urlsafe(30)}"


def key_pairing(key: str) -> str | None:
    """The receiving pairing's id a key names (None: not a pairing key)."""
    m = re.fullmatch(r"eaxp_([0-9a-f]{32})_[A-Za-z0-9_-]{20,}", (key or "").strip())
    if not m:
        return None
    h = m.group(1)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def purpose(conn=None) -> str:
    """This site's purpose label (PROD by default): a label only, nothing behaves differently."""
    from . import settings as S
    try:
        v = str(S.values(conn).get("site_purpose") or "PROD")
    except Exception:  # noqa: BLE001 - the database not there yet
        v = "PROD"
    return v if v in PURPOSES else "PROD"


# ---------------------------------------------------------------- the pairings
def listing(conn) -> dict:
    """Every pairing on this site (sending and receiving), the queue's state of each, and whether this is a DR copy."""
    out = _rows(conn, f"SELECT {FIELDS} FROM core.site_pairings ORDER BY side, lower(name)")
    for p in out:
        counts = _rows(conn, """SELECT b.status, count(*) AS n FROM core.sync_batches b JOIN core.site_pairings s ON s.id = b.pairing_id
                                 WHERE s.guid = CAST(:g AS uuid) GROUP BY b.status""", g=str(p["id"]))
        p["batches"] = {r["status"]: r["n"] for r in counts}
        p["lag"] = _lag(p)
    return {"pairings": out, "dr_copy": dr_copy(conn), "purpose": purpose(conn), "local": _local_name(conn)}


def _lag(p: dict) -> str:
    """How far behind a pairing is, in words (the DR copy shows it)."""
    at = p.get("last_received_at") if p["side"] == "receiver" else p.get("last_sent_at")
    if not at:
        return "nothing yet"
    mins = int((datetime.now(UTC) - at).total_seconds() // 60)
    return "just now" if mins < 1 else f"{mins} minutes ago" if mins < 120 else f"{mins // 60} hours ago"


def _one(conn, ident: Any) -> dict:
    r = _rows(conn, f"SELECT id AS _id, key_enc, key_hash, {FIELDS} FROM core.site_pairings WHERE guid = CAST(:g AS uuid)",
              g=str(ident))
    if not r:
        raise EditError("No such pairing.", 404)
    return r[0]


def _shape(p: dict) -> dict:
    return {k: v for k, v in p.items() if k not in ("_id", "key_enc", "key_hash")}


def _local_name(conn) -> str:
    from . import sites
    try:
        return next((s["name"] for s in sites.listing(conn) if s.get("source") == "local"), "Local")
    except Exception:  # noqa: BLE001 - the farm schema elsewhere and away
        return "Local"


def _clean_scope(raw: Any, kind: str) -> dict:
    """{"all": true} (the entire site) or {"models": [guid...], "projects": [guid...], "organisation": bool}; DR is always
    the entire site."""
    if kind == "dr" or not isinstance(raw, dict) or raw.get("all", False):
        return {"all": True}
    guid = re.compile(r"^[0-9a-fA-F-]{36}$")
    models = [str(x) for x in raw.get("models") or [] if guid.match(str(x))]
    projects = [str(x) for x in raw.get("projects") or [] if guid.match(str(x))]
    if not models and not projects and not raw.get("organisation"):
        raise EditError("Choose the entire site, or at least one model or project.")
    return {"all": False, "models": models, "projects": projects, "organisation": bool(raw.get("organisation"))}


def make_key(conn, user, name: str = "", note: str = "") -> dict:
    """Site 2: a pairing key to give Site 1 (shown once; only its hash is kept). The pairing waits for Site 1."""
    _need_super(user)
    name = (name or "").strip() or f"Key made {datetime.now(UTC):%Y-%m-%d %H:%M} UTC"
    if len(name) > 120:
        raise EditError("Give the key a name up to 120 characters.")
    if _rows(conn, "SELECT 1 AS x FROM core.site_pairings WHERE side = 'receiver' AND lower(name) = lower(:n)", n=name):
        raise EditError(f"There is already a pairing called {name}.", 409)
    g = conn.execute(text("""INSERT INTO core.site_pairings (side, name, status, commit_mode, note, created_by)
                              VALUES ('receiver', :n, 'key', 'manual', :note, :by) RETURNING guid"""),
                     {"n": name, "note": note[:2000], "by": user.username}).scalar_one()
    key = new_key(str(g))
    conn.execute(text("UPDATE core.site_pairings SET key_hash = :h WHERE guid = :g"), {"h": hash_key(key), "g": g})
    return {**_shape(_one(conn, g)), "key": key,
            "say": "Give this key to the Super Admin of the site that will send. It is shown once."}


def pair(conn, user, d: dict, call=None) -> dict:
    """Site 1: pair with Site 2 {name, url, key, kind, send_mode, every_minutes, scope, trust}: introduces itself to
    Site 2 (which then waits for its admin to accept). trust: the SHA-256 of Site 2's certificate, when it is not one
    this site trusts (a laptop's own) and the admin checked it."""
    from . import remote_instances as ri
    _need_super(user)
    name = str(d.get("name") or "").strip()
    url = str(d.get("url") or "").strip().rstrip("/")
    key = str(d.get("key") or "").strip()
    kind = str(d.get("kind") or "content")
    if not name or len(name) > 120:
        raise EditError("Give the pairing a name (up to 120 characters).")
    if not _URL.match(url) or len(url) > 500:
        raise EditError("Site 2's address is its web address, for example https://ea-dr.example.com.")
    if not url.startswith("https://"):
        raise EditError("Sites are paired over HTTPS only.")
    if kind not in KINDS:
        raise EditError("The kind is content (content only) or dr (content, users and roles; Site 2 read only).")
    if not key_pairing(key):
        raise EditError("That is not a pairing key: make one on Site 2 (System Admin › Site pairings › Make a key).")
    if _rows(conn, "SELECT 1 AS x FROM core.site_pairings WHERE side = 'sender' AND lower(name) = lower(:n)", n=name):
        raise EditError(f"There is already a pairing called {name}.", 409)
    send_mode = "auto" if kind == "dr" else ("auto" if d.get("send_mode") == "auto" else "manual")
    every = int(d.get("every_minutes") or (15 if kind == "dr" else 60))
    if not 5 <= every <= 10080:
        raise EditError("Send every 5 minutes to every 7 days (10,080 minutes).")
    scope = _clean_scope(d.get("scope"), kind)
    pin = str(d.get("trust") or "").strip().lower().replace(":", "")
    g = conn.execute(text("""INSERT INTO core.site_pairings (side, name, peer_url, kind, status, send_mode, every_minutes,
                                                              scope, key_enc, peer_pin, created_by)
                              VALUES ('sender', :n, :u, :k, 'waiting', :sm, :e, CAST(:s AS jsonb), :ke, :pin, :by)
                              RETURNING guid"""),
                     {"n": name, "u": url, "k": kind, "sm": send_mode, "e": every, "s": json.dumps(scope),
                      "ke": ri.encrypt(key), "pin": pin, "by": user.username}).scalar_one()
    p = _one(conn, g)
    answer = (call or peer_call)(p, "POST", "/api/v1/sync/hello",
                                 {"sender": {"name": _local_name(conn), "url": _own_url(), "pairing": str(g),
                                             "purpose": purpose(conn), "version": __version__}, "kind": kind, "key": key})
    conn.execute(text("""UPDATE core.site_pairings SET peer_guid = CAST(:pg AS uuid), peer_name = :pn, status = :st,
                                last_error = '', modified_at = now() WHERE guid = :g"""),
                 {"pg": answer.get("pairing"), "pn": str(answer.get("site") or "")[:120],
                  "st": "accepted" if answer.get("status") == "accepted" else "waiting", "g": g})
    return _shape(_one(conn, g))


def _own_url() -> str:
    from . import sites
    try:
        return sites.local_url()
    except Exception:  # noqa: BLE001
        return ""


def hello(conn, key: str, body: dict) -> dict:
    """Site 2, called by Site 1: the key checked, the pairing filled in (Site 1's name, address, kind), waiting for this
    site's Super Admin to accept."""
    p = _by_key(conn, key, allow=("key", "waiting"))
    sender = body.get("sender") or {}
    kind = str(body.get("kind") or "content")
    if kind not in KINDS:
        raise EditError("Unknown kind.", 400)
    conn.execute(text("""UPDATE core.site_pairings SET peer_url = :u, peer_name = :n, peer_guid = CAST(:pg AS uuid), kind = :k,
                                status = 'waiting', commit_mode = CASE WHEN :k = 'dr' THEN 'auto' ELSE commit_mode END,
                                note = :note, modified_at = now() WHERE id = :id"""),
                 {"u": str(sender.get("url") or "")[:500], "n": str(sender.get("name") or "")[:120],
                  "pg": sender.get("pairing") if re.fullmatch(r"[0-9a-f-]{36}", str(sender.get("pairing") or "")) else None,
                  "k": kind, "note": f"{sender.get('purpose') or ''} site, EA Explorer {sender.get('version') or '?'}"[:200],
                  "id": p["_id"]})
    return {"pairing": str(p["id"]), "status": "waiting", "site": _local_name(conn),
            "say": "Paired: waiting for this site's Super Admin to accept."}


def _by_key(conn, key: str, allow: tuple[str, ...] = ("accepted",)) -> dict:
    """The receiving pairing a key opens, refused unless its state is one of allow."""
    g = key_pairing(key)
    if not g:
        raise EditError("Not a pairing key.", 401)
    rows = _rows(conn, "SELECT id AS _id, key_hash, guid AS id, status, kind, commit_mode, last_seq, name FROM core.site_pairings "
                       "WHERE guid = CAST(:g AS uuid) AND side = 'receiver'", g=g)
    if not rows or not secrets.compare_digest(rows[0]["key_hash"] or "", hash_key(key)):
        raise EditError("This pairing key is not known here.", 401)
    p = rows[0]
    if p["status"] not in allow:
        say = {"refused": "refused by this site's Super Admin", "stopped": "stopped on this site (it may have taken over)",
               "waiting": "waiting for this site's Super Admin to accept", "key": "not introduced yet"}
        raise EditError(f"The pairing is {say.get(p['status'], p['status'])}.", 403)
    return p


def decide(conn, user, ident: Any, action: str, d: dict | None = None) -> dict:
    """accept (Site 2: {commit_mode}), refuse (Site 2), stop (either side; on a DR copy: take over, read only lifted),
    resume (Site 1 after a stop on its side), change (Site 1: {send_mode, every_minutes, scope}; Site 2: {commit_mode})."""
    _need_super(user)
    d = d or {}
    p = _one(conn, ident)
    if action == "accept":
        if p["side"] != "receiver" or p["status"] != "waiting":
            raise EditError("Only a pairing waiting on this site is accepted here.", 409)
        mode = "auto" if p["kind"] == "dr" else ("auto" if d.get("commit_mode") == "auto" else "manual")
        conn.execute(text("UPDATE core.site_pairings SET status = 'accepted', commit_mode = :m, modified_at = now() WHERE id = :id"),
                     {"m": mode, "id": p["_id"]})
    elif action == "refuse":
        if p["side"] != "receiver" or p["status"] not in ("waiting", "key"):
            raise EditError("Only a pairing waiting on this site is refused.", 409)
        conn.execute(text("UPDATE core.site_pairings SET status = 'refused', modified_at = now() WHERE id = :id"), {"id": p["_id"]})
    elif action == "stop":
        conn.execute(text("UPDATE core.site_pairings SET status = 'stopped', modified_at = now() WHERE id = :id"), {"id": p["_id"]})
        forget_dr()
    elif action == "resume":
        if p["side"] != "sender" or p["status"] != "stopped":
            raise EditError("Only a pairing stopped on this (sending) site resumes; Site 2 must still accept it.", 409)
        conn.execute(text("UPDATE core.site_pairings SET status = 'waiting', last_error = '', modified_at = now() WHERE id = :id"),
                     {"id": p["_id"]})
    elif action == "change":
        if p["side"] == "sender":
            send_mode = "auto" if p["kind"] == "dr" else ("auto" if d.get("send_mode", p["send_mode"]) == "auto" else "manual")
            every = int(d.get("every_minutes") or p["every_minutes"])
            if not 5 <= every <= 10080:
                raise EditError("Send every 5 minutes to every 7 days (10,080 minutes).")
            scope = _clean_scope(d.get("scope", p["scope"]), p["kind"])
            conn.execute(text("""UPDATE core.site_pairings SET send_mode = :sm, every_minutes = :e, scope = CAST(:s AS jsonb),
                                        modified_at = now() WHERE id = :id"""),
                         {"sm": send_mode, "e": every, "s": json.dumps(scope), "id": p["_id"]})
        else:
            mode = "auto" if p["kind"] == "dr" else ("auto" if d.get("commit_mode") == "auto" else "manual")
            conn.execute(text("UPDATE core.site_pairings SET commit_mode = :m, modified_at = now() WHERE id = :id"),
                         {"m": mode, "id": p["_id"]})
    else:
        raise EditError("accept, refuse, stop, resume or change.")
    return _shape(_one(conn, ident))


def remove(conn, user, ident: Any) -> dict:
    """A pairing removed with its queue (its files too). A DR copy's read only is lifted."""
    _need_super(user)
    p = _one(conn, ident)
    for b in _rows(conn, "SELECT file FROM core.sync_batches WHERE pairing_id = :id", id=p["_id"]):
        if b["file"]:
            (folder() / b["file"]).unlink(missing_ok=True)
    conn.execute(text("DELETE FROM core.site_pairings WHERE id = :id"), {"id": p["_id"]})
    forget_dr()
    return {"deleted": str(p["id"])}


# ---------------------------------------------------------------- a DR copy is read only
_dr: dict[str, Any] = {"at": 0.0, "value": None}
DR_ALLOWED = ("/api/v1/sync/", "/api/v1/pairings", "/api/v1/internal/", "/api/v1/heartbeat", "/api/v1/me")


def forget_dr() -> None:
    """The DR copy state read again at the next request (after a pairing is stopped or removed)."""
    _dr["at"] = 0.0


def dr_copy(conn=None) -> dict | None:
    """When this site is a DR copy (an accepted DR pairing receiving here): from which site, how far behind. Cached for
    15 seconds."""
    if conn is None and time.monotonic() - _dr["at"] < 15:
        return _dr["value"]
    def read(c):
        r = _rows(c, """SELECT guid AS id, name, peer_name, peer_url, last_received_at FROM core.site_pairings
                         WHERE side = 'receiver' AND kind = 'dr' AND status = 'accepted' ORDER BY id LIMIT 1""")
        return ({"pairing": str(r[0]["id"]), "from": r[0]["peer_name"] or r[0]["name"], "url": r[0]["peer_url"],
                 "last": r[0]["last_received_at"].isoformat() if r[0]["last_received_at"] else None} if r else None)
    try:
        if conn is not None:
            return read(conn)
        from .db import get_engine
        with get_engine().connect() as c:
            value = read(c)
    except Exception:  # noqa: BLE001 - the database not there yet, or the table not made yet
        value = None
    _dr.update(at=time.monotonic(), value=value)
    return value


def refused_on_dr(method: str, path: str) -> str | None:
    """Why a change is refused on a DR copy (None: allowed). Reading is always allowed; the pairings page and the sync
    itself stay open (to take over, a Super Admin stops the pairing)."""
    if method in ("GET", "HEAD", "OPTIONS") or any(path.startswith(a) for a in DR_ALLOWED):
        return None
    d = dr_copy()
    if not d:
        return None
    return (f"This site is a DR copy of {d['from']}: it is read only, kept up to date by DR sync. To work here (a "
            "failover), a Super Admin stops the pairing on System Admin › Site pairings.")


# ---------------------------------------------------------------- calling the other site
def _ssl(pin: str) -> ssl.SSLContext:
    """Verified as usual; with a pin (the other site's certificate the admin checked by hand), that certificate only."""
    ctx = ssl.create_default_context()
    if pin:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE           # checked against the pin below instead
    return ctx


def certificate_of(url: str, timeout: int = 10) -> str:
    """The SHA-256 of a site's certificate (for the admin to compare with what Site 2 shows on its pairings page)."""
    from urllib.parse import urlparse
    u = urlparse(url)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((u.hostname, u.port or 443), timeout=timeout) as s, \
            ctx.wrap_socket(s, server_hostname=u.hostname) as t:
        return hashlib.sha256(t.getpeercert(binary_form=True)).hexdigest()


def peer_call(p: dict, method: str, path: str, body: dict | None = None, data: bytes | None = None,
              headers: dict | None = None, key: str | None = None) -> dict:
    """A call to the other site's sync API with the pairing key; its JSON answer. Refusals become EditErrors with the
    other site's words."""
    from . import remote_instances as ri
    key = key or ri.decrypt(p["key_enc"])
    h = {"Authorization": f"Pairing {key}", **(headers or {})}
    raw = data
    if body is not None:
        raw = json.dumps(body, default=str).encode()
        h["Content-Type"] = "application/json"
    url = f"{p['peer_url'].rstrip('/')}{path}"
    pin = str(p.get("peer_pin") or "")
    if pin:
        got = certificate_of(url)
        if got != pin:
            raise EditError(f"Site 2's certificate has changed ({got[:16]}…, trusted {pin[:16]}…): check it, then pair again.", 502)
    req = urllib.request.Request(url, data=raw, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl(pin)) as r:  # noqa: S310 - https only (checked at pairing)
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            ans = json.loads(exc.read() or b"{}")
        except ValueError:
            ans = {}
        err = EditError(str(ans.get("message") or f"Site 2 answered {exc.code} {exc.reason}"), exc.code)
        err.answer = ans                                 # type: ignore[attr-defined]
        raise err from exc
    except ssl.SSLError as exc:
        raise EditError(f"Site 2's certificate is not trusted here ({exc.reason}). If it is a laptop's own, compare its "
                        f"fingerprint and trust it when pairing: {_fingerprint_or_blank(url)}", 502) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EditError(f"Site 2 did not answer: {getattr(exc, 'reason', exc)}", 502) from exc


def _fingerprint_or_blank(url: str) -> str:
    try:
        return certificate_of(url)
    except Exception:  # noqa: BLE001
        return "(could not be read)"


# ---------------------------------------------------------------- what is sent: the items and their fingerprints
def _scope_items(core, pc, p: dict) -> list[dict]:
    """The items a pairing covers: models, projects, the organisation, users (DR)."""
    scope = p.get("scope") or {"all": True}
    core.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
    if scope.get("all", True):
        models = _rows(core, """SELECT guid::text AS id, name FROM core.models WHERE NOT is_deleted AND kind_code <> 'template'
                                 AND NOT coalesce(is_test_data, false) ORDER BY id""")
        projects = _rows(pc, "SELECT guid::text AS id, name FROM proj.projects WHERE NOT coalesce(is_test_data, false) ORDER BY id")
        org = True
    else:
        models = _rows(core, "SELECT guid::text AS id, name FROM core.models WHERE guid::text = ANY (CAST(:g AS text[])) "
                             "AND NOT is_deleted ORDER BY id", g=scope.get("models") or [])
        projects = _rows(pc, "SELECT guid::text AS id, name FROM proj.projects WHERE guid::text = ANY (CAST(:g AS text[])) ORDER BY id",
                         g=scope.get("projects") or [])
        org = bool(scope.get("organisation"))
    items = [{"kind": "model", **m} for m in models] + [{"kind": "project", **x} for x in projects]
    if org:
        items.append({"kind": "organisation", "id": "organisation", "name": "The organisation's content"})
    if p.get("kind") == "dr":
        items.append({"kind": "users", "id": "users", "name": "Users and their roles"})
    return items


def fingerprint(core, pc, item: dict) -> str:
    """What changes when an item changes (cheap: no file is made): a model's commits and metamodel version, a project's
    rows' last changes and counts. The organisation and the users are always made, so their hash is their content's."""
    if item["kind"] == "model":
        r = _rows(core, """SELECT m.metamodel_version, m.modified_at, m.row_version,
                                  (SELECT coalesce(max(c.number), 0) FROM core.commits c WHERE c.model_id = m.id) AS commits
                             FROM core.models m WHERE m.guid = CAST(:g AS uuid)""", g=item["id"])
        return sha256(json.dumps(r, default=str).encode())
    if item["kind"] == "project":
        from . import project_backup as pb
        r = _rows(pc, "SELECT id, modified_at FROM proj.projects WHERE guid = CAST(:g AS uuid)", g=item["id"])
        if not r:
            return ""
        parts = [str(r[0]["modified_at"])]
        for table, where, _m in pb.TABLES:
            cols = pb._cols(pc, table)
            last = "max(modified_at)" if "modified_at" in cols else "max(created_at)" if "created_at" in cols else "NULL"
            q = _rows(pc, f"SELECT count(*) AS n, {last} AS at FROM proj.{table} WHERE {where}", p=r[0]["id"])
            parts.append(f"{table}:{q[0]['n']}:{q[0]['at']}")
        return sha256("|".join(parts).encode())
    return ""


def item_bytes(core, pc, item: dict, by: str) -> bytes:
    """One item as the bytes that go in the batch."""
    from . import backups as bk
    from . import org_backup
    from . import project_backup as pb
    from . import projects as pj
    if item["kind"] == "model":
        data, _info = bk.model_file(core, item["id"], by, "site sync")
        return data
    if item["kind"] == "project":
        data, _info = pb.project_file(core, pc, SyncUser(by), pj.project_row(pc, item["id"]), "site sync", with_models=False)
        return data
    if item["kind"] == "organisation":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            org_backup.write(z, core, pc)
        return buf.getvalue()
    if item["kind"] == "users":
        return json.dumps(users_out(), ensure_ascii=False).encode()
    raise EditError(f"Unknown item {item['kind']}.")


def _item_name(item: dict) -> str:
    return {"model": f"items/model-{item['id']}.zip", "project": f"items/project-{item['id']}.zip",
            "organisation": "items/organisation.zip", "users": "items/users.json"}[item["kind"]]


def build_file(items: list[tuple[dict, bytes]], head: dict) -> bytes:
    """A batch file (eax-sync/1) from its items and what it is."""
    buf = io.BytesIO()
    listed = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item, data in items:
            z.writestr(_item_name(item), data)
            listed.append({**item, "file": _item_name(item), "sha256": sha256(data), "size": len(data)})
        z.writestr("batch.json", json.dumps({"format": FORMAT, "version": __version__, "created": _stamp(), **head,
                                             "items": listed}, indent=2, default=str, ensure_ascii=False))
        z.writestr("README.txt", "EA Explorer site sync batch (eax-sync/1): batch.json says what it holds; "
                                 "Site 2 takes it on System Admin › Site pairings.\n")
    return buf.getvalue()


def read_file(data: bytes) -> tuple[dict, zipfile.ZipFile]:
    """A batch file opened; refused when it is not one or is from a newer EA Explorer."""
    from . import backups as bk
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        head = json.loads(z.read("batch.json"))
    except (KeyError, ValueError, zipfile.BadZipFile) as exc:
        raise EditError("That is not an EA Explorer sync batch.", 400) from exc
    if head.get("format") != FORMAT:
        raise EditError("That is not an EA Explorer sync batch.", 400)
    if bk.newer_than_here(head.get("version")):
        raise EditError(f"It was made by a newer EA Explorer ({head.get('version')}) than this site ({__version__}): "
                        "upgrade this site first.", 409)
    return head, z


# ---------------------------------------------------------------- Site 1: queueing and sending
def enqueue(core, pc, ident: Any, by: str, scope: dict | None = None, only_changed: bool = False) -> dict:
    """Site 1: the pairing's items made into batches in the queue (about BATCH_MB each, in order), each with the next
    sequence number. only_changed: those whose fingerprint differs from what was last sent (automatic sync)."""
    p = _one(core, ident)
    if p["side"] != "sender":
        raise EditError("Only the sending site queues batches.", 409)
    if p["status"] != "accepted":
        raise EditError(f"The pairing is {p['status']}: Site 2's Super Admin must accept it first.", 409)
    if scope is not None:
        p = {**p, "scope": _clean_scope(scope, p["kind"])}
    items = _scope_items(core, pc, p)
    sent = {(r["kind"], r["item"]): r["hash"] for r in
            _rows(core, "SELECT kind, item, hash FROM core.sync_sent WHERE pairing_id = :id", id=p["_id"])}
    groups: list[list[tuple[dict, bytes]]] = [[]]
    size, made, hashes = 0, [], {}
    for item in items:
        fp = fingerprint(core, pc, item)
        data = None
        if item["kind"] in ("organisation", "users"):
            data = item_bytes(core, pc, item, by)
            fp = sha256(data)
        if only_changed and fp and sent.get((item["kind"], item["id"])) == fp:
            continue
        data = data if data is not None else item_bytes(core, pc, item, by)
        hashes[(item["kind"], item["id"])] = fp
        if size and size + len(data) > BATCH_MB * 1024 * 1024:
            groups.append([])
            size = 0
        groups[-1].append(({**item, "hash": fp}, data))
        size += len(data)
    out = folder() / str(p["id"])
    out.mkdir(parents=True, exist_ok=True)
    for group in [g for g in groups if g]:
        seq = core.execute(text("UPDATE core.site_pairings SET next_seq = next_seq + 1 WHERE id = :id RETURNING next_seq - 1"),
                           {"id": p["_id"]}).scalar_one()
        data = build_file(group, {"site": {"name": _local_name(core), "url": _own_url(), "purpose": purpose(core)},
                                  "pairing": str(p["peer_guid"] or ""), "seq": seq, "kind": p["kind"], "by": by})
        file = f"{p['id']}/{seq:08d}-{_stamp()}.zip"
        (folder() / file).write_bytes(data)
        listed = [{k: v for k, v in i.items() if k in ("kind", "id", "name", "hash")} for i, _d in group]
        core.execute(text("""INSERT INTO core.sync_batches (pairing_id, direction, seq, status, items, file, sha256, size, created_by)
                             VALUES (:p, 'out', :s, 'queued', CAST(:i AS jsonb), :f, :h, :n, :by)"""),
                     {"p": p["_id"], "s": seq, "i": json.dumps(listed), "f": file, "h": sha256(data), "n": len(data), "by": by})
        made.append({"seq": seq, "items": len(group), "size": len(data)})
    for (kind, item), fp in hashes.items():
        if fp:
            core.execute(text("""INSERT INTO core.sync_sent (pairing_id, kind, item, hash) VALUES (:p, :k, :i, :h)
                                 ON CONFLICT (pairing_id, kind, item) DO UPDATE SET hash = EXCLUDED.hash, sent_at = now()"""),
                         {"p": p["_id"], "k": kind, "i": item, "h": fp})
    if only_changed:
        core.execute(text("UPDATE core.site_pairings SET last_auto_at = now() WHERE id = :id"), {"id": p["_id"]})
    return {"batches": made, "items": sum(b["items"] for b in made),
            "say": (f"{sum(b['items'] for b in made)} items in {len(made)} batches queued: they go in the next minute."
                    if made else "Nothing has changed since the last sync: nothing queued.")}


def due_for_auto(core, now: datetime | None = None) -> list[str]:
    """Site 1: the accepted pairings sending by themselves whose time has come."""
    now = now or datetime.now(UTC)
    out = []
    for p in _rows(core, """SELECT guid, every_minutes, last_auto_at FROM core.site_pairings
                             WHERE side = 'sender' AND status = 'accepted' AND send_mode = 'auto'"""):
        if not p["last_auto_at"] or p["last_auto_at"] + timedelta(minutes=p["every_minutes"]) <= now:
            out.append(str(p["guid"]))
    return out


def send_queued(core, call=peer_call, limit: int = 20) -> list[str]:
    """Site 1: the queued batches sent in order, each pairing's oldest first; Site 2's answer kept with each. A gap
    (Site 2 expects an earlier number) sends again from there; a refusal stops that pairing's sending for now."""
    said = []
    for p in _rows(core, f"SELECT id AS _id, key_enc, {FIELDS} FROM core.site_pairings WHERE side = 'sender' AND status = 'accepted'"):
        for b in _rows(core, """SELECT id, seq, file, sha256, attempts FROM core.sync_batches
                                 WHERE pairing_id = :p AND direction = 'out' AND status IN ('queued', 'failed')
                                 ORDER BY seq LIMIT :n""", p=p["_id"], n=limit):
            if b["attempts"] >= 3 and not _retry_due(core, b["id"]):
                break
            try:
                data = (folder() / b["file"]).read_bytes()
            except OSError as exc:
                _batch_failed(core, b["id"], f"its file is gone: {exc}")
                break
            try:
                ans = call(p, "POST", "/api/v1/sync/batch", data=data,
                           headers={"Content-Type": "application/zip", "X-Eax-Seq": str(b["seq"]), "X-Eax-Sha256": b["sha256"]})
            except EditError as exc:
                ans = getattr(exc, "answer", {}) or {}
                if ans.get("status") == "gap" and ans.get("expect"):
                    n = rewind(core, p["_id"], int(ans["expect"]))
                    said.append(f"{p['name']}: Site 2 expects batch {ans['expect']}; {n} sent again")
                    break
                _batch_failed(core, b["id"], str(exc))
                core.execute(text("UPDATE core.site_pairings SET last_error = :e WHERE id = :id"), {"e": str(exc)[:500], "id": p["_id"]})
                if exc.status == 403:
                    core.execute(text("UPDATE core.site_pairings SET status = 'stopped' WHERE id = :id"), {"id": p["_id"]})
                said.append(f"{p['name']} batch {b['seq']}: {exc}")
                break
            core.execute(text("""UPDATE core.sync_batches SET status = 'sent', sent_at = now(), attempts = attempts + 1,
                                        reply = CAST(:r AS jsonb), error = '' WHERE id = :id"""),
                         {"r": json.dumps(ans, default=str), "id": b["id"]})
            core.execute(text("UPDATE core.site_pairings SET last_sent_at = now(), last_error = '' WHERE id = :id"), {"id": p["_id"]})
            said.append(f"{p['name']} batch {b['seq']}: {ans.get('status')}")
    return said


def _retry_due(core, batch_id: int) -> bool:
    """After three failures a batch is tried again every 15 minutes (never dropped: the order must hold)."""
    r = _rows(core, "SELECT created_at, sent_at FROM core.sync_batches WHERE id = :id", id=batch_id)
    last = r[0]["sent_at"] or r[0]["created_at"]
    return datetime.now(UTC) - last >= timedelta(minutes=15)


def _batch_failed(core, batch_id: int, why: str) -> None:
    core.execute(text("""UPDATE core.sync_batches SET status = 'failed', attempts = attempts + 1, error = :e, sent_at = now()
                         WHERE id = :id"""), {"e": why[:1000], "id": batch_id})


def rewind(core, pairing_id: int, expect: int) -> int:
    """Site 2 expects an earlier batch (a gap, or it was restored): every batch from there is sent again."""
    return core.execute(text("""UPDATE core.sync_batches SET status = 'queued', attempts = 0, error = ''
                                 WHERE pairing_id = :p AND direction = 'out' AND seq >= :s"""),
                        {"p": pairing_id, "s": expect}).rowcount


def check_peers(core, call=peer_call) -> list[str]:
    """Site 1: each pairing waiting for Site 2 asked whether it was accepted; each accepted one asked what Site 2 has
    committed (its answers kept with the batches)."""
    said = []
    for p in _rows(core, f"""SELECT id AS _id, key_enc, {FIELDS} FROM core.site_pairings
                              WHERE side = 'sender' AND status IN ('waiting', 'accepted')"""):
        try:
            ans = call(p, "GET", "/api/v1/sync/status")
        except EditError as exc:
            core.execute(text("UPDATE core.site_pairings SET last_error = :e WHERE id = :id"), {"e": str(exc)[:500], "id": p["_id"]})
            if exc.status == 403 and "refused" in str(exc):
                core.execute(text("UPDATE core.site_pairings SET status = 'refused' WHERE id = :id"), {"id": p["_id"]})
            elif exc.status == 403 and "stopped" in str(exc):
                core.execute(text("UPDATE core.site_pairings SET status = 'stopped' WHERE id = :id"), {"id": p["_id"]})
            continue
        if ans.get("status") == "accepted" and p["status"] == "waiting":
            core.execute(text("UPDATE core.site_pairings SET status = 'accepted', last_error = '' WHERE id = :id"), {"id": p["_id"]})
            said.append(f"{p['name']}: accepted by Site 2")
        for c in ans.get("batches") or []:
            core.execute(text("""UPDATE core.sync_batches SET reply = coalesce(reply, '{}'::jsonb) || CAST(:r AS jsonb)
                                  WHERE pairing_id = :p AND direction = 'out' AND seq = :s"""),
                         {"r": json.dumps({"site2": c.get("status"), "site2_error": c.get("error") or ""}), "p": p["_id"],
                          "s": int(c.get("seq") or 0)})
    return said


# ---------------------------------------------------------------- Site 2: receiving and committing
def receive(core, key: str, seq: int, digest: str, data: bytes) -> tuple[int, dict]:
    """Site 2: a batch from Site 1. Taken only in order: the one expected next is kept (and committed by itself when the
    pairing says so); one already had is answered as such; a later one is answered with the number expected."""
    p = _by_key(core, key)
    if sha256(data) != (digest or "").lower():
        return 400, {"status": "damaged", "seq": seq, "expect": p["last_seq"] + 1,
                     "message": "The batch arrived damaged (its SHA-256 does not match): send it again."}
    if seq <= p["last_seq"]:
        return 200, {"status": "duplicate", "seq": seq, "expect": p["last_seq"] + 1}
    if seq != p["last_seq"] + 1:
        return 409, {"status": "gap", "seq": seq, "expect": p["last_seq"] + 1,
                     "message": f"Batch {p['last_seq'] + 1} is expected first."}
    head, _z = read_file(data)
    file = f"in-{p['id']}/{seq:08d}-{_stamp()}.zip"
    (folder() / file).parent.mkdir(parents=True, exist_ok=True)
    (folder() / file).write_bytes(data)
    status = "received" if p["commit_mode"] == "auto" else "waiting"
    core.execute(text("""INSERT INTO core.sync_batches (pairing_id, direction, seq, status, items, file, sha256, size, created_by)
                         VALUES (:p, 'in', :s, :st, CAST(:i AS jsonb), :f, :h, :n, :by)"""),
                 {"p": p["_id"], "s": seq, "st": status, "i": json.dumps(head.get("items") or [], default=str), "f": file,
                  "h": sha256(data), "n": len(data), "by": str(head.get("by") or "")[:60]})
    core.execute(text("UPDATE core.site_pairings SET last_seq = :s, last_received_at = now() WHERE id = :id"), {"s": seq, "id": p["_id"]})
    return 200, {"status": "received", "seq": seq, "expect": seq + 1,
                 "commit": "by itself" if status == "received" else "waiting for this site's admin"}


def status_for_peer(core, key: str) -> dict:
    """Site 2, asked by Site 1: the pairing's state and what became of the last batches."""
    p = _by_key(core, key, allow=("waiting", "accepted"))
    batches = _rows(core, """SELECT seq, status, error FROM core.sync_batches WHERE pairing_id = :p AND direction = 'in'
                              ORDER BY seq DESC LIMIT 50""", p=p["_id"])
    return {"status": p["status"], "last_seq": p["last_seq"], "expect": p["last_seq"] + 1, "batches": batches,
            "site": _local_name(core), "version": __version__}


def batches(core, ident: Any, limit: int = 100) -> list[dict]:
    """A pairing's batches, newest first."""
    p = _one(core, ident)
    return _rows(core, f"SELECT {BATCH_FIELDS} FROM core.sync_batches b WHERE b.pairing_id = :p ORDER BY b.seq DESC, b.id DESC LIMIT :n",
                 p=p["_id"], n=limit)


def _batch(core, ident: Any) -> dict:
    r = _rows(core, """SELECT b.id AS _id, b.file, b.pairing_id, s.side, s.name AS pairing_name, s.kind AS pairing_kind, """
                    f"""{BATCH_FIELDS} FROM core.sync_batches b LEFT JOIN core.site_pairings s ON s.id = b.pairing_id
                        WHERE b.guid = CAST(:g AS uuid)""", g=str(ident))
    if not r:
        raise EditError("No such batch.", 404)
    return r[0]


def next_to_commit(core) -> list[str]:
    """Site 2: the batches received to commit by themselves, oldest first per pairing (one at a time per pairing: a
    batch waits while an earlier one of its pairing is not committed)."""
    out = []
    for r in _rows(core, """SELECT b.guid, b.pairing_id FROM core.sync_batches b
                             WHERE b.direction = 'in' AND b.status = 'received'
                               AND NOT EXISTS (SELECT 1 FROM core.sync_batches e WHERE e.pairing_id = b.pairing_id
                                               AND e.direction = 'in' AND e.seq < b.seq AND e.status IN ('waiting', 'committing'))
                             ORDER BY b.pairing_id, b.seq"""):
        out.append(str(r["guid"]))
    return out


def commit(core, pc, ident: Any, by: str, apply=None) -> dict:
    """Site 2: a batch put into this site over what is here (models over themselves by their ids, projects over
    themselves, the organisation's content, DR's users and roles). Each item on its own: one failing does not stop the
    others; the batch says what happened to each."""
    b = _batch(core, ident)
    if b["direction"] != "in" or b["status"] not in ("received", "waiting", "failed"):
        raise EditError(f"This batch is {b['status']}: only one received is committed.", 409)
    if _rows(core, """SELECT 1 AS x FROM core.sync_batches WHERE pairing_id = :p AND direction = 'in'
                                           AND seq < :s AND status IN ('waiting', 'received', 'committing')""",
                                 p=b["pairing_id"], s=b["seq"]):
        raise EditError("An earlier batch of this pairing is not committed yet: commit (or discard) it first, in order.", 409)
    core.execute(text("UPDATE core.sync_batches SET status = 'committing' WHERE id = :id"), {"id": b["_id"]})
    data = (folder() / b["file"]).read_bytes()
    head, z = read_file(data)
    who = SyncUser(f"sync:{b['pairing_name']}")
    notes, failed = [], []
    with z:
        for item in head.get("items") or []:
            try:
                core.execute(text("SAVEPOINT sync_item"))
                pc.execute(text("SAVEPOINT sync_item"))
                said = (apply or apply_item)(core, pc, item, z.read(item["file"]), who)
                core.execute(text("RELEASE SAVEPOINT sync_item"))
                pc.execute(text("RELEASE SAVEPOINT sync_item"))
                notes.append(f"{item.get('name') or item['id']}: {said}")
            except Exception as exc:  # noqa: BLE001 - one item does not stop the others
                core.execute(text("ROLLBACK TO SAVEPOINT sync_item"))
                pc.execute(text("ROLLBACK TO SAVEPOINT sync_item"))
                failed.append(f"{item.get('name') or item['id']}: {str(exc)[:300]}")
    status = "failed" if failed and not notes else "committed"
    core.execute(text("""UPDATE core.sync_batches SET status = :s, committed_at = now(), committed_by = :by, error = :e,
                                notes = CAST(:n AS jsonb) WHERE id = :id"""),
                 {"s": status, "by": by, "e": "; ".join(failed)[:4000], "n": json.dumps(notes + [f"NOT DONE {f}" for f in failed]),
                  "id": b["_id"]})
    return {"status": status, "done": notes, "failed": failed}


def discard(core, user, ident: Any) -> dict:
    """Site 2: a batch waiting for an admin, not taken (the next one of its pairing may then be committed)."""
    _need_super(user)
    b = _batch(core, ident)
    if b["direction"] != "in" or b["status"] not in ("waiting", "received", "failed"):
        raise EditError(f"This batch is {b['status']}: it cannot be discarded.", 409)
    core.execute(text("UPDATE core.sync_batches SET status = 'discarded', committed_at = now(), committed_by = :by WHERE id = :id"),
                 {"by": user.username, "id": b["_id"]})
    return {"status": "discarded"}


def apply_item(core, pc, item: dict, data: bytes, who: SyncUser) -> str:
    """One item put into this site over what is here."""
    import tempfile

    from . import org_backup
    from . import project_backup as pb
    if item["kind"] == "model":
        return _model_in(core, data, item, who)
    if item["kind"] == "project":
        with tempfile.NamedTemporaryFile(suffix=pb.SUFFIX, delete=False) as f:
            f.write(data)
            path = Path(f.name)
        try:
            msg, _out = pb.restore(core, pc, who, path, over=True, models_over=False)
        finally:
            path.unlink(missing_ok=True)
        return msg
    if item["kind"] == "organisation":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            msg, problems = org_backup.restore(z, core, pc, who.username)
        return (msg or "nothing to put back") + (f" (not done: {'; '.join(problems)})" if problems else "")
    if item["kind"] == "users":
        return users_in(json.loads(data))
    raise EditError(f"Unknown item {item['kind']}.")


def _model_in(core, data: bytes, item: dict, who: SyncUser) -> str:
    """A model over itself when it is here (by its id), else made here keeping Site 1's id (so the next sync goes over it)."""
    import tempfile

    from . import backups as bk
    core.execute(text("SELECT set_config('eax.rls_bypass', 'on', true)"))
    here = _rows(core, "SELECT id, is_deleted FROM core.models WHERE guid = CAST(:g AS uuid)", g=item["id"])
    with tempfile.NamedTemporaryFile(suffix=bk.SUFFIX, delete=False) as f:
        f.write(data)
        path = Path(f.name)
    try:
        info, z = bk.read_file(path)
        with z:
            if here:
                if here[0]["is_deleted"]:
                    core.execute(text("UPDATE core.models SET is_deleted = false WHERE id = :id"), {"id": here[0]["id"]})
                msg, _out = bk._restore_over(core, who, info, z, item["id"])
                return msg
            msg, out = bk._restore_new(core, who, info, z, info["model"]["name"])
            core.execute(text("UPDATE core.models SET guid = CAST(:g AS uuid) WHERE guid = CAST(:n AS uuid)"),
                         {"g": item["id"], "n": out["model"]})
            return f"made here as {out['name']} (a draft, with the same id as on the sending site)"
    finally:
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------- DR: the users and their roles
def _kc():
    from .keycloak_upkeep import _kc as kc
    return kc()


def users_out(kc=None) -> dict:
    """Site 1 (DR): the people and their realm roles from Keycloak (never passwords: Keycloak does not give them out)."""
    from .keycloak_upkeep import _users, skipped
    kc = kc or _kc()
    out = []
    for u in _users(kc):
        if skipped(u.get("username") or ""):
            continue
        s, roles, _ = kc._call("GET", f"/users/{u['id']}/role-mappings/realm")
        out.append({"username": u["username"], "email": u.get("email") or "", "firstName": u.get("firstName") or "",
                    "lastName": u.get("lastName") or "", "enabled": bool(u.get("enabled", True)),
                    "roles": sorted(r["name"] for r in roles or [] if s == 200 and not r["name"].startswith("default-roles-"))})
    return {"users": out}


def users_in(data: dict, kc=None) -> str:
    """Site 2 (DR): each person made or changed to match Site 1, their realm roles set to Site 1's; anyone Site 1 no
    longer has is disabled here (never deleted). Passwords stay as they are here."""
    from .keycloak_upkeep import _users, skipped
    kc = kc or _kc()
    s, realm_roles, _ = kc._call("GET", "/roles")
    known = {r["name"]: r for r in realm_roles or []} if s == 200 else {}
    here = {u["username"]: u for u in _users(kc)}
    made = changed = disabled = 0
    theirs = set()
    for u in data.get("users") or []:
        name = u["username"]
        theirs.add(name)
        body = {k: u[k] for k in ("email", "firstName", "lastName", "enabled")}
        if name in here:
            uid = here[name]["id"]
            kc._call("PUT", f"/users/{uid}", body)
            changed += 1
        else:
            st, _b, h = kc._call("POST", "/users", {"username": name, **body})
            if st not in (201, 204):
                continue
            uid = (h.get("Location") or h.get("location") or "").rstrip("/").split("/")[-1]
            made += 1
        st, cur, _ = kc._call("GET", f"/users/{uid}/role-mappings/realm")
        have = {r["name"] for r in cur or []} if st == 200 else set()
        want = {r for r in u.get("roles") or [] if r in known}
        add = [known[r] for r in want - have]
        drop = [known[r] for r in have - want if r in known and not r.startswith("default-roles-")]
        if add:
            kc._call("POST", f"/users/{uid}/role-mappings/realm", add)
        if drop:
            kc._call("DELETE", f"/users/{uid}/role-mappings/realm", drop)
    for name, u in here.items():
        if name not in theirs and not skipped(name) and u.get("enabled", True):
            kc._call("PUT", f"/users/{u['id']}", {"enabled": False})
            disabled += 1
    return f"{made} people made, {changed} brought in line, {disabled} no longer on the sending site disabled"


# ---------------------------------------------------------------- eax sync (on the machine)
def main(argv: list[str]) -> int:
    """python -m eax.pairing list | send <pairing> | commit <batch> | status: for eax sync (and Jenkins)."""
    from .db import get_engine, get_projects_engine
    action = argv[0] if argv else "list"
    try:
        if action == "list":
            with get_engine().begin() as core:
                out = listing(core)
            for p in out["pairings"]:
                print(f"  {p['side']:<8} {p['name']:<30} {p['kind']:<7} {p['status']:<9} {p['peer_name'] or p['peer_url']}  "
                      f"last {p['lag']}  {p['batches']}")
            print(f"This site: {out['purpose']}" + (f", a DR copy of {out['dr_copy']['from']} (read only)" if out["dr_copy"] else ""))
            return 0
        if action == "send" and len(argv) > 1:
            with get_engine().begin() as core, get_projects_engine().begin() as pc:
                ident = argv[1] if re.fullmatch(r"[0-9a-f-]{36}", argv[1]) else _by_name(core, argv[1])
                print(enqueue(core, pc, ident, "eax")["say"])
            with get_engine().begin() as core:
                for line in send_queued(core):
                    print(f"  {line}")
            return 0
        if action == "status":
            with get_engine().begin() as core:
                for line in check_peers(core):
                    print(f"  {line}")
                for p in listing(core)["pairings"]:
                    print(f"  {p['name']}: {p['status']}, last {p['lag']}{', ' + p['last_error'] if p['last_error'] else ''}")
            return 0
    except EditError as exc:
        print(f"EA Explorer: {exc}")
        return 1
    print("python -m eax.pairing list | send <pairing name or id> | status")
    return 2


def _by_name(core, name: str) -> str:
    r = _rows(core, "SELECT guid FROM core.site_pairings WHERE side = 'sender' AND lower(name) = lower(:n)", n=name)
    if not r:
        raise EditError(f"No sending pairing called {name}.", 404)
    return str(r[0]["guid"])


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
