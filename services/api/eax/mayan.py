"""Mayan EDMS, the document store behind the project repositories (phase 13, D260).

EA Explorer keeps the rules and the screens; Mayan keeps the files: each project is a cabinet with a cabinet per folder,
each document a Mayan document with its versions (files), and a check-out in EA Explorer is also a check-out in Mayan.
EA Explorer talks to Mayan's REST API (v4) inside the Docker network (http://dms:8000) as one service account, Mayan's
own administrator (EAX_MAYAN_ADMIN_USER), with an API token; the person who acted is kept by EA Explorer
(proj.document_events) and written into Mayan's comments. Project roles are not copied into Mayan.

The token: Mayan signs people in through Keycloak, so its administrator has no password sign-in for the API; EA Explorer
reads (or makes) the administrator's API token in Mayan's own database (`mayan`, Mayan's login, EAX_MAYAN_DB_PASSWORD),
once, and keeps it in memory.

Every call raises MayanError with a plain message when Mayan is off, still starting or refuses: the caller shows it and
the repository is built when Mayan is up (the repository job retries).
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .config import get_settings

BASE = os.environ.get("EAX_MAYAN_URL", "http://dms:8000").rstrip("/")
API = BASE + "/api/v4"
TIMEOUT = 60
PAGE = 100             # results per page when listing
_lock = threading.Lock()
_token: dict = {"key": None}


class MayanError(Exception):
    """Documents (Mayan EDMS) refused or could not be reached, with the HTTP status to answer."""
    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def enabled() -> bool:
    """Whether Documents is switched on."""
    from . import services
    return services.enabled("documents")


def _db_token() -> str:
    """The administrator's API token, read or made in Mayan's database."""
    import psycopg
    s = get_settings()
    user = os.environ.get("EAX_MAYAN_ADMIN_USER", "admin")
    pw = os.environ.get("EAX_MAYAN_DB_PASSWORD", "")
    info = (f"host={s.db_host} port={s.db_port} dbname={os.environ.get('EAX_MAYAN_DB_NAME', 'mayan')} "
            f"user={os.environ.get('EAX_MAYAN_DB_USER', 'mayan')} password='{pw.replace(chr(92), chr(92) * 2).replace(chr(39), chr(92) + chr(39))}' "
            "connect_timeout=5")
    try:
        with psycopg.connect(info, autocommit=True) as conn:
            row = conn.execute("SELECT id FROM auth_user WHERE username = %s", (user,)).fetchone()
            if not row:
                raise MayanError(f"Mayan has no administrator '{user}' yet: it is still setting itself up.")
            tok = conn.execute("SELECT key FROM authtoken_token WHERE user_id = %s", (row[0],)).fetchone()
            if tok:
                return tok[0]
            key = secrets.token_hex(20)
            conn.execute("INSERT INTO authtoken_token (key, created, user_id) VALUES (%s, now(), %s)", (key, row[0]))
            return key
    except MayanError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MayanError(f"Documents (Mayan) cannot be reached yet: {str(exc).splitlines()[0][:200]}") from exc


def _key() -> str:
    with _lock:
        if not _token["key"]:
            _token["key"] = _db_token()
        return _token["key"]


def _request(method: str, path: str, *, data: bytes | None = None, ctype: str | None = None, raw: bool = False,
             timeout: int = TIMEOUT):
    if not enabled():
        raise MayanError("Documents (Mayan) are switched off (Administration > System settings > Services).", 409)
    url = path if path.startswith("http") else API + path
    headers = {"Authorization": f"Token {_key()}", "Accept": "application/json"}
    if ctype:
        headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if raw:
                return body, r.headers.get("Content-Type", "application/octet-stream")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        text = exc.read()[:500].decode(errors="replace")
        if exc.code == 401:
            _token["key"] = None   # read the token again next time
        err = MayanError(f"Mayan refused {method} {path.split('?')[0]}: HTTP {exc.code} {text}", 502)
        err.http = exc.code          # 404: the document is gone
        raise err from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise MayanError(f"Documents (Mayan) cannot be reached: {exc}") from exc


def _json(method: str, path: str, body: dict | None = None):
    return _request(method, path, data=json.dumps(body or {}).encode() if body is not None else None,
                    ctype="application/json" if body is not None else None)


def _multipart(fields: dict, file_name: str, content: bytes, ctype: str = "application/octet-stream",
               file_field: str = "file") -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    safe = file_name.replace('"', "'")
    out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{safe}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n").encode() + content + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def ping() -> bool:
    """Whether Documents answers."""
    return not why_not_up()


def why_not_up() -> str:
    """Why Documents does not answer ("" when it does): shown on the start-up status, so a fault (a refused sign-in to
    its database, say) is seen at once and not taken for a slow start (D893)."""
    try:
        _json("GET", "/document_types/?page_size=1")
        return ""
    except MayanError as exc:
        return str(exc) or "it does not answer"


# ---------------------------------------------------------------- cabinets (folders)
_cabinets: dict[tuple, int] = {}      # (parent, label) -> id, for this process


def _top_cabinets() -> list[dict]:
    """Every cabinet at the top (no parent), page by page: Mayan's cabinet list does not filter by label."""
    out, page = [], f"/cabinets/?page_size={PAGE}"
    while page:
        body = _json("GET", page)
        out += [c for c in body.get("results", []) if c.get("parent_id") is None and not isinstance(c.get("parent"), int)]
        page = body.get("next")
    return out


def cabinet(label: str, parent: int | None = None) -> int:
    """The cabinet with this label under `parent` (made when missing); returns its id. A cabinet's children come with it
    (GET /cabinets/<id>/), so the one wanted is found however many cabinets there are."""
    label = label[:128]
    key = (parent, label)
    if key in _cabinets:
        return _cabinets[key]
    found = _top_cabinets() if parent is None else (_json("GET", f"/cabinets/{parent}/").get("children") or [])
    for c in found:
        _cabinets[(parent, c.get("label"))] = c["id"]
    if key in _cabinets:
        return _cabinets[key]
    # Mayan asks for "parent" on every cabinet: null for a cabinet at the top (it answered HTTP 400 "parent: This field
    # is required" when it was left out, owner's laptop, 7 Nov 2026)
    body = {"label": label, "parent": parent or None}
    cid = _json("POST", "/cabinets/", body)["id"]
    _cabinets[key] = cid
    return cid


def rename_cabinet(cabinet_id: int, label: str) -> None:
    """A cabinet's label changed (an item brought back into use loses its "(not_for_use)" suffix, and the other way)."""
    _json("PATCH", f"/cabinets/{cabinet_id}/", {"label": label[:128]})
    for k, v in list(_cabinets.items()):
        if v == cabinet_id:
            del _cabinets[k]


def cabinet_path(path: str, root: int) -> int:
    """Cabinets for every part of a folder path under the project's cabinet; returns the last one's id."""
    cid = root
    for part in [p for p in path.split("/") if p]:
        cid = cabinet(part, cid)
    return cid


def add_to_cabinet(cabinet_id: int, document_id: int) -> None:
    """Puts a document in a cabinet (a project's folder in Documents)."""
    _json("POST", f"/cabinets/{cabinet_id}/documents/add/", {"document": document_id})


# ---------------------------------------------------------------- documents and versions
_doc_type: dict = {"id": None}


def document_type() -> int:
    """The document type EA Explorer files under: 'EA Explorer project document' (made when missing)."""
    if _doc_type["id"]:
        return _doc_type["id"]
    label = "EA Explorer project document"
    for t in _json("GET", "/document_types/?page_size=200").get("results", []):
        if t.get("label") == label:
            _doc_type["id"] = t["id"]
            return t["id"]
    _doc_type["id"] = _json("POST", "/document_types/", {"label": label})["id"]
    return _doc_type["id"]


def upload(file_name: str, content: bytes, ctype: str = "application/octet-stream", label: str | None = None) -> dict:
    """A new document; returns {id, file_id}. Mayan stores the file in the background (a task), so file_id is often
    None at first: the latest file is read when it is downloaded."""
    body, ct = _multipart({"document_type_id": document_type(), "label": label or file_name}, file_name, content, ctype)
    doc = _request("POST", "/documents/upload/", data=body, ctype=ct, timeout=300)
    return {"id": doc.get("id"), "file_id": (doc.get("file_latest") or {}).get("id")}


def new_version(document_id: int, file_name: str, content: bytes, comment: str, ctype: str = "application/octet-stream") -> None:
    """A new file (version) of a document; the latest is the current one. Mayan 4: POST /documents/<id>/files/ with
    the file as `file_new` and `action` 1 (replace: a new version made of the new file's pages)."""
    # Mayan 4 asks for action_name ('replace'); older 4.x took the number: both are sent
    body, ct = _multipart({"action": 1, "action_name": "replace", "comment": comment[:250]}, file_name, content, ctype, file_field="file_new")
    _request("POST", f"/documents/{document_id}/files/", data=body, ctype=ct, timeout=300)


def latest(document_id: int) -> dict:
    """A document's newest file: its id, name and label."""
    d = _json("GET", f"/documents/{document_id}/")
    f = d.get("file_latest") or {}
    return {"file_id": f.get("id"), "file_name": f.get("filename") or d.get("label"), "label": d.get("label"),
            "checksum": f.get("checksum")}


def trash(document_id: int) -> None:
    """To Mayan's trash (DELETE /documents/<id>/): a document uploaded by work that then failed."""
    _request("DELETE", f"/documents/{document_id}/")


def download(document_id: int) -> tuple[bytes, str, str]:
    """The latest version's bytes, content type and file name."""
    f = latest(document_id)
    if not f["file_id"]:
        raise MayanError("Documents is still storing this file (it does so in the background): try again in a moment.", 409)
    content, ctype = _request("GET", f"/documents/{document_id}/files/{f['file_id']}/download/", raw=True, timeout=300)
    return content, ctype, f["file_name"] or "document"


def files(document_id: int) -> list[dict]:
    """Every file (version) of a document, oldest first: [{id, filename, timestamp}] (Mayan 4: /documents/<id>/files/)."""
    out, page = [], f"/documents/{document_id}/files/?page_size={PAGE}"
    while page:
        body = _json("GET", page)
        out += body.get("results", [])
        page = body.get("next")
    return sorted(out, key=lambda f: (f.get("timestamp") or "", f.get("id") or 0))


def download_version(document_id: int, version: int) -> tuple[bytes, str, str]:
    """The bytes, content type and file name of one version (1 = the first file)."""
    fs = files(document_id)
    if not 1 <= version <= len(fs):
        raise MayanError(f"Documents has {len(fs)} version(s) of this document, not {version}.", 404)
    f = fs[version - 1]
    content, ctype = _request("GET", f"/documents/{document_id}/files/{f['id']}/download/", raw=True, timeout=300)
    return content, ctype, f.get("filename") or "document"


def check_out(document_id: int, hours: int = 24 * 30) -> None:
    """Mayan 4: POST /checkouts/ with the document's id (document_pk); /documents/<id>/checkout/ only reads (GET) and
    checks in (DELETE)."""
    from datetime import UTC, datetime, timedelta
    until = (datetime.now(UTC) + timedelta(hours=hours)).isoformat()
    _json("POST", "/checkouts/", {"document_pk": document_id, "expiration_datetime": until, "block_new_file": True})


def check_in(document_id: int) -> None:
    """Checks a document back in (nothing when it was not checked out)."""
    try:
        _request("DELETE", f"/documents/{document_id}/checkout/")
    except MayanError as exc:
        if exc.status != 502 or "404" not in str(exc):
            raise


def tag(document_id: int, label: str, color: str = "#999999") -> None:
    """Tags a document, making the tag when it is not there."""
    tid = None
    page, found = f"/tags/?page_size={PAGE}", []          # Mayan's tag list does not filter by label: page through it
    while page:
        body = _json("GET", page)
        found += body.get("results", [])
        page = body.get("next")
    for t in found:
        if t.get("label") == label:
            tid = t["id"]
    if not tid:
        tid = _json("POST", "/tags/", {"label": label, "color": color})["id"]
    _json("POST", f"/documents/{document_id}/tags/attach/", {"tag": tid})


def web_link(document_id: int) -> str:
    """Where the document is in Mayan's own screens (docs.<host>)."""
    s = get_settings()
    port = "" if str(s.https_port) == "443" else f":{s.https_port}"
    return f"https://docs.{s.hostname}{port}/#/documents/documents/{document_id}/preview/"


# ---------------------------------------------------------------- OCR (D903)
# Documents reads every page of a new document as a picture (OCR) unless its document type says not to. After a clean
# restart that is the 97 pack files, thousands of pages, an hour or more on a laptop, though their text is extracted
# anyway (owner, 23 Nov 2026, 22:45: "In the whole thing can OCR be turned off by default. We should be able to turn it
# on in a setting in admin"; 22:48: "Make this turning on OCR part of the initial setup on start page"). The setting
# documents_ocr (off unless chosen) is applied to every document type at start-up, before the packs load, and at once
# when it is changed; switching it on also asks Documents to read the documents already there (owner: "Existing ones
# too"); switching it off clears the OCR jobs waiting. Text extraction (search) is never switched off.
OCR_SETTINGS_PATHS = ("/document_types/{id}/ocr/settings/", "/document_types/{id}/ocr_settings/")
OCR_SUBMIT_PATHS = ("/documents/{id}/ocr/submit/", "/documents/{id}/submit_ocr/")


def _first_path(method: str, paths: tuple[str, ...], ident: int, body: dict | None = None):
    """The call on the first of Documents' paths that exists (they differ between its versions); 404 tries the next."""
    last: MayanError | None = None
    for p in paths:
        try:
            return _json(method, p.format(id=ident), body)
        except MayanError as exc:
            if getattr(exc, "http", None) not in (404, 405):
                raise
            last = exc
    raise MayanError(f"Documents has none of {', '.join(p.format(id=ident) for p in paths)} ({last})", 502)


def document_types() -> list[dict]:
    """Every document type in Documents."""
    return _json("GET", f"/document_types/?page_size={PAGE * 2}").get("results", [])


def set_auto_ocr(on: bool) -> int:
    """Automatic OCR on or off for every document type; returns how many types were set."""
    types = document_types()
    for t in types:
        _first_path("PATCH", OCR_SETTINGS_PATHS, t["id"], {"auto_ocr": bool(on)})
    return len(types)


def ocr_existing(limit: int | None = None) -> int:
    """Asks Documents to read every document already there (switching OCR on); returns how many were asked."""
    asked, page = 0, 1
    while True:
        r = _json("GET", f"/documents/?page_size={PAGE}&page={page}")
        for d in r.get("results", []):
            _first_path("POST", OCR_SUBMIT_PATHS, d["id"], {})
            asked += 1
            if limit is not None and asked >= limit:
                return asked
        if not r.get("next"):
            return asked
        page += 1


def _broker(*commands: tuple[str, ...]) -> list:
    """Commands to Documents' broker (Valkey, the Redis protocol) in one connection; their replies, in order."""
    import socket
    password = os.environ.get("EAX_DMS_BROKER_PASSWORD", "").strip().strip("'\"")
    host = os.environ.get("EAX_DMS_BROKER_HOST", "dms-broker")
    port = int(os.environ.get("EAX_DMS_BROKER_PORT", "6379"))
    with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
        f = sock.makefile("rb")

        def send(*parts: str):
            sock.sendall((f"*{len(parts)}\r\n" + "".join(f"${len(p.encode('latin-1'))}\r\n{p}\r\n" for p in parts)).encode("latin-1"))
            return _reply(f)
        if password:
            if send("AUTH", password) != "OK":
                raise MayanError("Documents' broker refused the password", 502)
        return [send(*c) for c in commands]


def _reply(f):
    """One reply of the Redis protocol: a string, a number, None or a list."""
    line = f.readline().rstrip(b"\r\n")
    kind, rest = line[:1], line[1:].decode("latin-1")
    if kind == b"+":
        return rest
    if kind == b"-":
        raise MayanError(f"Documents' broker: {rest}", 502)
    if kind == b":":
        return int(rest)
    if kind == b"$":
        n = int(rest)
        return None if n < 0 else f.read(n + 2)[:-2].decode("latin-1")
    if kind == b"*":
        n = int(rest)
        return None if n < 0 else [_reply(f) for _ in range(n)]
    raise MayanError(f"Documents' broker answered {line[:40]!r}", 502)


def ocr_queue(clear: bool = False) -> int:
    """The OCR jobs waiting in Documents' broker (its ocr queues, database 0), deleted with clear; returns how many were
    waiting. Only those: never its results (database 1) or locks (database 2)."""
    keys, cursor = [], "0"
    while True:
        cursor, found = _broker(("SELECT", "0"), ("SCAN", cursor, "MATCH", "ocr*", "COUNT", "1000"))[1]
        keys += found
        if cursor == "0":
            break
    if not keys:
        return 0
    lengths = _broker(("SELECT", "0"), *[("LLEN", k) for k in keys])[1:]
    if clear:
        _broker(("SELECT", "0"), ("DEL", *keys))
    return sum(int(n or 0) for n in lengths)


def apply_ocr(on: bool, existing: bool = False) -> str:
    """The setting applied: every type's automatic OCR, then (on) the documents already there asked to be read, or
    (off) the OCR jobs waiting cleared. Returns what was done, in words."""
    types = set_auto_ocr(on)
    if on:
        n = ocr_existing() if existing else 0
        return f"OCR on for {types} document type(s)" + (f"; {n} document(s) already there asked to be read" if existing else "")
    cleared = ocr_queue(clear=True)
    return f"OCR off for {types} document type(s); {cleared} OCR job(s) waiting cleared"
