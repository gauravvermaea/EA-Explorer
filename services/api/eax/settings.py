"""Phase 10 (D156, D182, D183): the settings of the administration console.

Two kinds:
  * runtime settings, in core.settings: changed on screen by a Super Admin and applied at once. The application
    settings every screen, report and export follow (base currency and symbol, country, time zone, date and number
    formats, first day of the week, the month the financial year starts) and the runtime system settings (largest
    upload, how long change log entries are kept, session time-outs, applied to Keycloak)
  * start-up settings: the config file (work/eaexplorer.env) the containers start with. Shown in the console with
    in clear text (IT and Super Admins); edited through the config file (D200); rotating secrets comes with phase 36 (D183)
"""

from __future__ import annotations

import os
import re
import threading
import time
import zoneinfo
from typing import Any

from sqlalchemy import text

from . import permissions as perms
from .metamodel_edit import EditError

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
DATE_FORMATS = ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD.MM.YYYY", "DD MMM YYYY", "MMM DD, YYYY"]
CURRENCIES = ["USD", "ZAR", "EUR", "GBP", "AUD", "CAD", "INR", "JPY", "CHF", "CNY", "NZD", "SGD", "AED", "BRL", "KES", "NGN"]

# key: (group, label, type, default, choices or (min, max), help)
REGISTRY: dict[str, tuple] = {
    "base_currency": ("application", "Base currency", "choice", "USD", CURRENCIES, "Every money value is in this currency (D182)."),
    "currency_symbol": ("application", "Currency symbol", "text", "$", (1, 5), "Shown before amounts, for example $, R or €."),
    "country": ("application", "Country or region", "text", "South Africa", (2, 60), "Where the installation is used."),
    "time_zone": ("application", "Time zone", "timezone", "Africa/Johannesburg", None,
                  "Times are stored in UTC and shown in this time zone, for everyone."),
    "date_format": ("application", "Date format", "choice", "YYYY-MM-DD", DATE_FORMATS, "How dates are shown on screens and in exports."),
    "decimal_separator": ("application", "Decimal separator", "choice", ".", [".", ","], "1234.5 or 1234,5"),
    "thousands_separator": ("application", "Thousands separator", "choice", " ", [" ", ",", ".", "'", ""],
                            "Between groups of three digits (empty for none)."),
    "first_day_of_week": ("application", "First day of the week", "choice", "Monday", ["Monday", "Sunday", "Saturday"],
                          "Calendars and week-based reports."),
    "financial_year_start": ("application", "Month the financial year starts", "month", 3, (1, 12),
                             "Financial years and quarters in reports start in this month."),
    "upload_max_mb": ("system", "Largest upload (MB)", "int", 50, (1, 100),
                      "Packages, Excel and CSV sheets, documents. The web server lets at most 100 MB through."),
    "change_log_keep_days": ("system", "Keep change log entries (days)", "int", 730, (0, 36500),
                             "Older entries are removed automatically every hour; 0 keeps them for ever."),
    "session_idle_minutes": ("system", "Signed out after idle (minutes)", "int", 60, (5, 1440), "Applied to Keycloak at once."),
    "session_max_hours": ("system", "Longest session (hours)", "int", 10, (1, 168),
                          "Signed out after this long whatever happens; applied to Keycloak at once."),
    "log_level": ("system", "Log level", "choice", "INFO", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                  "How much the API, the job runner and the change log write to their logs (eax logs api); applied at once. "
                  "INFO by default, on a laptop and a server alike (R5.6)."),
    "logs_keep_days": ("system", "Delete logs older than (days)", "int", 7, (0, 3650),
                       "The containers' daily logs, the web log, eax's own logs (work/logs) and the log backups are deleted "
                       "when older, every night (R2.30); 7 days by default (R5.6); 0 keeps them."),
    "jobs_slots_tasks": ("system", "Job slots per API server: people's work", "int", 4, (1, 32),
                         "Backups, deliveries, merges... at once on each API server; taken when the servers restart "
                         "(System Admin › Scaling, Apply now) (R5.33)."),
    "jobs_slots_scheduled": ("system", "Job slots per API server: scheduled jobs", "int", 2, (1, 16),
                             "The scheduled housekeeping at once on each API server; taken when the servers restart (R5.33)."),
    "jobs_full_waiting": ("system", "Job queue too full: jobs waiting", "int", 20, (1, 10000),
                          "Above this many waiting, low-priority recurring jobs miss their turn; their next run does the "
                          "work (System Admin › Jobs, R5.6)."),
    "jobs_full_minutes": ("system", "Job queue too full: oldest waiting (minutes)", "int", 10, (1, 1440),
                          "When the oldest waiting job has waited longer, low-priority recurring jobs miss their turn (R5.6)."),
    "jobs_skip_max": ("system", "Skips in a row before a low-priority job runs anyway", "int", 5, (1, 100),
                      "A low-priority recurring job skipped this many times in a row runs anyway (R5.6)."),
    "gov_dispensation_warn_days": ("application", "Warn of a dispensation ending (days before)", "int", 30, (1, 365),
                                   "Its owner, sponsor, the project's Project Admins and Lead Architects and the Architecture "
                                   "Board are told this many days before a dispensation ends, and again on the day (R5.5.1)."),
    "jobs_waiting_minutes": ("system", "A background job is stuck after waiting (minutes)", "int", 5, (1, 1440),
                             "System Admin › Jobs and the alert 'jobs stuck' count a job waiting longer as stuck (R5.30)."),
    "jobs_running_minutes": ("system", "A background job is stuck after running (minutes)", "int", 60, (5, 1440),
                             "Backups, restores and the self-test may run three times as long (R5.30)."),
    "web_log_debug_until": ("hidden", "Web log debug until", "text", "", (0, 40),
                            "Set on System Admin › Logs: while it lasts, each API call's input and answer are written too "
                            "(masked), R5.6. Empty: off."),
    # the resource history (R3.5-M8; owner, 14 Nov 2026: "every 15 min configurable from admin screen"): set here or on
    # System Admin > Footprint, applied at once (the job eax.resource_sample reads them each minute)
    "resource_every_minutes": ("system", "Resource history: a sample every (minutes)", "int", 15, (0, 1440),
                               "Memory, CPU, disk and the database's cache of every container, kept on System Admin › Footprint; "
                               "0 stops it. Taken while people work and while the self-test runs."),
    "resource_detail_days": ("system", "Resource history: every sample kept for (days)", "int", 7, (1, 365),
                             "Older samples become one an hour (their average and peak), so the history stays small."),
    "resource_keep_days": ("system", "Resource history: kept for (days)", "int", 90, (1, 3650),
                           "Older samples are deleted automatically."),
    "resource_boost_every": ("hidden", "Resource history: for a while, a sample every (minutes)", "int", 0, (0, 60),
                             "Set on System Admin › Footprint for a test; goes back by itself."),
    "resource_boost_until": ("hidden", "Resource history: the shorter interval until", "text", "", (0, 40),
                             "When the shorter interval ends (UTC)."),
    # database maintenance (R5.12, D691): the window for the nightly tidy, and how long a session may sit idle in a
    # transaction before it is ended
    "db_maint_window_start": ("system", "Database maintenance: window starts", "text", "01:00", (5, 5),
                              "The nightly tidy (VACUUM, ANALYZE, REINDEX CONCURRENTLY) runs between these times (HH:MM, local)."),
    "db_maint_window_end": ("system", "Database maintenance: window ends", "text", "05:00", (5, 5), "HH:MM, local."),
    "db_idle_tx_minutes": ("system", "End sessions idle in a transaction after (minutes)", "int", 30, (0, 1440),
                           "They hold locks and stop the tidy; 0 never ends them."),
    # automated security testing (R5.17): the security suite every week, by itself
    "security_test_weekly": ("system", "Security test every week", "bool", True, None,
                             "Every Sunday at 03:20 the security suite runs by itself (scans, attacks, the gate); a new finding raises an alert."),
    # the optimisation report (R5.1, D697: "This limit should be configurable")
    "optimise_unused_days": ("system", "Optimisation report: unused after (days)", "int", 180, (30, 3650),
                             "A model or project not opened or changed for this long is suggested for the archive."),
    # alerts (R5.9, D689): who gets the email, through the mail server in the config file (EAX_SMTP_*)
    "alerts_email_to": ("system", "Alerts: email to", "text", "", (0, 500),
                        "Addresses (comma-separated) that get every alert, reminder and recovery by email; empty: none. The mail "
                        "server is set in the config file (EAX_SMTP_HOST and the rest)."),
    "alerts_email_escalate": ("system", "Alerts: also email when not acknowledged", "text", "", (0, 500),
                              "Addresses told as well when an alert is not acknowledged within 30 minutes."),
    # multi-factor sign-in (R5.3, D690; owner, 15 Nov 2026: "A setting, off by default", "kepp mfa off by default"):
    # applied to Keycloak at once and every hour (eax/keycloak_upkeep.py)
    "mfa_mode": ("security", "Multi-factor sign-in", "choice", "off", ["off", "admins", "everyone"],
                 "off: nobody is asked (anyone may still add an authenticator app to their own account). admins: the "
                 "Super, IT, User and Keycloak Admins and the Auditors set up a code at their next sign-in. everyone: "
                 "every person does. Codes come from an authenticator app (TOTP)."),
    # the parts of EA Explorer an organisation uses (owner, 8 Nov 2026, phase 13.3, D329): off hides a part's screens, menus,
    # API, MCP tools and background work; its data is kept and comes back when it is switched on again
    "part_projects": ("system", "Projects", "bool", True, None,
                      "Architecture projects, Project admin, the project library and templates. Off also switches off the "
                      "Repository and References (they show what projects hold). The data is kept."),
    "part_repository": ("system", "Repository", "bool", True, None,
                        "The Architecture Repository, at organisation and project level. Needs Projects. The data is kept."),
    "part_references": ("system", "References", "bool", True, None,
                        "The organisation's reference library and the projects' references. Needs Projects. The data is kept."),
    # the library (owner, 9 Nov 2026, phase 15.2, D350): EA Explorer's own, the organisation's own somewhere else, or none.
    # Projects keep their own library whatever is chosen (a project admin may point theirs at a link of its own).
    "library_mode": ("system", "Enterprise library", "choice", "ours", ["ours", "link", "off"],
                     "ours: EA Explorer's library. link: the organisation's own library at the link below (opened in a new tab). "
                     "off: no enterprise library. Project libraries stay either way."),
    "library_link": ("system", "Enterprise library link", "url", "", (0, 500),
                     "With link: where the organisation's own library is (https://…)."),
    "library_search_link": ("system", "Enterprise library search link", "url", "", (0, 500),
                            "Optional, with link: the library's search page with {q} where the words go, "
                            "for example https://intranet.example.org/search?q={q}."),
}
PARTS = ("projects", "repository", "references")

_cache: dict[str, Any] = {"at": 0.0, "values": None}
_lock = threading.Lock()
CACHE_SECONDS = 15


# defaults that depend on the deployment (owner, 12 Nov 2026, R2.30: "Laptop mode should be debug other can be error")
# (R5.6, owner 14 Nov 2026: "We will by default keep it at an info level"; "Logs are deleted once every 7 days"): the
# same everywhere now
BY_DEPLOYMENT: dict[str, dict] = {}


def default_of(key: str) -> Any:
    """A setting's default: by deployment (EAX_DEPLOYMENT) where BY_DEPLOYMENT says, else the registry's."""
    import os
    by = BY_DEPLOYMENT.get(key)
    if by:
        kind = (os.environ.get("EAX_DEPLOYMENT") or "laptop").strip().lower()
        return by.get(kind, by["*"])
    return REGISTRY[key][3]


def _default_values() -> dict[str, Any]:
    return {k: default_of(k) for k in REGISTRY}


def values(conn=None) -> dict[str, Any]:
    """Every runtime setting (cached for a few seconds); the defaults for any not in the database."""
    with _lock:
        if _cache["values"] is not None and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return dict(_cache["values"])
    out = _default_values()
    try:
        if conn is None:
            from .db import get_engine
            with get_engine().connect() as c:
                rows = c.execute(text("SELECT key, value FROM core.settings")).mappings().all()
        else:
            rows = conn.execute(text("SELECT key, value FROM core.settings")).mappings().all()
        for r in rows:
            if r["key"] in REGISTRY:
                out[r["key"]] = r["value"]
    except Exception:  # noqa: BLE001 - the defaults keep the API answering
        return out
    with _lock:
        _cache.update(at=time.monotonic(), values=dict(out))
    return out


def parts(conn=None) -> dict[str, bool]:
    """Which parts are on (D329): Repository and References only while Projects is on."""
    v = values(conn)
    proj = bool(v.get("part_projects", True))
    return {"projects": proj, "repository": proj and bool(v.get("part_repository", True)),
            "references": proj and bool(v.get("part_references", True))}


# what each part answers in the API (path prefixes under /api/v1); the first part that is off and matches refuses it
PART_PATHS = {
    "references": (r"^/api/v1/reference-library", r"^/api/v1/projects/reference-sources", r"^/api/v1/projects/[^/]+/reference(s|/|$)"),
    "repository": (r"^/api/v1/repository/(?!summary$)", r"^/api/v1/projects/[^/]+/repo-tags"),   # summary: the Organisation base's id
    "projects": (r"^/api/v1/projects", r"^/api/v1/calendars", r"^/api/v1/calendar-feed/", r"^/api/v1/tracking-sheets",
                 r"^/api/v1/repository/", r"^/api/v1/reference-library"),
}


def part_of_path(path: str, on: dict[str, bool]) -> str | None:
    """The switched-off part a request belongs to, or None."""
    for part in ("projects", "repository", "references"):
        if not on.get(part, True) and any(re.match(p, path) for p in PART_PATHS[part]):
            return part
    return None


def forget() -> None:
    """Forgets the cached settings (they are read again)."""
    with _lock:
        _cache.update(at=0.0, values=None)


def describe(conn) -> dict:
    """The settings with their labels, types, choices and help, grouped (for the console)."""
    v = values(conn)
    rows = {r["key"]: r for r in conn.execute(text("SELECT key, modified_at, modified_by FROM core.settings")).mappings()}
    out: dict[str, list] = {"application": [], "system": [], "security": []}   # security: System Admin › Security (R5)
    for k, (group, label, typ, _default, choices, help_) in REGISTRY.items():
        if group == "hidden":                   # set by their own screen only (the resource history's shorter interval)
            continue
        out[group].append({"key": k, "label": label, "type": typ, "value": v[k], "default": default_of(k),
                           "choices": choices if isinstance(choices, list) else None,
                           "range": list(choices) if isinstance(choices, tuple) else None, "help": help_,
                           "modified_at": rows.get(k, {}).get("modified_at") if _by_person(rows.get(k, {})) else None,
                           "modified_by": rows.get(k, {}).get("modified_by") if _by_person(rows.get(k, {})) else None})
    out["months"] = MONTHS
    out["parts"] = parts(conn)
    return out


def _by_person(row: dict) -> bool:
    """A setting changed by a person (not the installer's defaults)."""
    return bool(row.get("modified_by")) and row["modified_by"] not in ("eax_app", "eax_migrator", "postgres")


def check(key: str, value: Any) -> Any:
    """The value as stored, or EditError saying what is wrong."""
    if key not in REGISTRY:
        raise EditError(f"There is no setting '{key}'.", 404)
    _group, label, typ, _default, choices, _help = REGISTRY[key]
    if typ == "bool":
        if isinstance(value, bool):
            return value
        if str(value).strip().lower() in ("true", "on", "yes", "1"):
            return True
        if str(value).strip().lower() in ("false", "off", "no", "0"):
            return False
        raise EditError(f"{label}: on or off.")
    if typ in ("int", "month"):
        try:
            n = int(value)
        except (TypeError, ValueError) as exc:
            raise EditError(f"{label}: a whole number, please.") from exc
        lo, hi = choices
        if not lo <= n <= hi:
            raise EditError(f"{label}: between {lo} and {hi}.")
        return n
    s = "" if value is None else str(value)
    if typ == "choice":
        if s not in choices:
            raise EditError(f"{label}: one of {', '.join(repr(c) for c in choices)}.")
        return s
    if typ == "timezone":
        if s not in zoneinfo.available_timezones():
            raise EditError(f"{label}: '{s}' is not a time zone (for example Africa/Johannesburg).")
        return s
    lo, hi = choices
    s = s.strip()
    if not lo <= len(s) <= hi:
        raise EditError(f"{label}: {lo} to {hi} characters.")
    if typ == "url" and s:
        if not re.match(r"^https?://[^\s/]+", s, re.I):
            raise EditError(f"{label}: a web address starting with https:// or http://.")
        if key == "library_search_link" and "{q}" not in s:
            raise EditError(f"{label}: put {{q}} where the search words go.")
    if key.startswith("db_maint_window_") and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", s):
        raise EditError(f"{label}: a time as HH:MM, for example 01:00.")
    if key.startswith("alerts_email") and s:
        bad = [a for a in re.split(r"[,;]\s*", s) if a and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", a)]
        if bad:
            raise EditError(f"{label}: {bad[0]} is not an email address.")
    return s


def store(conn, clean: dict) -> None:
    """Writes checked values (check()) and forgets the cache, so they apply at once. The caller says who may."""
    import json
    for k, v in clean.items():
        conn.execute(text("""INSERT INTO core.settings (key, value, name) VALUES (:k, CAST(:v AS jsonb), :n)
                             ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, modified_at = now(),
                                 modified_by = core.current_actor(), row_version = core.settings.row_version + 1
                             WHERE core.settings.value IS DISTINCT FROM EXCLUDED.value"""),
                     {"k": k, "v": json.dumps(v), "n": REGISTRY[k][1]})
    forget()


def library(conn=None) -> dict:
    """The enterprise library as the screens and the library service see it (D350): mode ours, link or off. Off when
    the library service is switched off (EAX_SERVICE_LIBRARY) and EA Explorer's own is chosen, or when Projects is off."""
    v = values(conn)
    mode = v.get("library_mode") or "ours"
    link, search = (v.get("library_link") or "").strip(), (v.get("library_search_link") or "").strip()
    service = os.environ.get("EAX_SERVICE_LIBRARY", "on").strip().lower() not in ("off", "false", "0", "no", "disabled")
    if mode == "link" and not link:
        mode = "ours"
    return {"mode": mode if parts(conn)["projects"] else "off", "link": link if mode == "link" else "",
            "search_link": search if mode == "link" else "", "service": service and parts(conn)["projects"]}


def update(conn, user, changes: dict) -> dict:
    """Changes settings (Super Admin), applies them at once (session time-outs in Keycloak), returns the new values."""
    if perms.SUPER_ADMIN not in (user.roles or []):
        raise EditError("Only a Super Admin changes settings.", 403)
    clean = {k: check(k, v) for k, v in (changes or {}).items()}
    after = {**values(conn), **clean}
    if not after.get("part_projects", True):
        for k in ("part_repository", "part_references"):
            if clean.get(k) is True:
                raise EditError(f"{REGISTRY[k][1]} needs Projects: switch Projects on first.")
    if clean.get("decimal_separator", values(conn)["decimal_separator"]) == clean.get("thousands_separator",
                                                                                       values(conn)["thousands_separator"]):
        raise EditError("The decimal and thousands separators must differ.")
    store(conn, clean)
    applied, note = [], ""
    if {"session_idle_minutes", "session_max_hours"} & set(clean):
        v = {**values(conn), **clean}
        try:
            from . import keycloak_admin
            keycloak_admin.set_sessions(int(v["session_idle_minutes"]) * 60, int(v["session_max_hours"]) * 3600)
            applied.append("session time-outs (Keycloak)")
        except Exception as exc:  # noqa: BLE001
            note = f" The session time-outs are saved but Keycloak did not take them ({exc}); they apply after the next restart."
    if "mfa_mode" in clean:
        try:
            from . import keycloak_upkeep
            r = keycloak_upkeep.apply_mfa(clean["mfa_mode"])
            applied.append("multi-factor sign-in (Keycloak)")
            note += f" Multi-factor sign-in {r['mode']}: {r['asked']} asked to set up a code, {r['released']} no longer asked."
        except Exception as exc:  # noqa: BLE001
            note += f" Multi-factor sign-in is saved but Keycloak did not take it yet ({exc}); it is applied within the hour."
    if {"part_projects", "part_repository", "part_references"} & set(clean):
        p = parts(conn)
        off = [k.title() for k in PARTS if not p[k]]
        note += (f" Switched off: {', '.join(off)} (their data is kept)." if off else " Every part is on.")
    return {"values": values(conn), "changed": sorted(clean), "note": f"{len(clean)} settings saved and applied at once.{note}",
            "applied": applied, "parts": parts(conn)}


# ---------------------------------------------------------------- start-up settings (shown only, D183)
SECRET = re.compile(r"(PASSWORD|SECRET|TOKEN|_KEY$|PRIVATE)", re.I)
GROUPS = [("Database", ("EAX_DB_",)), ("Change log", ("EAX_CHANGELOG_",)), ("Host and network", ("EAX_HOSTNAME", "EAX_HTTP", "EAX_TLS",
          "EAX_PUBLIC")), ("Sign-in (Keycloak)", ("EAX_KC_", "EAX_KEYCLOAK", "EAX_FIRST_ADMIN", "EAX_BREAK_GLASS", "EAX_API_AUDIENCE")),
          ("Reports (Superset)", ("EAX_SUPERSET",)), ("Documents (Mayan)", ("EAX_MAYAN", "EAX_DMS")), ("MCP", ("EAX_MCP",)),
          ("Folders and backups", ("EAX_BACKUP", "EAX_IMPORT", "EAX_EXPORT", "EAX_WORK")), ("Operations helper", ("EAX_OPS",))]


def startup() -> dict:
    """The start-up settings the containers were started with (this container's view), grouped, in clear text: only IT
    and Super Admins see them (owner, 5 Nov 2026)."""
    env = {k: v for k, v in os.environ.items() if k.startswith("EAX_")}
    out: dict[str, list] = {}
    for k in sorted(env):
        group = next((g for g, prefixes in GROUPS if k.startswith(prefixes)), "General")
        out.setdefault(group, []).append({"key": k, "value": env[k], "secret": bool(SECRET.search(k))})
    return {"groups": [{"name": g, "settings": out[g]} for g, _ in [("General", ())] + GROUPS if g in out],
            "file": "work/eaexplorer.env",
            "note": "The values the containers were started with. Change them in the config file below (Edit): they apply at "
                    "the next eax up. Rotating passwords in the database and Keycloak comes with phase 36."}


_LEVEL = {"level": None}


def apply_log_level() -> None:
    """The log level set in the console (D191), applied to this process when it changed (cheap: values() is cached)."""
    import logging
    try:
        level = str(values().get("log_level") or "INFO").upper()
    except Exception:  # noqa: BLE001
        return
    if level != _LEVEL["level"] and level in ("DEBUG", "INFO", "WARNING", "ERROR"):
        logging.getLogger().setLevel(level)
        logging.getLogger("eax").setLevel(level)
        _LEVEL["level"] = level
