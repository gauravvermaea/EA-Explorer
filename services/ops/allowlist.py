"""IP allow-listing at the front door (R5.2, D686: "I assume 5.2 ip white listing will be managed on nginx").

The lists live in work/proxy/allow/lists.json, written here only (the API sends them; `eax allow` on the machine runs
this file inside the ops container when no screen can be reached). From them this module writes the files nginx reads
(work/proxy is the proxy's /eax-proxy, read only there):

  allow/<place>.geo         one geo block body per place: "default 1;" then each allowed address or range with 0.
                            nginx sets $eax_deny_<place> to 1 for any other address; a place with no list holds
                            "default 0;" and everyone may come in, as before (the setup service makes them at start)
  allow/realip.conf         the load balancers trusted to say who the caller is (X-Forwarded-For from them only)

Places: site (everything on the main name, reports and docs), signin (/auth/, Keycloak), admin (System Admin's API:
/api/v1/admin/ and /api/v1/operations/), mcp (/mcp), machine (the client-certificate port, D366).

Never a lock-out: 127.0.0.0/8, ::1 and this installation's own Docker networks are always allowed (the self-test, the
API calling itself, the operations helper); the API refuses a change that would refuse the address of the person
making it; `eax allow clear` empties every list from the machine itself. Each new set of files is tested with
`nginx -t` in the proxy before nginx reloads; when the test fails the previous files are put back.

Each refusal is logged by nginx to /var/log/nginx/eax-refused.log (address, place, time, path); refused() reads it.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

PLACES = {
    "site": "Everything (the screens, the API, Reports and Documents)",
    "signin": "The sign-in pages (Keycloak)",
    "admin": "System Admin (its API)",
    "mcp": "AI (MCP)",
    "machine": "Machine access with client certificates (its own port)",
}
ALWAYS = ["127.0.0.0/8", "::1/128"]
WORK = os.environ.get("EAX_WORK_MOUNT", "/eax-work")
DIR = os.path.join(WORK, "proxy", "allow")
LISTS = os.path.join(DIR, "lists.json")
REFUSED_LOG = "/var/log/nginx/eax-refused.log"


def clean_entry(e: dict) -> dict:
    """One allowed address or range: {address, name, why}; the address normalised (10.1.2.0/24, 2001:db8::/32)."""
    raw = str(e.get("address") or "").strip()
    try:
        net = ipaddress.ip_network(raw, strict=False)
    except ValueError as exc:
        raise ValueError(f"{raw or '(empty)'} is not an address or a range (for example 10.1.2.3 or 10.1.0.0/16).") from exc
    return {"address": str(net), "name": str(e.get("name") or "")[:80], "why": str(e.get("why") or "")[:200]}


def clean(body: dict) -> dict:
    """The allow lists checked: known places, valid addresses."""
    lists = {}
    for place, entries in (body.get("lists") or {}).items():
        if place not in PLACES:
            raise ValueError(f"No place called {place}: {', '.join(PLACES)}.")
        seen, out = set(), []
        for e in entries or []:
            c = clean_entry(e if isinstance(e, dict) else {"address": e})
            if c["address"] not in seen:
                seen.add(c["address"])
                out.append(c)
        lists[place] = out
    trusted = [clean_entry(e if isinstance(e, dict) else {"address": e}) for e in body.get("trusted") or []]
    return {"lists": {p: lists.get(p, []) for p in PLACES}, "trusted": trusted}


def read() -> dict:
    """The allow lists kept."""
    try:
        with open(LISTS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return clean(data) | {"changed_at": data.get("changed_at"), "changed_by": data.get("changed_by")}


def allowed(lists: dict, place: str, address: str, internal: list[str] | None = None) -> bool:
    """Whether an address may reach a place: the site's list and the place's own both (an empty list lets everyone)."""
    ip = ipaddress.ip_address(address)
    always = [ipaddress.ip_network(n) for n in ALWAYS + list(internal or [])]
    if any(ip.version == n.version and ip in n for n in always):
        return True
    for p in ({place} if place == "machine" else {"site", place}):   # the certificate port: its own list only
        entries = lists.get(p) or []
        if entries and not any(ip.version == ipaddress.ip_network(e["address"]).version
                               and ip in ipaddress.ip_network(e["address"]) for e in entries):
            return False
    return True


def render(data: dict, internal: list[str]) -> dict[str, str]:
    """The files nginx reads, by name (in allow/): <place>.geo for every place, and realip.conf; all of them always, so
    nginx always finds what it includes (a place with no list: "default 0;", everyone in)."""
    files: dict[str, str] = {}
    for place in PLACES:
        entries = data["lists"].get(place) or []
        if not entries:
            files[f"{place}.geo"] = f"# {place}: no list, everyone may come in (R5.2)\ndefault 0;\n"
            continue
        lines = [f"# {PLACES[place]}: only these may come in (R5.2); written by EA Explorer, do not edit", "default 1;"]
        for n in ALWAYS + internal:
            lines.append(f"{n} 0;   # always: this machine and its own containers")
        for e in entries:
            note = " ".join(x for x in (e["name"], e["why"]) if x)
            lines.append(f"{e['address']} 0;" + (f"   # {_safe(note)}" if note else ""))
        files[f"{place}.geo"] = "\n".join(lines) + "\n"
    lines = ["# load balancers trusted to say who the caller is (R5.2); written by EA Explorer, do not edit"]
    if data.get("trusted"):
        lines += [f"set_real_ip_from {e['address']};" for e in data["trusted"]]
        lines += ["real_ip_header X-Forwarded-For;", "real_ip_recursive on;"]
    files["realip.conf"] = "\n".join(lines) + "\n"
    return files


def _safe(text: str) -> str:
    return re.sub(r"[^\w .,:/()@-]", "", text)[:120]


def _docker(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)


def proxy_container(project: str) -> str | None:
    """The front door's container."""
    out = _docker("ps", "-q", "--filter", f"label=com.docker.compose.project={project}",
                  "--filter", "label=com.docker.compose.service=proxy").stdout.split()
    return out[0] if out else None


def internal_networks(project: str) -> list[str]:
    """The subnets of this installation's own Docker networks (always allowed)."""
    nets = _docker("network", "ls", "-q", "--filter", f"label=com.docker.compose.project={project}").stdout.split()
    found: list[str] = []
    for n in nets:
        out = _docker("network", "inspect", n, "--format", "{{range .IPAM.Config}}{{.Subnet}} {{end}}").stdout
        for s in out.split():
            try:
                found.append(str(ipaddress.ip_network(s, strict=False)))
            except ValueError:
                pass
    return sorted(set(found)) or ["172.16.0.0/12"]


def _write_files(files: dict[str, str]) -> None:
    os.makedirs(DIR, exist_ok=True)
    for name, body in files.items():
        with open(os.path.join(DIR, name), "w", encoding="utf-8") as f:
            f.write(body)


def _current_files() -> dict[str, str]:
    out = {}
    if os.path.isdir(DIR):
        for name in os.listdir(DIR):
            if name.endswith(".geo") or name == "realip.conf":
                with open(os.path.join(DIR, name), encoding="utf-8") as f:
                    out[name] = f.read()
    return out


def apply(body: dict, project: str, by: str) -> dict:
    """Save the lists, write nginx's files, test them in the proxy and reload it; the old files back when the test
    fails. Returns the lists as saved."""
    data = clean(body)
    internal = internal_networks(project)
    before = _current_files()
    _write_files(render(data, internal))
    proxy = proxy_container(project)
    if proxy:
        test = _docker("exec", proxy, "nginx", "-t")
        if test.returncode != 0:
            _write_files(before)
            raise ValueError(f"nginx did not accept the lists, nothing changed: {(test.stderr or test.stdout)[-400:]}")
        _docker("exec", proxy, "nginx", "-s", "reload")
    saved = data | {"changed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "changed_by": by}
    os.makedirs(DIR, exist_ok=True)
    tmp = LISTS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(saved, f, indent=2)
    os.replace(tmp, LISTS)
    return saved | {"internal": internal, "reloaded": bool(proxy)}


def refused(project: str, tail: int = 5000) -> dict:
    """The refusals nginx logged: the most refused addresses, by place, and the latest."""
    proxy = proxy_container(project)
    lines: list[str] = []
    if proxy:
        out = _docker("exec", proxy, "sh", "-c", f"tail -n {int(tail)} {REFUSED_LOG} 2>/dev/null || true").stdout
        lines = [x for x in out.splitlines() if x.strip()]
    rows = []
    for x in lines:
        parts = x.split("\t")
        if len(parts) >= 4:
            rows.append({"at": parts[0], "address": parts[1], "place": parts[2], "path": parts[3][:200]})
    return {"count": len(rows), "by_address": Counter(r["address"] for r in rows).most_common(20),
            "by_place": dict(Counter(r["place"] for r in rows)), "latest": rows[-50:][::-1]}


def main(argv: list[str]) -> int:
    """`eax allow` runs this in the ops container: show | clear | add <place> <address> [name] | remove <place> <address>."""
    project = os.environ.get("COMPOSE_PROJECT_NAME", "eaexplorer")
    cmd = argv[0] if argv else "show"
    data = read()
    if cmd == "show":
        print(json.dumps({"lists": data["lists"], "trusted": data["trusted"]}, indent=2))
        return 0
    if cmd == "clear":
        apply({"lists": {}, "trusted": data["trusted"]}, project, "eax allow clear")
        print("Every allow list is empty: every address may come in again.")
        return 0
    if cmd in ("add", "remove") and len(argv) >= 3:
        place, address = argv[1], argv[2]
        if place not in PLACES:
            print(f"No place called {place}: {', '.join(PLACES)}.", file=sys.stderr)
            return 1
        lists = data["lists"]
        entry = clean_entry({"address": address, "name": " ".join(argv[3:]) or "added with eax allow"})
        if cmd == "add":
            lists[place] = [e for e in lists[place] if e["address"] != entry["address"]] + [entry]
        else:
            lists[place] = [e for e in lists[place] if e["address"] != entry["address"]]
        apply({"lists": lists, "trusted": data["trusted"]}, project, f"eax allow {cmd}")
        print(f"{place}: {', '.join(e['address'] for e in lists[place]) or 'everyone'}")
        return 0
    print("eax allow show | clear | add <place> <address> [name] | remove <place> <address>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
