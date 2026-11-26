"""Basic security tests (phase 36.1, D367, D525).

Run by the runner: the security headers and cookies of the front door (the proxy, as people reach it) and of the
sign-in page, and the Python dependencies (pip-audit). Run by the operations helper next to the runner (they need
Docker): an OWASP ZAP baseline scan of the front door and Trivy scans of EA Explorer's images (which see the Python
packages in the API's image and the npm packages of the web image's lock file); the runner then reads their reports
(collect). Unauthenticated and cross-user access are tested in the API matrix (api_matrix.py)."""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .. import httpopen

Record = Callable[[str, str, str, int], None]

# header: what a good value contains (lower case); None: only that it is there
HEADERS: list[tuple[str, str | None, str]] = [
    ("x-content-type-options", "nosniff", "failed"),
    ("referrer-policy", None, "failed"),
    ("strict-transport-security", "max-age", "warning"),       # on a server (EAX_HSTS); a laptop may leave it out
    ("x-frame-options", None, "warning"),
    ("content-security-policy", None, "failed"),               # enforced since R3.12 (D672)
]


def csp_problems(policy: str) -> list[str]:
    """What is weak in a Content-Security-Policy (R3.12, D672): scripts from anywhere, inline or eval'd; plugins; being
    framed by other sites; no default."""
    d: dict[str, list[str]] = {}
    for part in (policy or "").split(";"):
        bits = part.split()
        if bits:
            d[bits[0].lower()] = [b.lower() for b in bits[1:]]
    out = []
    script = d.get("script-src", d.get("default-src"))
    if "default-src" not in d:
        out.append("no default-src")
    if script is None:
        out.append("no script-src or default-src")
    else:
        for bad in ("'unsafe-inline'", "'unsafe-eval'", "*", "http:", "https:", "data:"):
            if bad in script:
                out.append(f"script-src allows {bad}")
    if d.get("object-src", d.get("default-src")) != ["'none'"]:
        out.append("object-src is not 'none'")
    fa = d.get("frame-ancestors")
    if fa is None or any(x not in ("'self'", "'none'") for x in fa):
        out.append("frame-ancestors lets other sites frame the screens")
    if "base-uri" not in d:
        out.append("no base-uri")
    return out


def _get(url: str, host: str) -> tuple[int, dict[str, str], list[str]]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE           # the front door is reached by its container name inside Docker
    req = urllib.request.Request(url, headers={"Host": host, "User-Agent": "EA Explorer test runner"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _NoRedirect())
    try:
        r = opener.open(req, timeout=20)
        status, headers = r.status, r.headers
    except urllib.error.HTTPError as exc:
        status, headers = exc.code, exc.headers
    return status, {k.lower(): v for k, v in headers.items()}, headers.get_all("Set-Cookie") or []


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # noqa: ANN002, ANN003
        """Never follows a redirect (the headers of the first answer are checked)."""
        return None


def check_headers(headers: dict[str, str], where: str, record: Record) -> None:
    """Records whether the security headers are there and good (the CSP's weaknesses named)."""
    for name, want, bad in HEADERS:
        have = headers.get(name)
        if name == "content-security-policy" and have is None and headers.get("content-security-policy-report-only"):
            record(f"{where}: header {name}", "warning", "only reported, not enforced (EAX_CSP_HEADER=Content-Security-Policy-"
                   "Report-Only)", 0)
            continue
        if name == "content-security-policy" and have is not None:
            weak = csp_problems(have)
            record(f"{where}: header {name}", "warning" if weak else "passed",
                   ("; ".join(weak) + ": " if weak else "") + have[:300], 0)
            continue
        if have is None and name == "strict-transport-security" and os.environ.get("EAX_DEPLOYMENT", "laptop") == "laptop":
            # off on a laptop on purpose (D107): its certificate is the laptop's own, so the browser warning must stay
            # possible to accept; a server sets EAX_HSTS
            record(f"{where}: header {name}", "passed", "off on a laptop by design (D107); a server sets EAX_HSTS", 0)
        elif have is None:
            record(f"{where}: header {name}", bad, "missing", 0)
        elif want and want not in have.lower():
            record(f"{where}: header {name}", bad, f"is {have!r}; expected it to contain {want!r}", 0)
        else:
            record(f"{where}: header {name}", "passed", have[:200], 0)
    server = headers.get("server", "")
    if any(ch.isdigit() for ch in server):
        record(f"{where}: server version hidden", "warning", f"Server header shows a version: {server}", 0)


def check_cookies(cookies: list[str], where: str, record: Record) -> None:
    """Records whether each cookie is Secure, HttpOnly and has SameSite."""
    if not cookies:
        record(f"{where}: cookies", "passed", "no cookie set", 0)
        return
    for c in cookies:
        name = c.split("=", 1)[0].strip()
        flags = [p.strip().lower() for p in c.split(";")[1:]]
        missing = [f for f in ("secure", "httponly") if not any(x.startswith(f) for x in flags)]
        same = next((x for x in flags if x.startswith("samesite")), "")
        if "secure" in missing:
            record(f"{where}: cookie {name}", "failed", "not marked Secure", 0)
        elif "httponly" in missing and not name.upper().startswith("KC_RESTART"):
            record(f"{where}: cookie {name}", "warning", "not HttpOnly (readable by the page's scripts)", 0)
        elif not same:
            record(f"{where}: cookie {name}", "warning", "no SameSite attribute", 0)
        else:
            record(f"{where}: cookie {name}", "passed", "; ".join(flags), 0)


def front_door(record: Record) -> None:
    """The front door's headers and the sign-in page's cookies, asked inside Docker of the proxy container."""
    host = os.environ.get("EAX_HOSTNAME", "localhost")
    proxy = os.environ.get("EAX_TEST_PROXY", "https://proxy")
    realm = os.environ.get("EAX_KEYCLOAK_REALM", "eaexplorer")
    try:
        _status, headers, _ = _get(f"{proxy}/", host)
        check_headers(headers, "front door", record)
        _status, headers, cookies = _get(f"{proxy}/auth/realms/{realm}/protocol/openid-connect/auth?client_id=eax-web"
                                         f"&response_type=code&scope=openid&redirect_uri=https%3A%2F%2F{host}%2F", host)
        check_cookies(cookies, "sign-in page", record)
    except (urllib.error.URLError, OSError) as exc:
        record("front door reachable", "failed", f"the proxy did not answer: {exc}", 0)


def _page(url: str, host: str) -> tuple[int, str, str]:
    """A page through the front door, as it answers (no redirect followed): its status, its text and where it sends."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"Host": host, "User-Agent": "EA Explorer test runner"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _NoRedirect())
    try:
        r = opener.open(req, timeout=30)
        return r.status, r.read(400_000).decode("utf-8", "replace"), r.headers.get("Location", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(400_000).decode("utf-8", "replace"), exc.headers.get("Location", "")


def documents_sign_in(record: Record, page: Callable[[str, str], tuple[int, str, str]] | None = None,
                      password: str | None = None) -> None:
    """Documents' sign-in page shows no password (D932): Mayan showed the administrator it made at first start, with its
    password, to anyone who opened docs.<host>, until that administrator changed it (nobody does: people sign in
    through Keycloak). The page is followed from docs.<host>/ to where Documents sends (its own pages only)."""
    name = "Documents' sign-in page shows no password"
    from .. import services
    if not services.enabled("documents"):
        record(name, "skipped", "Documents is switched off", 0)
        return
    from ..config import secret
    pw = secret("EAX_MAYAN_ADMIN_PASSWORD") if password is None else password
    if not pw:
        record(name, "skipped", "the runner cannot read Documents' administrator password to look for it", 0)
        return
    host = "docs." + os.environ.get("EAX_HOSTNAME", "localhost")
    proxy = os.environ.get("EAX_TEST_PROXY", "https://proxy")
    get = page or _page
    path, seen = "/", []
    try:
        for _ in range(4):                      # / sends to the sign-in page; never off Documents' own host
            status, text, where = get(proxy + path, host)
            seen.append(f"{path} ({status})")
            if pw in text:
                record(name, "failed", f"the administrator's password is on {path}: anyone who opens docs.<host> can "
                       "sign in as Documents' administrator", 0)
                return
            parts = urllib.parse.urlsplit(where) if 300 <= status < 400 and where else None
            if not parts or (parts.netloc and parts.netloc.split(":")[0] != host):
                break
            path = parts.path + (f"?{parts.query}" if parts.query else "")
    except (urllib.error.URLError, OSError) as exc:
        record(name, "failed", f"Documents did not answer through the front door: {exc}", 0)
        return
    record(name, "passed", "no password on " + ", ".join(seen), 0)


def secret_files(record: Record, fetch: Callable[[], dict] | None = None) -> None:
    """No password or key in any container's environment (R6-F1, D745), as the operations helper sees it with docker
    inspect: they reach the containers as files of their own under /run/secrets."""
    def ask() -> dict:
        req = urllib.request.Request(os.environ.get("EAX_OPS_URL", "http://ops:8090") + "/secrets-check",
                                     headers={"X-Ops-Token": os.environ.get("EAX_OPS_TOKEN", "")})
        with httpopen.urlopen(req, timeout=120) as r:
            return json.load(r)
    try:
        v = (fetch or ask)()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        record("secrets: none in a container's environment", "failed", f"the operations helper did not answer: {exc}", 0)
        return
    inside = v.get("in_environment") or {}
    record("secrets: none in a container's environment", "failed" if inside else "passed",
           ("in the environment of: " + "; ".join(f"{c} ({', '.join(n)})" for c, n in inside.items())) if inside
           else f"none of the {v.get('checked', 0)} passwords and keys: each is a file under /run/secrets", 0)


def python_dependencies(record: Record, accepted: list[dict] | None = None) -> None:
    """pip-audit of the API's requirements (needs the internet to read the advisory database); a vulnerability accepted
    until a date not yet past (security_accepted.json, R5.17) is listed, not failed."""
    req = Path("/app/requirements.txt")
    if not req.exists():
        record("Python dependencies (pip-audit)", "skipped", "no requirements.txt in the runner", 0)
        return
    r = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(req), "--format", "json", "--progress-spinner", "off"],
                       capture_output=True, text=True, timeout=900)
    try:
        data = json.loads(r.stdout or "{}")
    except ValueError:
        record("Python dependencies (pip-audit)", "skipped", f"pip-audit could not run: {(r.stderr or '')[-500:]}", 0)
        return
    found = [(d["name"], d["version"], v["id"]) for d in data.get("dependencies", []) for v in d.get("vulns", [])]
    from datetime import date
    ok = {a["id"] for a in accepted or [] if a.get("until", "") >= date.today().isoformat()}
    kept = [f for f in found if f[2] in ok]
    found = [f for f in found if f[2] not in ok]
    if kept and not found:
        record("Python dependencies (pip-audit)", "warning", "accepted for now: " + "; ".join(f"{n} {ver}: {vid}" for n, ver, vid in kept), 0)
        return
    if found:
        record("Python dependencies (pip-audit)", "failed",
               "; ".join(f"{n} {ver}: {vid}" for n, ver, vid in found[:60]), 0)
    else:
        record("Python dependencies (pip-audit)", "passed", f"{len(data.get('dependencies', []))} packages, no known vulnerability", 0)


def read_zap(path: Path, record: Record, name: str = "OWASP ZAP baseline scan") -> None:
    """A ZAP report (zap.json, the baseline; zap-api.json, the signed-in scan, R5.17): High and Medium alerts are listed
    as a warning; the security gate (security_gate.py) fails the run on a High one that is not accepted."""
    if not path.exists():
        record(name, "skipped", "no ZAP report (the scan did not run: see the run's log)", 0)
        return
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    alerts = [a for s in data.get("site", []) for a in s.get("alerts", [])]
    risk = lambda a: int(str(a.get("riskcode", "0")) or 0)  # noqa: E731
    high = [a for a in alerts if risk(a) >= 3]
    medium = [a for a in alerts if risk(a) == 2]
    if high or medium:
        record(name, "warning", "; ".join([f"High: {a.get('alert', '')}" for a in high] + [f"Medium: {a.get('alert', '')}" for a in medium]), 0)
    else:
        record(name, "passed", f"{len(alerts)} low or informational alerts", 0)


def read_trivy(folder: Path, record: Record) -> None:
    """Every trivy-*.json in the run's folder: one result per image, its high and critical findings listed as a warning
    (the security gate fails the run on one with a fix that is not accepted, R5.17)."""
    files = sorted(folder.glob("trivy-*.json"))
    if not files:
        record("image and dependency scans (Trivy)", "skipped", "no Trivy report (the scan did not run: see the run's log)", 0)
        return
    for f in files:
        image = f.stem.removeprefix("trivy-")
        try:
            data = json.loads(f.read_text(encoding="utf-8") or "{}")
        except ValueError:
            record(f"image {image} (Trivy)", "skipped", "the report could not be read", 0)
            continue
        vulns = [v for r in data.get("Results") or [] for v in (r.get("Vulnerabilities") or [])]
        crit = [v for v in vulns if v.get("Severity") == "CRITICAL" and v.get("FixedVersion")]
        high = [v for v in vulns if v.get("Severity") in ("HIGH", "CRITICAL")]
        show = lambda vs: "; ".join(f"{v.get('PkgName')} {v.get('InstalledVersion')}: {v.get('VulnerabilityID')}"  # noqa: E731
                                    + (f" (fixed in {v['FixedVersion']})" if v.get("FixedVersion") else "") for v in vs[:40])
        if crit:
            record(f"image {image} (Trivy)", "warning", f"{len(crit)} critical with a fix: " + show(crit), 0)
        elif high:
            record(f"image {image} (Trivy)", "warning", f"{len(high)} high or critical: " + show(high), 0)
        else:
            record(f"image {image} (Trivy)", "passed", "no high or critical vulnerability", 0)
