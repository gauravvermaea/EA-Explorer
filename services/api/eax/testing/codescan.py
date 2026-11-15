"""Code and secrets scanning (R5.17 (3)): static analysis of the Python code (bandit), secrets committed by mistake (our
own patterns, below) and the licences of the Python dependencies (pip-licenses). Run by the self-test's security suite
over the code in the runner (/app), and by CI nightly over the whole repository:

  python -m eax.testing.codescan <folder to scan> <folder for the reports>

Each writes its report beside the run's other scanners' (bandit.json, secrets.json, licences.json) for the gate
(security_gate.py), and records one result each. Nothing is sent anywhere; a secret found is shown only as where it is
and what kind, never its value."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Record = Callable[[str, str, str, int], None]

# what a secret looks like (kind, pattern); the value itself is never written down
SECRETS: list[tuple[str, re.Pattern]] = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----(?:\\n|\s)+[A-Za-z0-9+/=]{64,}")),
    ("cloud access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("source-host token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("chat token", re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b")),
    ("API secret key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    ("password in a config line", re.compile(r"(?m)^\s*(?:export\s+)?[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN)[A-Z0-9_]*\s*[:=]\s*[\"']?"
                                             r"(?![$<{(])(?!env\b)(?!os\.)(?!re\.)(?!change)[A-Za-z0-9^&*!@#%+/=_.-]{12,}[\"']?\s*$")),
]
# the laptop's documented default (eax deploy and the server template replace it; admin_check warns of it)
KNOWN_DEFAULTS = ("P^55w0rd1234&",)
SKIP_DIRS = {".git", "node_modules", "__pycache__", "work", "persist", "logs", ".venv", "dist", "build"}
SKIP_FILES = re.compile(r"(\.lock|\.min\.js|\.map|\.png|\.jpg|\.jpeg|\.gif|\.ico|\.pdf|\.zip|\.gz|\.woff2?|\.ttf|\.xlsx|\.pptx|\.docx)$", re.I)
# files that hold patterns or made-up examples on purpose (this file, the tests of it, the config templates' placeholders)
ALLOWED = ("codescan.py", "test_r5_17_security.py", "eaxcli/help.txt")
COPYLEFT = re.compile(r"\b(A?GPL|SSPL|EUPL)\b", re.I)


def secrets(root: Path, limit_mb: float = 2.0) -> list[dict]:
    """Secrets committed by mistake under a folder: where and what kind, never the value."""
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(root).parts) or SKIP_FILES.search(p.name):
            continue
        rel = p.relative_to(root).as_posix()
        if rel.endswith(ALLOWED) or p.stat().st_size > limit_mb * 1048576:
            continue
        try:
            body = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # tests' own passwords, the docs' examples and the config templates' documented laptop defaults (changed by eax deploy)
        example = ("tests" in p.relative_to(root).parts or p.suffix in (".md", ".txt", ".example", ".template")
                   or rel.startswith("deploy/templates/"))
        for kind, rx in SECRETS:
            if example and kind == "password in a config line":
                continue
            for m in rx.finditer(body):
                if any(d in m.group(0) for d in KNOWN_DEFAULTS):
                    continue
                line = body.count("\n", 0, m.start()) + 1
                out.append({"id": f"secret:{kind.replace(' ', '-')}", "severity": "high", "title": f"a {kind}",
                            "where": f"{rel}:{line}", "fix": True})
    return out


def bandit(root: Path, out: Path) -> dict | None:
    """bandit's static analysis of the Python code, its report kept; None when bandit is not there."""
    r = subprocess.run([sys.executable, "-m", "bandit", "-r", str(root), "-f", "json", "-q", "-x",
                        ",".join(f"*/{d}/*" for d in ("tests", "node_modules", ".git"))], capture_output=True, text=True, timeout=1800)
    try:
        data = json.loads(r.stdout or "")
    except ValueError:
        return None
    out.write_text(json.dumps(data), encoding="utf-8")
    return data


def licences() -> list[dict] | None:
    """The Python dependencies with a copyleft licence; None when pip-licenses is not there."""
    r = subprocess.run([sys.executable, "-m", "piplicenses", "--format", "json", "--with-system"], capture_output=True, text=True,
                       timeout=600)
    try:
        rows = json.loads(r.stdout or "")
    except ValueError:
        return None
    return [{"id": f"licence:{x['Name']}", "severity": "medium", "title": f"{x['Name']} {x.get('Version', '')}: {x.get('License')}",
             "where": "Python dependencies", "fix": True} for x in rows if COPYLEFT.search(str(x.get("License") or ""))]


def run(root: Path, out: Path, record: Record) -> None:
    """The three scans, their reports in `out` and one result each (the gate decides what fails)."""
    out.mkdir(parents=True, exist_ok=True)
    data = bandit(root, out / "bandit.json")
    if data is None:
        record("code: Python static analysis (bandit)", "skipped", "bandit is not in the test runner (rebuild it: eax test --build)", 0)
    else:
        bad = [r for r in data.get("results") or [] if r.get("issue_severity") == "HIGH" and r.get("issue_confidence") in ("HIGH", "MEDIUM")]
        medium = [r for r in data.get("results") or [] if r.get("issue_severity") == "MEDIUM"]
        record("code: Python static analysis (bandit)", "warning" if bad or medium else "passed",
               f"{len(bad)} high, {len(medium)} medium" + (": " + "; ".join(f"{r['test_id']} {Path(r['filename']).name}:{r['line_number']}"
                                                                           for r in bad[:20]) if bad else ""), 0)
    found = secrets(root)
    (out / "secrets.json").write_text(json.dumps(found), encoding="utf-8")
    record("secrets committed by mistake", "warning" if found else "passed",
           f"{len(found)} found (where, not what): " + "; ".join(f"{f['title']} at {f['where']}" for f in found[:20]) if found
           else "none in the code", 0)
    lic = licences()
    if lic is None:
        record("licences of the Python dependencies", "skipped", "pip-licenses is not in the test runner", 0)
    else:
        (out / "licences.json").write_text(json.dumps(lic), encoding="utf-8")
        record("licences of the Python dependencies", "warning" if lic else "passed",
               "copyleft: " + "; ".join(x["title"] for x in lic[:20]) if lic else "no copyleft licence", 0)


def main(argv: list[str]) -> int:
    """python -m eax.testing.codescan <folder> <reports>: the scans and the gate (CI); 1 when the gate fails."""
    root, out = Path(argv[0] if argv else "."), Path(argv[1] if len(argv) > 1 else "security-reports")
    results = []
    run(root, out, lambda n, o, d, _ms: results.append((n, o, d)) or print(f"{o.upper():<8} {n}: {d[:300]}"))
    from . import security_gate as sg
    g = sg.gate(sg.collect(out), sg.accepted())
    for f in g["failing"]:
        print(f"FAILING  {f['source']} {f['id']} {f['where']}")
    return 1 if g["failing"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
