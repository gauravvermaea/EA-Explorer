"""eax dr-pack <folder>: a DR pack in one command (R5.6-B2; owner, 16 Nov 2026, 22:07: the DR pack is the backup, the
version number and the env file; 22:12: "can the DR pack that is generated have some sort of has or fingerprints, which
can compare after DR restore to ensure everything was done in DR tool?"; 22:13: "One command: eax dr-pack"; 22:44:
"Shouldnt DR pack also have the code ... why depend upon git? What if the server where its getting DR doesnt have github
access": the pack carries the code, so eax-dr needs no GitHub; code only, no Docker images, agreed 22:46).

On the running installation, asking nothing, one step after another:
  1. the installation runs; the folder is new or empty and outside the installation's folder
  2. the maintenance page on and the background paused, then waited for until it has finished what it was doing (a
     project's documents being made, for one), so nothing changes between the next two steps
  3. the fingerprint of every table of every database and every file of every file set (fingerprint.json)
  4. a full infrastructure backup (tag dr-pack)
  5. the maintenance page off and the background back (also when a step failed)
  6. the pack written: backup/<name>/, eaexplorer.env, VERSION.txt, fingerprint.json, code/ (the code that runs here,
     with CODE.sha256), the dr folder (the DR tool), RESTORE.txt (the eax-dr command for this pack, Windows and Linux),
     then PACK.sha256: a checksum of every file
  7. the pack checked: every file against PACK.sha256, the backup against its own SHA256SUMS

dr/eax-dr -Pack <folder> then checks PACK.sha256 before it touches anything, builds from the pack's code (no GitHub), and
after the restore takes the same fingerprint on the new machine and compares it with fingerprint.json, table by table
and file by file. The new machine still needs Docker and what building the images downloads (Docker Hub, the Python and
Node packages)."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

from . import drill as DRL
from .core import ROOT, WORK, Failure, log_only, say, version

DR_FILES = ("eax-dr.ps1", "eax-dr.sh", "dr-common.ps1", "dr-common.sh", "eax-drill.ps1", "eax-drill.sh", "README.md")


def sha256(path: Path) -> str:
    """A file's sha256."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_sums(pack: Path) -> int:
    """PACK.sha256: every file of the pack but itself, in sha256sum's format, paths with / (pure but for the files)."""
    lines = [f"{sha256(p)}  {p.relative_to(pack).as_posix()}" for p in sorted(pack.rglob("*"))
             if p.is_file() and p.name != "PACK.sha256"]
    (pack / "PACK.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(lines)


def check_sums(pack: Path) -> list[str]:
    """What does not match PACK.sha256 (missing or changed files); empty when the pack is whole."""
    bad = []
    for line in (pack / "PACK.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, rel = line.partition("  ")
        p = pack / rel
        if not p.is_file():
            bad.append(f"{rel}: missing")
        elif sha256(p) != digest:
            bad.append(f"{rel}: changed")
    return bad


def restore_text(pack: Path, name: str, ver: str) -> str:
    """RESTORE.txt: how to rebuild from this pack (pure)."""
    return (f"EA Explorer DR pack: version {ver}, backup {name}.\n"
            "Copy this whole folder to the new machine (Docker running), then from its dr folder:\n\n"
            "  Windows:          .\\eax-dr.ps1 -Pack .. -Install C:\\EA-Explorer\n"
            "  Linux and macOS:  ./eax-dr.sh --pack .. --install /opt/ea-explorer\n\n"
            "eax-dr checks every file of the pack (PACK.sha256), builds v" + ver + " from the pack's code (code/, no GitHub), restores\n"
            "the backup and compares every table and file with fingerprint.json. Building still downloads the images' parts\n"
            "(Docker Hub, the Python and Node packages). Documentation: Disaster recovery: the DR pack and the DR tool.\n"
            "The env file holds every password and key: keep this pack where only those who may rebuild EA Explorer reach it.\n")


def make(folder: str) -> int:
    """eax dr-pack <folder> (see the module)."""
    pack = Path(folder).expanduser().resolve()
    if pack == ROOT or ROOT in pack.parents:
        raise Failure(f"{pack} is inside the installation's folder: give a folder outside it (a disk or share you keep "
                      "away from this machine).")
    if pack.exists() and any(pack.iterdir()):
        raise Failure(f"{pack} is not empty: give a new or empty folder.")
    r = DRL.running()
    if not r.get("running"):
        raise Failure(r.get("error") or "EA Explorer is not running.")
    ver = version()
    say(f"Making a DR pack of EA Explorer {ver} in {pack}. The maintenance page is on for a few minutes.", "cyan")
    pack.mkdir(parents=True, exist_ok=True)
    fp = pack / "fingerprint.json"
    q = DRL._ops("quiet", "on")
    if q.get("error"):
        raise Failure(f"the maintenance page could not be put on: {q['error']}")
    try:
        say("> the background finishing what it was doing")
        w = DRL._api("idle", {})
        if w.get("error"):
            raise Failure(w["error"])
        say("> the fingerprint of every table and file")
        f = DRL._ops("fingerprint")
        if f.get("error"):
            raise Failure(f"the fingerprint: {f['error']}")
        fp.write_text(json.dumps(f), encoding="utf-8")
        say(f"  {len(f.get('tables', {}))} tables, {len(f.get('files', {}))} files")
        say("> a full infrastructure backup")
        b = DRL._ops("backup", "dr-pack")
        if b.get("error"):
            raise Failure(f"the backup: {b['error']}")
        say(f"  {b['name']}, {round((b.get('bytes') or 0) / 1e9, 2)} GB in {b.get('seconds')} s")
    finally:
        q = DRL._ops("quiet", "off")
        say("> the maintenance page off and the background back" + (f": {q['error']}" if q.get("error") else ""))
    name = b["name"]
    src = Path(DRL.info()["backups"]) / name
    say("> the pack written")
    shutil.copytree(src, pack / "backup" / name)
    shutil.copy2(WORK / "eaexplorer.env", pack / "eaexplorer.env")
    (pack / "VERSION.txt").write_text(ver + "\n", encoding="utf-8", newline="\n")
    say("> the code")
    c = DRL.copy_code(pack / "code", ROOT)
    if c["version"] != ver:
        raise Failure(f"the code copied says version {c['version']}, the installation {ver}")
    say(f"  {c['files']} files, version {c['version']}")
    (pack / "dr").mkdir()
    for f_ in DR_FILES:
        if (ROOT / "dr" / f_).exists():
            shutil.copy2(ROOT / "dr" / f_, pack / "dr" / f_)
    (pack / "RESTORE.txt").write_text(restore_text(pack, name, ver), encoding="utf-8")
    n = write_sums(pack)
    say("> the pack checked")
    bad = check_sums(pack)
    whole = _backup_whole(pack / "backup" / name)
    if bad or whole:
        raise Failure("the pack is not whole: " + "; ".join((bad + whole)[:10]))
    log_only(f"dr-pack: {pack} ({name}, {ver}, {n} files)")
    say(f"\nDR pack ready: {pack}\n  version {ver}, backup {name}, {n} files, each in PACK.sha256; fingerprint.json for the "
        "check after the restore; the code, so no GitHub is needed.\n  Keep it away from this machine: it holds every password and all the data. "
        "RESTORE.txt says how to use it.", "green")
    return 0


def _backup_whole(folder: Path) -> list[str]:
    """What does not match the backup's own SHA256SUMS."""
    bad = []
    for line in (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, _, rel = line.partition("  ")
        rel = rel.strip().lstrip("*").removeprefix("./")
        if rel and (not (folder / rel).is_file() or sha256(folder / rel) != digest.strip()):
            bad.append(f"backup/{folder.name}/{rel}: missing or changed")
    return bad


def main(args: list[str]) -> int:
    """eax dr-pack <folder>."""
    if not args:
        raise Failure("Give the folder for the DR pack: eax dr-pack <folder> (new or empty, outside work/).")
    return make(args[0])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
