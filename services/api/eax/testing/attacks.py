"""The attacks Release 3 was reviewed against, kept as black-box tests (R5.17 (4)); run by the security suite through the
API, as the run's own test users, in the run's own test data. Each is an attack that must be refused; nothing real can
change even when one is not (anything a check makes is deleted at once and the check fails):

  SSRF            a discovery source pointed at the cloud's metadata address, at one of EA Explorer's own containers
                  and at the machine itself: refused when saved (D671)
  secret ref      a discovery source told to sign in with a setting that is not one made for sources (the database's
                  password): refused (D671)
  settings leak   the settings every screen reads hold no password, secret or token, and nothing answers unsigned
  cross-model     a test user reads and writes a model they have no role on: refused, never someone else's data
  cross-project   the same for a project
  identity        a header that claims to be another person (the front door's own, X-EAX-Actor, or a forwarded user)
                  changes nothing: an Architect stays an Architect
  uploads         a file that is not a backup, one named to climb out of its folder, one far too big: refused

One result each ("attack: ..."), in the suite "security"; the gate (security_gate.py) counts them with the scanners.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable

from .negative import send

REFUSED = {400, 401, 403, 404, 405, 409, 413, 415, 422}
SECRETISH = re.compile(r"(password|secret|token|private|passphrase|api_?key)", re.I)


def _created(text: str) -> str:
    try:
        got = json.loads(text or "{}")
    except ValueError:
        return ""
    return str(got.get("id") or got.get("guid") or "")


def ssrf(base: str, token: str, model: str, record: Callable) -> None:
    """SSRF: discovery sources at the metadata address, a container, the machine and a private network must be refused
    when saved."""
    for name, url in (("the cloud's metadata address", "http://169.254.169.254/latest/meta-data/"),
                      ("one of its own containers", "http://db:5432/"),
                      ("the machine itself", "http://127.0.0.1:8000/api/v1/"),
                      ("a private network", "http://10.0.0.1/odata/")):
        t0 = time.time()
        body = {"name": f"self-test attack {uuid.uuid4().hex[:6]}", "kind": "odata", "url": url}
        s, text = send(base, "POST", f"/api/v1/models/{model}/discovery-sources", token, json.dumps(body).encode())
        made = _created(text) if s < 300 else ""
        if made:
            send(base, "DELETE", f"/api/v1/discovery-sources/{made}", token, None)
        ok = s in REFUSED
        record(f"attack: SSRF: a discovery source at {name}", "passed" if ok else "failed",
               f"answered {s}" + ("" if ok else f" (it was saved{', then deleted' if made else ''}): {text[:200]}"),
               int((time.time() - t0) * 1000))


def secret_ref(base: str, token: str, model: str, record: Callable) -> None:
    """A discovery source signing in with the database's password must be refused."""
    t0 = time.time()
    body = {"name": f"self-test attack {uuid.uuid4().hex[:6]}", "kind": "push", "auth_ref": "EAX_DB_PASSWORD"}
    s, text = send(base, "POST", f"/api/v1/models/{model}/discovery-sources", token, json.dumps(body).encode())
    made = _created(text) if s < 300 else ""
    if made:
        send(base, "DELETE", f"/api/v1/discovery-sources/{made}", token, None)
    record("attack: a discovery source signing in with the database's password", "passed" if s in REFUSED else "failed",
           f"answered {s}", int((time.time() - t0) * 1000))


def leaks(base: str, token: str, record: Callable) -> None:
    """The screens' settings hold no secret, and nothing answers without signing in."""
    t0 = time.time()
    s, text = send(base, "GET", "/api/v1/settings", token, None, limit=None)
    bad = []
    try:
        for k, v in (json.loads(text) if s == 200 else {}).items():
            if SECRETISH.search(k) and v not in ("", None, False, 0, [], {}):
                bad.append(k)
    except ValueError:
        pass
    record("attack: the screens' settings hold no password, secret or token", "passed" if s == 200 and not bad else "failed",
           f"answered {s}" + (f"; holds {', '.join(bad)}" if bad else ""), int((time.time() - t0) * 1000))
    for path in ("/api/v1/settings", "/api/v1/me", "/api/v1/models"):
        s, _ = send(base, "GET", path, "", None)
        record(f"attack: unsigned: GET {path}", "passed" if s in (401, 403) else "failed", f"answered {s}", 0)


def cross(base: str, token: str, ids: dict[str, str], record: Callable) -> None:
    """A test user reading or writing a model or project with no role there is refused."""
    other = ids.get("other_model")
    if other:
        for method, path, body in (("GET", f"/api/v1/models/{other}/entities", None),
                                   ("POST", f"/api/v1/models/{other}/entities", {"name": "self-test attack", "type": "x"})):
            s, text = send(base, method, path, token, json.dumps(body).encode() if body else None)
            ok = s in (403, 404)
            record(f"attack: cross-model: {method} on a model with no role", "passed" if ok else "failed",
                   f"answered {s}" + ("" if ok else f": {text[:200]}"), 0)
    else:
        record("attack: cross-model", "skipped", "the run has no second test model", 0)
    proj = ids.get("other_project")
    if proj:
        s, _ = send(base, "GET", f"/api/v1/projects/{proj}", token, None)
        record("attack: cross-project: a project with no role", "passed" if s in (403, 404) else "failed", f"answered {s}", 0)
    else:
        s, _ = send(base, "GET", f"/api/v1/projects/{uuid.uuid4()}", token, None)
        record("attack: cross-project: a project that is not theirs", "passed" if s in (403, 404) else "failed", f"answered {s}", 0)


def identity(base: str, token: str, record: Callable) -> None:
    """A header claiming to be someone else changes nothing."""
    from ..service_split import route
    for header in ("X-EAX-Actor", "X-Forwarded-User", "X-Remote-User"):
        req = urllib.request.Request(route(base, "/api/v1/admin/databases") + "/api/v1/admin/databases", method="GET",
                                     headers={"Authorization": f"Bearer {token}", header: "eaadmin", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                s = r.status
        except urllib.error.HTTPError as exc:
            s = exc.code
        except (urllib.error.URLError, OSError):
            s = 599
        record(f"attack: {header} claiming another person changes nothing", "passed" if s in (401, 403) else "failed",
               f"answered {s}", 0)


def uploads(base: str, admin: str, record: Callable) -> None:
    """Multipart uploads to the backups' upload (the one upload that takes any file name): each must be refused."""
    from ..service_split import route
    url = route(base, "/api/v1/admin/backups/upload") + "/api/v1/admin/backups/upload"
    for name, filename, size in (("not a backup", "notes.exe", 1024), ("a name that climbs out of its folder",
                                 "../../../etc/cron.d/x.eaxbackup.zip", 1024), ("not a zip", "model.eaxbackup.zip", 2048)):
        boundary = uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n").encode() + b"x" * size + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Authorization": f"Bearer {admin}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                s, text = r.status, r.read(400).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            s, text = exc.code, ""
        except (urllib.error.URLError, OSError) as exc:
            s, text = 599, str(exc)
        record(f"attack: upload: {name}", "passed" if s in REFUSED else "failed", f"answered {s}" + ("" if s in REFUSED else f": {text}"), 0)


def run(base: str, tokens: dict[str, str], ids: dict[str, str], record: Callable) -> None:
    """Every attack, as the run's test users in its own test data."""
    architect = tokens.get("architect") or next(iter(tokens.values()), "")
    model = ids.get("model", "")
    if model and architect:
        ssrf(base, architect, model, record)
        secret_ref(base, architect, model, record)
    else:
        record("attack: SSRF", "skipped", "no test model or architect", 0)
    reader = tokens.get("report-viewer") or architect
    if reader:
        leaks(base, reader, record)
        cross(base, architect, ids, record)
        identity(base, architect, record)
    if tokens.get("super-admin"):
        uploads(base, tokens["super-admin"], record)
