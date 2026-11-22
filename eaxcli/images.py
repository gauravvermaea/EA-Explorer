"""eax images (R9.12; owner, 22 Nov 2026, 07:49: "this should be checked every 3 months when we check latest images.
Add a schedule to check for latets images every 3 months and we will tackle it there"; D841, D843).

  eax images [check] [--no-tell]   every image EA Explorer uses, the one in use and whether a newer one is published

What it looks at: each image the installation runs or builds on. For our own images (api, web, ops and the rest, built
here) that is the image each Dockerfile starts FROM; for the others (PostgreSQL, Keycloak, Superset and the rest) the
image itself. For each: the one on this machine (its digest and when it was made) against the one published now under
the same name (`docker buildx imagetools inspect`, which reads the registry and downloads nothing), and the fixable
high and critical findings the last security test found in it (security-findings.json of the newest test run).

Nothing is changed: taking the newer images is a deliberate step afterwards (a clean restart fetches them and builds on
them; then eax test full). A schedule runs this on the first of every third month (System Admin > Command centre >
Schedules); when it finds something newer, the Super Admins and IT Admins are told, with the report
(work/images/check-<time>.md).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from .core import EAX, ROOT, WORK, Failure, capture, compose_args, say, setting

FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)


def from_lines(dockerfile: str) -> list[str]:
    """The images a Dockerfile builds on (pure): every FROM, leaving out its own stages and anything with a variable."""
    stages: set[str] = set()
    out: list[str] = []
    for line in dockerfile.splitlines():
        m = FROM.match(line)
        if not m:
            continue
        ref, alias = m.group(1), m.group(2)
        if ref.lower() not in stages and "$" not in ref and ref.lower() != "scratch" and ref not in out:
            out.append(ref)
        if alias:
            stages.add(alias.lower())
    return out


def images_of(config: dict, root: Path = ROOT) -> list[dict]:
    """Every image from `docker compose config` (pure but for reading the Dockerfiles): {ref, kind: base|image,
    services}. A service built here gives its Dockerfile's FROM images (base); the others their own image."""
    found: dict[str, dict] = {}
    for name, svc in sorted((config.get("services") or {}).items()):
        build = svc.get("build")
        refs: list[tuple[str, str]] = []
        if build:
            ctx = Path(build.get("context") or ".") if isinstance(build, dict) else Path(build)
            ctx = ctx if ctx.is_absolute() else root / ctx
            df = ctx / ((build.get("dockerfile") if isinstance(build, dict) else None) or "Dockerfile")
            try:
                refs = [(r, "base") for r in from_lines(df.read_text(encoding="utf-8"))]
            except OSError:
                refs = []
        elif svc.get("image"):
            refs = [(svc["image"], "image")]
        for ref, kind in refs:
            found.setdefault(ref, {"ref": ref, "kind": kind, "services": []})["services"].append(name)
    return list(found.values())


def _digest_of(text: str) -> str:
    m = re.search(r"sha256:[0-9a-f]{64}", text or "")
    return m.group(0) if m else ""


def local(ref: str, run=capture) -> dict:
    """The image on this machine: its registry digests and when it was made (empty when it is not here)."""
    code, out = run(["docker", "image", "inspect", ref, "--format", "{{json .RepoDigests}}|{{.Created}}"])
    if code != 0:
        return {}
    digests, _, created = out.strip().partition("|")
    try:
        names = json.loads(digests) or []
    except ValueError:
        names = []
    return {"digests": [_digest_of(x) for x in names if _digest_of(x)], "created": created.strip()[:19]}


def published(ref: str, run=capture) -> str:
    """The digest published now under the same name (read from the registry, nothing downloaded); "" when unknown."""
    code, out = run(["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest}}"])
    if code != 0:
        return ""
    try:
        return str(json.loads(out).get("digest") or "")
    except ValueError:
        return _digest_of(out)


def repo(ref: str) -> str:
    """An image's name without its tag or digest (pure): postgres:16-alpine and postgres@sha256:... are postgres."""
    ref = ref.split("@")[0]
    head, _, last = ref.rpartition("/")
    return (head + "/" if head else "") + last.split(":")[0]


def fixable(findings: list[dict], ref: str) -> int:
    """How many fixable high or critical findings the last security test found in an image (pure); our own images are
    matched by their service's name (eaexplorer/<service>)."""
    name = repo(ref)
    return sum(1 for f in findings if f.get("source") == "trivy" and f.get("fix") and f.get("severity") in ("high", "critical")
               and repo(str(f.get("where", "")).removeprefix("image ")) == name)


def last_findings(work: Path = WORK) -> tuple[list[dict], str]:
    """The newest test run's security findings, and the run's folder name ("" when there is none)."""
    runs = sorted((p for p in (work / "tests").glob("*/security-findings.json")), key=lambda p: p.stat().st_mtime)
    if not runs:
        return [], ""
    try:
        return json.loads(runs[-1].read_text(encoding="utf-8")).get("findings") or [], runs[-1].parent.name
    except (OSError, ValueError):
        return [], runs[-1].parent.name


def status(here: dict, latest: str) -> str:
    """newer, current, not here (never fetched) or unknown (the registry not reached) (pure)."""
    if not here:
        return "not here"
    if not latest:
        return "unknown"
    return "current" if latest in here.get("digests", []) else "newer"


def check(images: list[dict], findings: list[dict], run=capture) -> list[dict]:
    """Each image looked at: what is here, what is published, the fixable findings."""
    rows = []
    for im in images:
        here = local(im["ref"], run)
        latest = published(im["ref"], run)
        rows.append({**im, "created": here.get("created", ""), "status": status(here, latest),
                     "fixable": fixable(findings, im["ref"]) if im["kind"] == "image" else
                     sum(fixable(findings, f"eaexplorer/{s}") for s in im["services"])})
    return rows


def report(rows: list[dict], findings_from: str, folder: Path) -> Path:
    """work/images/check-<time>.json and .md: a line an image, the newer ones first."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    order = {"newer": 0, "unknown": 1, "not here": 2, "current": 3}
    rows = sorted(rows, key=lambda r: (order.get(r["status"], 9), r["ref"]))
    newer = [r for r in rows if r["status"] == "newer"]
    (folder / f"check-{stamp}.json").write_text(json.dumps({"at": stamp, "findings_from": findings_from, "images": rows},
                                                           indent=1), encoding="utf-8")
    md = ["# Images: what is in use and what is published", "",
          f"{len(newer)} of {len(rows)} images have a newer one published. Fixable high and critical findings from the "
          f"security test of {findings_from or '(no test run yet)'}. Nothing was changed: to take the newer images, "
          f"`{EAX} clean-restart` (it fetches them and builds on them), then `{EAX} test full`.", "",
          "| Image | Used by | On this machine since | Published | Fixable findings |", "|---|---|---|---|---|"]
    md += [f"| `{r['ref']}`{' (base of ours)' if r['kind'] == 'base' else ''} | {', '.join(r['services'])} | "
           f"{r['created'] or '-'} | {r['status']} | {r['fixable']} |" for r in rows]
    path = folder / f"check-{stamp}.md"
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return path


def tell(rows: list[dict], path: Path, post=None) -> bool:
    """The Super Admins and IT Admins told when something newer is published (through the API, as the operations
    helper tells them of containers); False when the API cannot be reached from here (the report stays)."""
    newer = [r for r in rows if r["status"] == "newer"]
    if not newer:
        return False
    event = {"event": "reminder", "service": "images", "kind": "images",
             "text": f"Newer images published: {len(newer)} of {len(rows)} (the 3-monthly image check)",
             "detail": "; ".join(f"{r['ref']} ({r['fixable']} fixable findings)" for r in newer)[:1500]
             + f". The report: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}."}
    if post:
        return post(event)
    token = setting("EAX_OPS_TOKEN", "")
    url = os.environ.get("EAX_API_URL", "http://api:8000") + "/api/v1/internal/container-alerts"
    req = urllib.request.Request(url, data=json.dumps({"events": [event]}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Ops-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 - the API on EA Explorer's own network
            return r.status == 200
    except OSError:
        return False


def main(argv: list[str], run=capture) -> int:
    """eax images [check] [--no-tell]."""
    words = [a for a in argv if not a.startswith("--")]
    if words and words[0] != "check":
        raise Failure(f"{EAX} images [check] [--no-tell]")
    code, out = run(compose_args(["--profile", "test", "--profile", "platform", "config", "--format", "json"]))
    if code != 0:
        raise Failure(f"docker compose config failed: {out.strip()[-300:]}")
    images = images_of(json.loads(out))
    findings, findings_from = last_findings()
    say(f"Looking at {len(images)} images (nothing is downloaded or changed)...")
    rows = check(images, findings, run)
    path = report(rows, findings_from, WORK / "images")
    for r in sorted(rows, key=lambda r: r["status"] != "newer"):
        colour = "yellow" if r["status"] == "newer" else "red" if r["status"] == "unknown" else None
        say(f"  {r['status']:9} {r['ref']}  ({', '.join(r['services'])}; {r['fixable']} fixable findings)",
            *([colour] if colour else []))
    newer = sum(1 for r in rows if r["status"] == "newer")
    say(f"{newer} of {len(rows)} images have a newer one published. The report: {path}")
    if "--no-tell" not in argv and newer:
        say("The Super Admins and IT Admins were told." if tell(rows, path) else
            "The admins could not be told from here (the report stays); a schedule run tells them.")
    return 0

