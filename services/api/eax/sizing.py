"""The server sizing estimate (R5.19; owner, 14 Nov 2026: "A user will put in the number of concurrent users and models
and projects. We need to be able to predict RAM, CPU and Disk for server deployments"; "R4.10 will have to be done
without 4.9 based on best guess. We will not have server class machines to run this"; "same for containers etc for
them to estimate this out").

**This is a best estimate, and every answer says so.** The sizing model is this one file: per container a fixed base
plus what each person at once, each thousand elements, each project and each thousand documents adds (CONTAINERS), and
the sizes of the data itself (DATA). The figures were worked out from what each container is given and uses on the
owner's laptop (its limits in deploy/compose/docker-compose.laptop.yml, the memory measured in Release 3.5), each
component's own published needs (PostgreSQL, Keycloak, Superset, Mayan EDMS, Valkey) and the API's workers and
connections per person. When real figures come in (System Admin > Footprint, the benchmark of R5.18), the change is made
here, with its reason in CHANGES. A margin for peaks (HEADROOM, 30%) is added and the answer rounded to sizes servers
come in; past a size the advice is to split (the database, Reports or Documents on their own, R2.50).

estimate(inputs) answers: the server's RAM, CPU cores and disk; per container the memory and CPU to reserve and the
limit, the copies to run (only for the containers that can run more than one), each volume's size and a year's growth;
the settings to use (the API's workers, the database's memory, each container's limit); for a container platform the
nodes it adds up to with room to lose one; a compose override to paste; and the assumptions it used.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

VERSION = "1"          # bumped with every change of the figures below (CHANGES says why)
CHANGES = [("1", "2026-11-15", "first figures: the laptop's limits and Release 3.5's measuring, each component's published needs")]
HEADROOM = 0.30
SIZES = {"small": (500, 700), "medium": (5000, 7000), "large": (25000, 35000)}       # elements, relationships a model
RAM_GB = (4, 8, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512)
CORES = (2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128)
SPLIT_AT_GB, SPLIT_AT_USERS = 64, 400

# the data itself (D: assumptions a person can change on the screen)
DATA = {
    "kb_per_element": 12.0,          # its row, attribute values, indexes and the history of its changes (about 3 versions)
    "kb_per_relationship": 6.0,
    "mb_per_project": 8.0,           # its pages, deliverables, governance records and views
    "mb_per_document": 2.0,          # an average document kept in Documents (the file, its pages and text)
    "growth_per_year": 0.30,         # the repository grows by this share in a year
    "backup_ratio": 0.35,            # a compressed backup's size against what it backs up
    "log_mb_per_day": 150.0,         # every container's logs together, a day (kept 7 days)
    "users_per_api_copy": 150,       # people at once one API container serves well
    "connections_per_worker": 5,     # the database connections each API worker holds
}


@dataclass(frozen=True)
class C:
    """A container's figures: memory (MB) = base + per person at once + per 1,000 elements + per project + per 1,000
    documents; CPU (cores) = base + per person at once. many: it may run as more than one copy; once: it runs and stops
    (set-up); needs: the switch it depends on (reports, documents, mcp, discovery) or "" for always."""
    name: str
    what: str
    mb: float
    mb_user: float = 0.0
    mb_kel: float = 0.0
    mb_project: float = 0.0
    mb_kdoc: float = 0.0
    cpu: float = 0.1
    cpu_user: float = 0.0
    many: bool = False
    once: bool = False
    needs: str = ""


CONTAINERS = [
    C("proxy", "the front door (nginx)", 32, 0.3, cpu=0.1, cpu_user=0.004, many=True),
    C("web", "the screens (static files)", 32, cpu=0.05, many=True),
    C("api", "the API, its job servers and the MCP server", 1100, 25, 0.8, 2, cpu=0.5, cpu_user=0.02, many=True),
    C("library", "the reference library", 160, 1.5, cpu=0.1, cpu_user=0.002, many=True),
    C("views", "the drawn views' service", 160, 2, 0.4, cpu=0.1, cpu_user=0.002, many=True),
    C("drawio", "draw.io (the drawing editor)", 320, 3, cpu=0.1, cpu_user=0.004, many=True),
    C("db", "PostgreSQL (every database, R2.50)", 384, 6, 0, 3, cpu=0.5, cpu_user=0.015),     # + its cache: below
    C("keycloak", "sign-in (Keycloak)", 620, 1, cpu=0.3, cpu_user=0.003),
    C("reports", "Reports (Superset)", 1250, 15, 0.6, cpu=0.3, cpu_user=0.01, needs="reports"),
    C("reports-init", "Reports' set-up (runs and stops)", 512, cpu=0.5, once=True, needs="reports"),
    C("dms", "Documents (Mayan EDMS)", 2050, 20, 0, 0, 60, cpu=0.5, cpu_user=0.01, needs="documents"),
    C("dms-broker", "Documents' message broker (Valkey)", 64, 0, 0, 0, 4, cpu=0.05, needs="documents"),
    C("ops", "the operations helper", 128, cpu=0.1),
    C("backup", "backups", 160, 0, 0.3, cpu=0.2),
    C("setup", "set-up at each start (runs and stops)", 256, cpu=0.5, once=True),
]
VOLUMES = {"db": "database", "dms": "documents", "reports": "Reports' home", "backup": "backups"}


def _clean(inputs: dict) -> dict:
    """The inputs checked, with their defaults: users (people at once), models and their size, projects, documents a
    project, the switches, backups kept, headroom and the platform's node size."""
    def num(key, default, lo=0, hi=10 ** 7):
        try:
            v = float(inputs.get(key, default) if inputs.get(key, default) not in (None, "") else default)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} is a number.") from exc
        if not lo <= v <= hi:
            raise ValueError(f"{key} is between {lo} and {hi}.")
        return v
    size = str(inputs.get("model_size") or "medium")
    if size not in SIZES:
        raise ValueError("model_size is small, medium or large.")
    out = {"users": int(num("users", 20, 1, 100000)), "models": int(num("models", 10, 0, 100000)), "model_size": size,
           "projects": int(num("projects", 10, 0, 100000)), "documents_per_project": int(num("documents_per_project", 50, 0, 10 ** 6)),
           "backups_kept": int(num("backups_kept", 7, 0, 3650)), "headroom": num("headroom", HEADROOM, 0, 3),
           "node_gb": num("node_gb", 16, 2, 4096), "node_cores": num("node_cores", 4, 1, 1024)}
    for k in ("reports", "documents", "mcp", "discovery"):
        out[k] = bool(inputs.get(k, True))
    data = dict(DATA)
    for k, v in (inputs.get("assumptions") or {}).items():
        if k in DATA:
            data[k] = float(v)
    out["assumptions"] = data
    return out


def _up(v: float, steps) -> float:
    return next((s for s in steps if s >= v), steps[-1] if v <= steps[-1] else math.ceil(v / steps[-1]) * steps[-1])


def _mb_limit(v: float) -> int:
    """A container's limit, rounded up to 256 MB (64 MB below 512)."""
    step = 64 if v < 512 else 256
    return int(math.ceil(v / step) * step)


def estimate(inputs: dict) -> dict:
    """The sizing estimate for the inputs: per container, the server, the disk, the settings, the platform's nodes and a
    compose override, with the assumptions used."""
    p = _clean(inputs)
    a = p["assumptions"]
    el_per, rel_per = SIZES[p["model_size"]]
    kel = p["models"] * el_per / 1000
    docs = p["projects"] * p["documents_per_project"] if p["documents"] else 0
    copies_api = max(1, math.ceil(p["users"] / a["users_per_api_copy"]))
    workers = int(min(8, max(2, math.ceil(p["users"] / copies_api / 25))))
    rows, total_mb, total_cpu = [], 0.0, 0.0
    db_data_mb = p["models"] * (el_per * a["kb_per_element"] + rel_per * a["kb_per_relationship"]) / 1024
    for c in CONTAINERS:
        if c.needs and not p.get(c.needs):
            continue
        copies = copies_api if c.many and c.name in ("api", "proxy") else 1 if not c.many else max(1, math.ceil(copies_api / 2))
        users_each = p["users"] / copies
        mb = c.mb + c.mb_user * users_each + c.mb_kel * kel + c.mb_project * p["projects"] + c.mb_kdoc * docs / 1000
        if c.name == "db":                       # a cache of a quarter of the data, at most 16 GB
            mb += min(db_data_mb * 0.25, 16384)
        if c.name == "api" and p["mcp"]:
            mb += 64
        if c.name == "api" and p["discovery"]:
            mb += 96
        cpu = c.cpu + c.cpu_user * users_each
        limit = _mb_limit(mb * (1 + p["headroom"]))
        cpu_limit = round(max(0.25, cpu * (1 + p["headroom"]) * 2), 2)          # bursts: twice the steady need
        rows.append({"container": c.name, "what": c.what, "copies": copies, "many": c.many, "once": c.once,
                     "memory_reserve_mb": int(math.ceil(mb)), "memory_limit_mb": limit,
                     "cpu_reserve": round(cpu, 2), "cpu_limit": cpu_limit})
        if not c.once:                                                       # set-up runs before the rest: not added
            total_mb += limit * copies
            total_cpu += cpu * copies
    # the disk
    db_gb = db_data_mb / 1024 + p["projects"] * a["mb_per_project"] / 1024 + 1.0
    docs_gb = docs * a["mb_per_document"] / 1024
    rep_gb = 1.0 if p["reports"] else 0.0
    logs_gb = a["log_mb_per_day"] * 7 / 1024
    backups_gb = (db_gb + docs_gb) * a["backup_ratio"] * max(1, p["backups_kept"])
    g = a["growth_per_year"]
    disk = {"database": db_gb, "documents": docs_gb, "reports": rep_gb, "logs": logs_gb, "backups": backups_gb,
            "images": 12.0}
    disk = {k: round(v, 1) for k, v in disk.items()}
    year = {k: round(v * (1 + g), 1) if k in ("database", "documents", "backups") else v for k, v in disk.items()}
    disk_total = sum(year.values()) * (1 + p["headroom"])
    ram_gb = total_mb / 1024 + 1.0                                           # the operating system
    server = {"ram_gb": _up(ram_gb, RAM_GB), "cores": _up(total_cpu * (1 + p["headroom"]), CORES),
              "disk_gb": int(math.ceil(disk_total / 50) * 50), "ram_needed_gb": round(ram_gb, 1),
              "cores_needed": round(total_cpu, 2), "disk_needed_gb": round(disk_total, 1)}
    split = []
    if ram_gb > SPLIT_AT_GB or p["users"] > SPLIT_AT_USERS:
        split = ["the database on a server of its own (EAX_DB_HOST, R2.50)",
                 *(["Reports on its own server"] if p["reports"] else []), *(["Documents on its own server"] if p["documents"] else [])]
    db = next(r for r in rows if r["container"] == "db")
    settings = {"EAX_API_WORKERS": workers, "api copies (System Admin > Scaling)": copies_api,
                "PostgreSQL shared_buffers": f"{max(128, int(db['memory_limit_mb'] * 0.25))}MB",
                "PostgreSQL effective_cache_size": f"{max(256, int(db['memory_limit_mb'] * 0.6))}MB",
                "PostgreSQL max_connections": max(100, copies_api * workers * int(a["connections_per_worker"]) + 50)}
    per_node = p["node_gb"] * 1024 * 0.8
    nodes = max(1, math.ceil(total_mb / per_node), math.ceil(total_cpu / (p["node_cores"] * 0.8))) + 1   # room to lose one
    vols = [{"volume": name, "for": c, "gb": disk.get({"db": "database", "dms": "documents", "reports": "reports", "backup": "backups"}[c], 0),
             "in_a_year_gb": year.get({"db": "database", "dms": "documents", "reports": "reports", "backup": "backups"}[c], 0)}
            for c, name in VOLUMES.items() if any(r["container"] == c for r in rows)]
    return {"estimate": True, "says": "A best estimate, not a measurement: check it against what the installation really uses.",
            "model_version": VERSION, "inputs": {k: v for k, v in p.items() if k != "assumptions"}, "assumptions": a,
            "headroom": p["headroom"], "containers": rows, "server": server, "disk": disk, "disk_in_a_year": year,
            "volumes": vols, "settings": settings, "split": split, "platform": {"nodes": nodes, "node_gb": p["node_gb"],
                                                                                "node_cores": p["node_cores"]},
            "override": override(rows)}


def override(rows: list[dict]) -> str:
    """A compose override with each service's memory limit (and the API's copies), to paste beside docker-compose.yml."""
    lines = ["# EA Explorer: the sizing estimate's limits (a best estimate; R5.19). Use with -f docker-compose.yml -f this file.",
             "services:"]
    for r in rows:
        lines += [f"  {r['container']}:", "    deploy:"]
        if r["many"] and r["copies"] > 1:
            lines.append(f"      replicas: {r['copies']}")
        lines += ["      resources:", f"        limits: {{ memory: {r['memory_limit_mb']}m, cpus: \"{r['cpu_limit']}\" }}",
                  f"        reservations: {{ memory: {r['memory_reserve_mb']}m }}"]
    return "\n".join(lines) + "\n"


LAPTOP = {"users": 5, "models": 10, "model_size": "small", "projects": 5, "documents_per_project": 20, "backups_kept": 7}


def against(result: dict, measured: list[dict]) -> list[dict]:
    """The estimate beside what each container really used (the resource history's peaks): for the screen, so the
    figures above can be corrected."""
    real = {}
    for c in measured or []:
        name = str(c.get("container") or "")
        base = name.split("-")[1] if name.count("-") >= 2 else name
        real[base] = max(real.get(base, 0), float(c.get("memory_peak_mb") or c.get("memory_mb") or 0))
    return [{"container": r["container"], "estimate_mb": r["memory_reserve_mb"], "limit_mb": r["memory_limit_mb"],
             "really_mb": round(real[r["container"]]) if r["container"] in real else None} for r in result["containers"]]


def workbook(result: dict) -> bytes:
    """An estimate as an Excel workbook (estimate, containers, disk, settings, assumptions)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Estimate"
    s = result["server"]
    for row in (["EA Explorer server sizing: a best estimate", ""], [result["says"], ""], [],
                ["RAM (GB)", s["ram_gb"]], ["CPU cores", s["cores"]], ["Disk (GB, a year on)", s["disk_gb"]], [],
                ["Input", "Value"], *[[k, str(v)] for k, v in result["inputs"].items()]):
        ws.append(row)
    ws["A1"].font = Font(bold=True, size=14)
    c = wb.create_sheet("Containers")
    head = ["Container", "What", "Copies", "Reserve MB", "Limit MB", "CPU reserve", "CPU limit"]
    c.append(head)
    for r in result["containers"]:
        c.append([r["container"], r["what"], r["copies"], r["memory_reserve_mb"], r["memory_limit_mb"], r["cpu_reserve"], r["cpu_limit"]])
    d = wb.create_sheet("Disk")
    d.append(["Part", "GB now", "GB in a year"])
    for k, v in result["disk"].items():
        d.append([k, v, result["disk_in_a_year"][k]])
    t = wb.create_sheet("Settings")
    for k, v in result["settings"].items():
        t.append([k, str(v)])
    m = wb.create_sheet("Assumptions")
    for k, v in {**result["assumptions"], "headroom": result["headroom"], "model_version": result["model_version"]}.items():
        m.append([k, v])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def text_report(result: dict) -> str:
    """An estimate as text, for eax estimate."""
    s = result["server"]
    out = [f"EA Explorer server sizing ({result['says']})", "",
           f"Server: {s['ram_gb']} GB RAM, {s['cores']} CPU cores, {s['disk_gb']} GB disk "
           f"(needed {s['ram_needed_gb']} GB, {s['cores_needed']} cores, {s['disk_needed_gb']} GB with {int(result['headroom'] * 100)}% headroom)", "",
           f"{'Container':<14}{'copies':>7}{'reserve MB':>12}{'limit MB':>10}{'CPU':>7}"]
    for r in result["containers"]:
        out.append(f"{r['container']:<14}{r['copies']:>7}{r['memory_reserve_mb']:>12}{r['memory_limit_mb']:>10}{r['cpu_reserve']:>7}"
                   + ("  (runs and stops)" if r["once"] else ""))
    out += ["", "Disk now / in a year (GB): " + ", ".join(f"{k} {v}/{result['disk_in_a_year'][k]}" for k, v in result["disk"].items()),
            "Settings: " + "; ".join(f"{k} {v}" for k, v in result["settings"].items()),
            f"On a container platform: {result['platform']['nodes']} nodes of {result['platform']['node_gb']:g} GB, "
            f"{result['platform']['node_cores']:g} cores (one spare)"]
    if result["split"]:
        out.append("Past one server's size: put " + "; ".join(result["split"]))
    out.append("Assumptions: " + ", ".join(f"{k} {v}" for k, v in result["assumptions"].items()))
    return "\n".join(out)
