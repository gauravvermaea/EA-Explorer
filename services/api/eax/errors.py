"""Error codes (Release 7.9, D787): one list, eax/errors.json, read by the API's answers, the logs, System Admin's health
and alerts, `eax status` and the error guide. A code is EAX-AREA-NNN and never changes meaning; each has what it means,
its usual cause and what to do."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LIST = Path(__file__).with_name("errors.json")


@lru_cache(maxsize=1)
def all_errors() -> list[dict]:
    """Every error code, in the list's order."""
    return json.loads(LIST.read_text(encoding="utf-8"))["errors"]


@lru_cache(maxsize=1)
def _by_code() -> dict[str, dict]:
    return {e["code"]: e for e in all_errors()}


def get(code: str) -> dict | None:
    """One error code's entry, or None."""
    return _by_code().get(code)


def to_do(code: str) -> str:
    """What to do about a code ("" for an unknown one)."""
    return (get(code) or {}).get("to_do", "")


def for_status(status: int) -> str:
    """The code of an API answer by its HTTP status: its own when listed, else the nearest (any other 5xx is a server
    error, any other 4xx a request not valid)."""
    for e in all_errors():
        if e.get("http") == status and e["code"].startswith("EAX-API-") and int(e["code"][-3:]) == status:
            return e["code"]
    return "EAX-API-500" if status >= 500 else "EAX-API-400"


def for_health(service: dict) -> str:
    """The code of a health check that is not up ("" when it is up or off): by its name, its status and, where one
    check has several warnings, the words of its detail."""
    status = service.get("status")
    if status not in ("down", "warning"):
        return ""
    name, detail = service.get("name"), (service.get("detail") or "").lower()
    found = [e for e in all_errors() if e.get("health") == name and e.get("health_status") == status]
    for e in found:
        if e.get("health_detail") and e["health_detail"] in detail:
            return e["code"]
    plain = [e for e in found if not e.get("health_detail")]
    if plain:
        return plain[0]["code"]
    if found:
        return found[0]["code"]
    down = [e for e in all_errors() if e.get("health") == name and e.get("health_status") == "down"]
    return down[0]["code"] if down else "EAX-API-503"


def for_alert(key: str, message: str = "", state: str = "") -> str:
    """The code of an alert check: a service's is its health code (WARNING as a warning, else as down), a custom check's
    EAX-ALRT-001."""
    if key.startswith("service:") and key != "service:health":
        status = "warning" if state == "WARNING" else "down"
        return for_health({"name": key.split(":", 1)[1], "status": status, "detail": message})
    if key.startswith("custom:"):
        return "EAX-ALRT-001"
    for e in all_errors():
        if e.get("alert") == key:
            return e["code"]
    return ""


def for_container(service: str, state: str) -> str:
    """The code of a container that is not running well, for `eax status`: its part's own code when it has one."""
    if "unhealthy" in state:
        return "EAX-STACK-002"
    for e in all_errors():
        if e.get("stack") == service:
            return e["code"]
    return "EAX-STACK-001"


def stamp(item: dict, code: str) -> dict:
    """An answer, a health check or an alert with its code and what to do added."""
    if code:
        item["error_code"] = code
        item["to_do"] = to_do(code)
    return item


def problems(health: dict | None = None, alert_rows: list[dict] | None = None) -> list[dict]:
    """Every problem now, each with its code, what it is, the detail and what to do: health checks not up and alerts
    open (WARNING or CRITICAL), without the same code twice. For `eax status` (python -m eax.errors)."""
    out: dict[str, dict] = {}
    for s in (health or {}).get("services", []):
        code = s.get("error_code") or for_health(s)
        if code and code not in out:
            out[code] = {"code": code, "level": "critical" if s["status"] == "down" else "warning", "what": s["name"],
                         "detail": s.get("detail") or "", "to_do": to_do(code)}
    for r in alert_rows or []:
        if r.get("state") not in ("WARNING", "CRITICAL"):
            continue
        code = for_alert(r.get("check_key") or "", r.get("message") or "", r.get("state") or "")
        if code and code not in out:
            out[code] = {"code": code, "level": r["state"].lower(), "what": r.get("what") or r.get("check_key"),
                         "detail": r.get("message") or "", "to_do": to_do(code)}
    return sorted(out.values(), key=lambda p: (p["level"] != "critical", p["code"]))


def main() -> None:
    """python -m eax.errors: the problems now as JSON lines, for `eax status` (inside the api container)."""
    from . import health
    h = health.check_all()
    rows: list[dict] = []
    try:
        from sqlalchemy import text

        from .db import get_engine
        with get_engine().connect() as conn:
            rows = [dict(r) for r in conn.execute(text("SELECT check_key, what, state, message FROM core.alert_checks")).mappings()]
    except Exception:  # noqa: BLE001 - no database: the health checks say so
        rows = []
    print(json.dumps({"status": h["status"], "problems": problems(h, rows)}))


if __name__ == "__main__":
    main()
