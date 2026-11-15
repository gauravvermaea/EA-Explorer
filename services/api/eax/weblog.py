"""Web log debug (R5.6; owner, 14 Nov 2026: "Web log debug (off by default) - will also show input and output").

The web log itself is written by the front door (nginx, one JSON line per call to the API and MCP: logs/web/<day>.log).
With web log debug on, switched on for a while by a Super Admin on System Admin > Logs (the setting web_log_debug_until,
audited) and said on that page while on, the API also writes each call's input and answer to logs/web/debug-<day>.log
(mounted at /eax-web): cut to 4 KB each, every password, secret, token, key, cookie and personal field (e-mail
addresses, phone numbers) masked. Off by default; it goes off by itself when its time ends.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

FOLDER = Path(os.environ.get("EAX_WEB_LOG_MOUNT", "/eax-web"))
CUT = 4096
_SECRET_KEYS = re.compile(r"(password|secret|token|_key$|^key$|apikey|api_key|authorization|cookie|private|passphrase|"
                          r"email|e-mail|phone|mobile)", re.I)
_TEXT = [(re.compile(r'("(?:password|secret|token|api_key|apikey|authorization|cookie|private_key)"\s*:\s*")[^"]*"', re.I), r'\1****"'),
         (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1****"),
         (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "****@****"),
         (re.compile(r"\+?\d[\d ()-]{8,}\d"), "****")]
_cache = {"at": 0.0, "until": ""}


def mask(value):
    """A request's or answer's body with every secret and personal field masked."""
    if isinstance(value, dict):
        return {k: ("****" if isinstance(k, str) and _SECRET_KEYS.search(k) and value[k] not in (None, "") else mask(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    if isinstance(value, str):
        for rx, rep in _TEXT:
            value = rx.sub(rep, value)
        return value
    return value


def _body(raw: bytes, content_type: str):
    if not raw:
        return None
    if "json" in (content_type or ""):
        try:
            return mask(json.loads(raw))
        except ValueError:
            pass
    if "multipart" in (content_type or "") or "octet-stream" in (content_type or ""):
        return f"({len(raw)} bytes, not shown)"
    return mask(raw[:CUT].decode("utf-8", errors="replace"))


def until() -> str:
    """When web log debug ends (an ISO time, UTC), or "" when it is off; read from the settings every 30 seconds."""
    if time.monotonic() - _cache["at"] > 30:
        try:
            from . import settings as st
            _cache["until"] = str(st.values().get("web_log_debug_until") or "")
        except Exception:  # noqa: BLE001 - no database: off
            _cache["until"] = ""
        _cache["at"] = time.monotonic()
    return _cache["until"]


def on(now: datetime | None = None) -> bool:
    """Whether the web log's debug lines are on now (until the time set)."""
    u = until()
    if not u:
        return False
    try:
        return (now or datetime.now(UTC)) < datetime.fromisoformat(u.replace("Z", "+00:00"))
    except ValueError:
        return False


def forget() -> None:
    """Forgets the cached setting (read again)."""
    _cache["at"] = 0.0


def line(method: str, path: str, status: int, who: str, request_id: str, req_body, resp_body, now: datetime | None = None) -> str:
    """One debug line of the web log: the call, who, and the bodies cut short."""
    def cut(v):
        text = json.dumps(v, ensure_ascii=False, default=str)
        return v if len(text) <= CUT else text[:CUT] + "…"
    now = now or datetime.now(UTC)
    return json.dumps({"time": now.isoformat(timespec="milliseconds"), "who": who, "method": method, "path": path,
                       "status": status, "request_id": request_id, "input": cut(req_body), "answer": cut(resp_body)},
                      ensure_ascii=False, default=str)


def debug_line(request, response, request_id: str, who: str) -> None:
    """One debug line for this call, when web log debug is on."""
    if not on() or not FOLDER.is_dir():
        return
    if request.path.startswith("/api/health") or request.path.endswith("/metrics"):
        return
    req = _body(request.get_data(cache=True) or b"", request.content_type or "")
    resp = None
    if not response.direct_passthrough and response.mimetype in ("application/json", "text/plain"):
        resp = _body(response.get_data()[: 256 * 1024], response.mimetype)
    now = datetime.now(UTC)
    with open(FOLDER / f"debug-{now:%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(line(request.method, request.path, response.status_code, who, request_id, req, resp, now) + "\n")
