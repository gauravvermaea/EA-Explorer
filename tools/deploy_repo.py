"""The deploy repository, made from this one (Release 14.8.1, D973, D976; owner, 27 Nov 2026: "From our github repo we
still create docker containers and thats simply just how to deploy"; 28 Nov 2026: "Remember we will need both the
repos to point to each other").

    python tools/deploy_repo.py --to ../EA-Explorer-Deploy          write it (only the files it manages)
    python tools/deploy_repo.py --to ../EA-Explorer-Deploy --check  say what would change, change nothing

Everything in the deploy repository is made here, so the two never disagree: what an installation needs to run (the
eax command and its launchers, the settings files the third-party images read, the DR tools, the version), a compose
file that runs the published images instead of building them, and the deploy repository's own pages (deploy/repo/: its
README, guides, the deploy page and the folders for advanced users). Only git's files are taken (never work/, a local
TOGAF file or a password). The files it manages are listed in its MANIFEST.txt; a file of the deploy repository that is
not in the list (its .git, its LICENSE) is never touched.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_REPO = "https://github.com/gauravvermaea/EA-Explorer"
DEPLOY_REPO = "https://github.com/gauravvermaea/EA-Explorer-Deploy"
REGISTRY = "ghcr.io/gauravvermaea/eaexplorer-"
OURS = ("api", "web", "backup", "library", "views", "ops", "drawio", "superset", "jenkins", "testrunner", "eax")

# what is copied as it is (git's files only)
COPY = ["eaxcli", "dr", "eax.sh", "eax.ps1", "eax.cmd", "eaxpy.py", "eaxpy.sh", "eaxpy.ps1", "eaxpy.cmd",
        "eax-deploy.sh", "eax-deploy.ps1", "eax-deploy.cmd", "services/api/version.toml",
        "library/templates/togaf/.gitignore", "library/templates/togaf/README.md", "library/templates/own/README.md"]
# never copied, even when git has them: The Open Group's TOGAF templates (their licence forbids redistributing them)
NEVER = re.compile(r"^library/templates/togaf/(?!\.gitignore$|README\.md$)|\.(docx|xlsx|pptx|pdf)$", re.IGNORECASE)
DEPLOY_SKIP = ("deploy/release/", "deploy/eax/", "deploy/repo/")   # how images are made, and the deploy repo's own pages
# a mount of what the published images hold (D973): left out of the deploy repository's compose file
BAKED = re.compile(r"^\s*-\s*\./[^:]+:(/data/docs[^:\s]*|/data/ea-explorer-templates|/data/industry-packs|/testdata)(:ro)?\s*(#.*)?$")


def git_files(prefix: str) -> list[str]:
    """git's files under a path (or the file itself)."""
    out = subprocess.run(["git", "ls-files", "-z", "--", prefix], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p and not NEVER.search(p)]


def compose_for_deploy(text: str) -> str:
    """docker-compose.yml for an installation from the deploy repository (pure): every build: section out (our images are
    pulled, D973), never pulled from Docker Hub by their local names (pull_policy: never; eax images pull names them),
    and no mount of what the published images hold."""
    out: list[str] = ["# Made by tools/deploy_repo.py from EA Explorer's docker-compose.yml: change it there, not here.",
                      "# Our images (eaexplorer/<image>) are pulled from the registry and named by eax images pull (eax up",
                      "# does it); they are never built here. See guides/images.md for what each image is."]
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(\s*)build:\s*(\S.*)?$", line)
        if m:                                            # the build section and everything indented under it
            indent = len(m.group(1))
            i += 1
            while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
                i += 1
            continue
        if BAKED.match(line):
            i += 1
            continue
        out.append(line)
        im = re.match(r"^(\s*)image:\s*eaexplorer/(\w+):", line)
        if im and im.group(2) in OURS:
            out.append(f"{im.group(1)}pull_policy: never")
        i += 1
    return "\n".join(out) + "\n"


def template_for_deploy(text: str, version: str) -> str:
    """A case template (deploy/templates/*.env) for the deploy repository (pure): this release's version, and our images
    from the registry."""
    text = re.sub(r"^EAX_VERSION=.*$", f"EAX_VERSION={version}", text, flags=re.M)
    extra = ("\n# Made from the deploy repository (D973): our images are pulled from the registry, never built here.\n"
             "EAX_IMAGES_FROM=registry\n"
             f"EAX_IMAGES_REGISTRY={REGISTRY}\n")
    return text.rstrip("\n") + "\n" + extra


def version() -> str:
    m = re.search(r'^version = "(.*)"', (ROOT / "services/api/version.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "dev"


def plan() -> dict[str, bytes]:
    """Every file of the deploy repository it manages: path -> content."""
    v = version()
    files: dict[str, bytes] = {}
    for prefix in COPY:
        for f in git_files(prefix):
            if "__pycache__" not in f:
                files[f] = (ROOT / f).read_bytes()
    for f in git_files("deploy"):
        if f.startswith(DEPLOY_SKIP):
            continue
        data = (ROOT / f).read_bytes()
        if f.startswith("deploy/templates/") and f.endswith(".env"):
            data = template_for_deploy(data.decode("utf-8"), v).encode("utf-8")
        files[f] = data
    files["docker-compose.yml"] = compose_for_deploy((ROOT / "docker-compose.yml").read_text(encoding="utf-8")).encode("utf-8")
    for f in git_files("deploy/compose"):
        if f.endswith(".yml"):
            files[f] = compose_for_deploy((ROOT / f).read_text(encoding="utf-8")).encode("utf-8")
    jenkins = "deploy/jenkins/docker-compose.jenkins.yml"
    if (ROOT / jenkins).exists():
        files[jenkins] = compose_for_deploy((ROOT / jenkins).read_text(encoding="utf-8")).encode("utf-8")
    files["guides/images.md"] = (ROOT / "docs/images.md").read_bytes()
    files["releases/LATEST.md"] = (ROOT / "releases" / f"{v}.md").read_bytes() if (ROOT / "releases" / f"{v}.md").exists() \
        else f"# EA Explorer {v}\n\nThe release notes: {CODE_REPO}/tree/main/releases\n".encode()
    for f in git_files("deploy/repo"):
        rel = f[len("deploy/repo/"):]
        data = (ROOT / f).read_bytes()
        if rel.endswith((".md", ".html", ".sh", ".ps1", ".cmd", ".txt", ".yml")) or rel in ("eax", ".gitignore"):
            text = data.decode("utf-8").replace("{{VERSION}}", v).replace("{{CODE_REPO}}", CODE_REPO) \
                .replace("{{DEPLOY_REPO}}", DEPLOY_REPO).replace("{{REGISTRY}}", REGISTRY)
            if rel.endswith(".cmd"):                     # cmd.exe reads a batch file with Windows line ends only
                text = text.replace("\r\n", "\n").replace("\n", "\r\n")
            data = text.encode("utf-8")
        files[rel] = data
    files["MANIFEST.txt"] = ("# The files tools/deploy_repo.py made, from EA Explorer " + v + " (" + CODE_REPO + ").\n"
                             "# Change them there; a file not listed here (.git, LICENSE) is this repository's own.\n"
                             + "".join(f"{hashlib.sha256(files[p]).hexdigest()[:16]}  {p}\n" for p in sorted(files))).encode()
    return files


def write(target: Path, files: dict[str, bytes], check: bool = False) -> list[str]:
    """Writes the files into the deploy repository; removes the files it made before that are no longer made. Returns
    what changed (added, changed, removed)."""
    before = set()
    man = target / "MANIFEST.txt"
    if man.exists():
        before = {ln.split("  ", 1)[1] for ln in man.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")}
    changed = []
    for rel, data in sorted(files.items()):
        p = target / rel
        if not p.exists():
            changed.append(f"added    {rel}")
        elif p.read_bytes() != data:
            changed.append(f"changed  {rel}")
        else:
            continue
        if not check:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            if rel in ("eax",) or rel.endswith(".sh"):
                p.chmod(0o755)
    for rel in sorted(before - set(files)):
        changed.append(f"removed  {rel}")
        if not check and (target / rel).is_file():
            (target / rel).unlink()
    return changed


def main(argv: list[str]) -> int:
    """python tools/deploy_repo.py --to <folder> [--check]."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--to", required=True, help="the deploy repository's folder")
    ap.add_argument("--check", action="store_true", help="say what would change, change nothing")
    a = ap.parse_args(argv)
    target = Path(a.to).resolve()
    if target == ROOT or ROOT in target.parents:
        print("The deploy repository is another folder, not this one or inside it.")
        return 2
    if not (target / ".git").exists() and not a.check:
        print(f"{target} is not a git repository: clone {DEPLOY_REPO} there first.")
        return 2
    changed = write(target, plan(), a.check)
    for c in changed:
        print(c)
    print(f"{len(changed)} file(s) {'would change' if a.check else 'changed'} in {target}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
