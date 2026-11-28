"""Every backup file checked after it is made, and on demand (owner, 28 Nov 2026, 09:08: "after a backup is done its zip
file should be checked"; D968).

A model backup (.eaxbackup.zip) and a project backup (.eaxproject.zip) carry, in their backup.json, a fingerprint of the
file: "files", the SHA-256 of every member but backup.json itself. An application backup's manifest.json carries the
SHA-256 of each model and project file in it. Checking a file:

  * the zip opens and every member's own checksum (CRC) is right (zipfile.testzip);
  * backup.json says what it is, in a format this installation reads, made by this release or an earlier one;
  * every member listed in the fingerprint is there with that SHA-256, and nothing is there that is not listed;
  * a model backup: its package (package.zip) reads as a model package, its entity and relationship counts are those
    backup.json gives, and restore/side.json (to put the model back over itself) reads;
  * a project backup: each project/<table>.json reads as rows, as many as backup.json counts, the project row is the one
    it names; each model backup inside it is checked the same way; each document file is there for each document row
    with a file, except those backup.json lists as missing;
  * an application backup: its manifest reads, every model and project file it lists as backed up is there, has the
    SHA-256 the manifest gives and checks out as above; the organisation part opens.

A file made before fingerprints (before 14.6) is checked for everything but the fingerprint, and says so.
Nothing here writes anything: it only reads.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

MODEL_SUFFIX = ".eaxbackup.zip"
PROJECT_SUFFIX = ".eaxproject.zip"
ORG_SUFFIX = ".eaxorg.zip"


def sha(data: bytes) -> str:
    """The SHA-256 of some bytes, in hex (pure)."""
    return hashlib.sha256(data).hexdigest()


def fingerprint(members: dict[str, bytes]) -> dict[str, str]:
    """The fingerprint written into backup.json: every member's SHA-256, by name, backup.json left out (pure)."""
    return {n: sha(b) for n, b in sorted(members.items()) if n != "backup.json"}


def result(name: str, kind: str) -> dict[str, Any]:
    """An empty check result (pure)."""
    return {"file": name, "kind": kind, "ok": True, "problems": [], "notes": [], "checked": []}


def _bad(out: dict, problem: str) -> None:
    out["problems"].append(problem)
    out["ok"] = False


def _open(data: bytes, out: dict) -> zipfile.ZipFile | None:
    """The zip, its members' CRCs checked; None (said in out) when it is not a readable zip."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        _bad(out, f"it is not a readable zip file ({str(exc)[:120]})")
        return None
    try:
        broken = z.testzip()
    except (zipfile.BadZipFile, OSError, EOFError, ValueError, NotImplementedError) as exc:  # a member cut short
        _bad(out, f"a member cannot be read ({str(exc)[:120]})")
        return z
    if broken:
        _bad(out, f"{broken} is damaged (its checksum is wrong)")
    out["checked"].append("the zip and every member's checksum")
    return z


def _info(z: zipfile.ZipFile, out: dict) -> dict | None:
    try:
        info = json.loads(z.read("backup.json"))
    except KeyError:
        _bad(out, "it has no backup.json, so it is not an EA Explorer backup")
        return None
    except (ValueError, zipfile.BadZipFile, OSError) as exc:
        _bad(out, f"backup.json cannot be read ({str(exc)[:120]})")
        return None
    if not isinstance(info, dict):
        _bad(out, "backup.json is not a JSON object")
        return None
    return info


def _newer(version: str | None) -> bool:
    from .backups import newer_than_here
    return newer_than_here(version)


def _members(z: zipfile.ZipFile, info: dict, out: dict) -> dict[str, bytes]:
    """Every member's bytes; the fingerprint checked when the file has one."""
    data: dict[str, bytes] = {}
    for n in z.namelist():
        if n.endswith("/"):
            continue
        try:
            data[n] = z.read(n)
        except (zipfile.BadZipFile, OSError, EOFError, ValueError) as exc:
            _bad(out, f"{n} cannot be read ({str(exc)[:100]})")
    files = info.get("files")
    if not isinstance(files, dict):
        out["notes"].append("made before backups were fingerprinted (14.6): checked without the fingerprint")
        return data
    have = fingerprint(data)
    for n, want in files.items():
        if n not in have:
            _bad(out, f"{n} is missing (the fingerprint lists it)")
        elif have[n] != want:
            _bad(out, f"{n} has changed since the backup was made (its SHA-256 differs)")
    extra = sorted(set(have) - set(files))
    if extra:
        _bad(out, f"{len(extra)} member(s) not in the fingerprint: {', '.join(extra[:5])}")
    out["checked"].append(f"the fingerprint of {len(files)} member(s)")
    return data


def check_model_bytes(data: bytes, name: str = "model backup") -> dict:
    """A model backup file checked (see the module)."""
    from .backups import FORMAT
    out = result(name, "model")
    z = _open(data, out)
    if z is None:
        return out
    with z:
        info = _info(z, out)
        if info is None:
            return out
        if info.get("format") != FORMAT:
            _bad(out, f"backup.json says {info.get('format')!r}, not {FORMAT}: it is not a model backup")
            return out
        if _newer(info.get("version")):
            _bad(out, f"made by a newer EA Explorer ({info.get('version')}): this installation cannot restore it")
        out["model"] = (info.get("model") or {}).get("name")
        members = _members(z, info, out)
    pkg_bytes = members.get("package.zip")
    if pkg_bytes is None:
        _bad(out, "package.zip (the model itself) is missing")
        return out
    from . import model_ops as mo
    try:
        pkg = mo.read_package(pkg_bytes, "package.zip")
    except Exception as exc:  # noqa: BLE001 - any reason the package does not read is a problem with the file
        _bad(out, f"package.zip does not read as a model package ({str(exc)[:150]})")
        return out
    ents = sum(len(v) for v in (pkg.get("entities") or {}).values())
    rels = len(pkg.get("relationships") or [])
    counts = (pkg.get("manifest") or {}).get("counts") or {}    # what the package says it holds, written with it
    kind = (info.get("model") or {}).get("kind")
    if pkg.get("format") == "zip":
        if counts.get("entities") is not None and int(counts["entities"]) != ents:
            _bad(out, f"package.zip holds {ents} entities; its manifest says {counts['entities']}")
        if counts.get("relationships") is not None and int(counts["relationships"]) != rels:
            _bad(out, f"package.zip holds {rels} relationships; its manifest says {counts['relationships']}")
    if kind != "template" and "restore/side.json" in members:
        try:
            side = json.loads(members["restore/side.json"])
            if not isinstance(side, dict) or "spec" not in side or "snapshot" not in side:
                _bad(out, "restore/side.json has no metamodel or snapshot to put the model back over itself")
        except ValueError as exc:
            _bad(out, f"restore/side.json cannot be read ({str(exc)[:100]})")
    if not (pkg.get("spec") or {}).get("entity_types") and kind == "template":
        out["notes"].append("the root metamodel's package has no entity types")
    out["counts"] = {"entities": ents, "relationships": rels,
                     "entity_types": len((pkg.get("spec") or {}).get("entity_types") or [])}
    out["checked"].append("the model package and its counts")
    return out


def check_project_bytes(data: bytes, name: str = "project backup") -> dict:
    """A project backup file checked (see the module)."""
    from . import project_backup as pb
    out = result(name, "project")
    z = _open(data, out)
    if z is None:
        return out
    with z:
        info = _info(z, out)
        if info is None:
            return out
        if not str(info.get("format", "")).startswith(pb.FORMAT_NAME):
            _bad(out, f"backup.json says {info.get('format')!r}: it is not a project backup")
            return out
        if pb.format_of(info) > pb.FORMAT_VERSION:
            _bad(out, f"made by a newer EA Explorer ({info.get('version')}): this installation cannot restore it")
        out["project"] = (info.get("project") or {}).get("name")
        members = _members(z, info, out)
    counts = info.get("counts") or {}
    rows: dict[str, list] = {}
    for n, b in members.items():
        if n.startswith("project/") and n.endswith(".json"):
            table = n[len("project/"):-len(".json")]
            try:
                rows[table] = json.loads(b)
            except ValueError as exc:
                _bad(out, f"{n} cannot be read ({str(exc)[:100]})")
                continue
            if not isinstance(rows[table], list):
                _bad(out, f"{n} is not a list of rows")
            elif table in counts and int(counts[table]) != len(rows[table]):
                _bad(out, f"{n} holds {len(rows[table])} rows; backup.json says {counts[table]}")
    proj = rows.get("projects") or []
    if len(proj) != 1:
        _bad(out, f"project/projects.json holds {len(proj)} projects, not 1")
    elif str(proj[0].get("guid")) != str((info.get("project") or {}).get("id")):
        _bad(out, "the project in project/projects.json is not the one backup.json names")
    for m in info.get("models") or []:
        if not m.get("in_file"):
            continue
        member = f"models/{m.get('guid')}{MODEL_SUFFIX}"
        if member not in members:
            _bad(out, f"the model {m.get('name') or m.get('guid')} is missing ({member})")
            continue
        inner = check_model_bytes(members[member], member)
        for p in inner["problems"]:
            _bad(out, f"{member}: {p}")
    missing = len(info.get("documents_missing") or [])
    docs = [d for d in rows.get("documents") or [] if d.get("mayan_document_id")]
    files = {n.split("/")[1] for n in members if n.startswith("documents/") and n.count("/") >= 2}
    absent = [d.get("file_name") for d in docs if str(d.get("guid")) not in files]
    if len(absent) > missing:
        _bad(out, f"{len(absent) - missing} document file(s) missing that backup.json does not list as missing: "
                  f"{', '.join(str(a) for a in absent[:5])}")
    out["counts"] = {"tables": len(rows), "rows": sum(len(v) for v in rows.values() if isinstance(v, list)),
                     "documents": len(files), "models": len([m for m in info.get("models") or [] if m.get("in_file")])}
    out["checked"].append("the project's rows, its models and its document files")
    return out


def check_org_bytes(data: bytes, name: str = "organisation part") -> dict:
    """The organisation part of an application backup: it opens and its members read."""
    out = result(name, "organisation")
    z = _open(data, out)
    if z is not None:
        z.close()
    return out


def check_file(path: Path) -> dict:
    """One backup file checked, by its kind (its name's ending)."""
    name = path.name
    try:
        data = path.read_bytes()
    except OSError as exc:
        out = result(name, "file")
        _bad(out, f"it cannot be read ({str(exc)[:120]})")
        return out
    if name.endswith(PROJECT_SUFFIX):
        out = check_project_bytes(data, name)
    elif name.endswith(ORG_SUFFIX):
        out = check_org_bytes(data, name)
    else:
        out = check_model_bytes(data, name)
    out["sha256"] = sha(data)
    out["bytes"] = len(data)
    return out


def check_run(run_dir: Path) -> dict:
    """An application backup (its folder) checked: the manifest, then every file in it."""
    out = result(run_dir.name, "application")
    try:
        man = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _bad(out, f"its manifest.json cannot be read ({str(exc)[:120]})")
        return out
    out["tag"] = man.get("tag")
    if man.get("status") not in ("ok", "partial"):
        _bad(out, f"it did not finish (its status is {man.get('status')!r})")
    out["files"] = []
    for part, folder in (("models", "models"), ("projects", "projects")):
        for item in man.get(part) or []:
            if item.get("status") != "ok":
                continue
            p = run_dir / folder / str(item.get("file") or "")
            if not item.get("file") or not p.is_file():
                _bad(out, f"{item.get('name')}: its file {item.get('file')} is missing")
                continue
            c = check_file(p)
            if item.get("sha256") and item["sha256"] != c["sha256"]:
                c["problems"].append("its SHA-256 differs from the one the manifest gives")
                c["ok"] = False
            out["files"].append({k: c.get(k) for k in ("file", "kind", "ok", "problems", "notes", "sha256")})
            for pr in c["problems"]:
                _bad(out, f"{folder}/{p.name}: {pr}")
    org = man.get("organisation") or {}
    if org.get("status") == "ok" and org.get("file"):
        c = check_file(run_dir / org["file"])
        out["files"].append({k: c.get(k) for k in ("file", "kind", "ok", "problems", "notes", "sha256")})
        for pr in c["problems"]:
            _bad(out, f"{org['file']}: {pr}")
    out["checked"].append(f"the manifest and {len(out['files'])} file(s)")
    return out


def words(c: dict) -> str:
    """One check result in a line or a few (pure)."""
    head = f"{'OK' if c['ok'] else 'NOT OK'}  {c.get('kind')} backup {c.get('file')}"
    lines = [head] + [f"    problem: {p}" for p in c.get("problems") or []] + [f"    note: {n}" for n in c.get("notes") or []]
    return "\n".join(lines)
