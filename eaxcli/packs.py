"""eax packs (phase 39; owner 10 Nov 2026, D546 to D549): the industry packs.

  packs load [folder]   load packs into Documents now: the shipped ones (library/industry-packs; also done at every
                        start) or another folder on this computer (copied into the api container first)
  packs reload          the same as load (the shipped packs)
  packs status          each industry's pack: how many files are in Documents
  packs auto            what up, run, restart, clean-restart and clean-run do by themselves before starting (D584):
                        copy what is new or changed from the pack sources into library/industry-packs; quick
                        when nothing changed; nothing to do when no source folder is there
  packs source [folder...]
                        show, set or (with --clear) forget the pack source folders (kept in persist/settings.json)
  packs collect [source...]
                        copy the owner's industry packs from folders on this computer into library/industry-packs, ready
                        to commit: one folder per industry, the "complete set" zips opened, duplicates (same checksum)
                        kept once, files marked not for AI use left out and listed, files over 50 MB split into
                        parts below 45 MB with a manifest (no Git LFS). Without sources: the owner's folders
                        (Enterprise_Architecture\\Industry Specific Guidance and Sample_Repo\\Metamodels_And_Views_by_Industry
                        and Sample_Repo\\MetaModel_And_Views in the home folder)

One Python program for every form (D331, D500): eax.ps1 and eax.sh hand `packs` to eaxpy.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from .core import EAX, ROOT, Failure, say

DEST = ROOT / "library" / "industry-packs"
AI_MARK = re.compile(r"NOT\s+FOR\s+AI\s+USE|AI\s+USE\s+RESTRICTION", re.IGNORECASE)
SPLIT_LIMIT = 50 * 1024 * 1024
PART_SIZE = 45 * 1024 * 1024

# folder or file-name words -> the industry folder in library/industry-packs
FOLDERS = [("health", "Healthcare"), ("pharma", "Pharmaceuticals"), ("manufactur", "Manufacturing"), ("retail", "Retail"),
           ("banking", "Banking"), ("insurance", "Insurance"), ("meridian", "Insurance"), ("government", "Government"),
           ("logistic", "Logistics"), ("mining", "Minerals_and_Mining"), ("mineral", "Minerals_and_Mining"),
           ("telecom", "Telecommunications")]
WANTED = (".pdf", ".xlsx", ".xlsm", ".pptx")


def default_sources() -> list[Path]:
    """Where industry packs are looked for by default."""
    home = Path.home() / "Enterprise_Architecture"
    return [home / "Industry Specific Guidance", home / "Sample_Repo" / "Metamodels_And_Views_by_Industry",
            home / "Sample_Repo" / "MetaModel_And_Views"]


def industry_for(path: Path) -> str | None:
    """By the nearest folder or the file's own name (a flat folder of <Industry>_TOGAF_Metamodel.xlsx files)."""
    for part in [path.name, *[p.name for p in path.parents]]:
        low = part.lower()
        for word, folder in FOLDERS:
            if word in low:
                return folder
    return None


def clean_name(name: str, industry: str) -> str:
    """'00 READ ME FIRST - what is in this set.pdf' -> 'Retail - read me first (what is in this set).pdf'."""
    m = re.match(r"^\d+\s+READ ME FIRST\s*-", name, re.IGNORECASE)   # D804: the rest by string work
    stem, dot, ext = name[m.end():].rpartition(".") if m else ("", "", "")
    if m and dot and ext and all(c.isalnum() or c == "_" for c in ext):
        return f"{industry.replace('_', ' ')} - read me first ({stem.strip()}).{ext.lower()}"
    return re.sub(r"\s+", " ", name).strip()


FIRST_PAGE_CHARS = 3000                # the same as services/api/eax/industry_packs.py; a page's worth of text, where a file has no pages (Word, a sheet, plain text)


def _xml_text(xml: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)).strip()


def _first_sheet(z: zipfile.ZipFile, names: list[str]) -> str:
    """A workbook's first sheet: its own words and the shared words its cells use, in cell order."""
    sheets = sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                    key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
    shared = (re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8", "ignore"), re.DOTALL)
              if "xl/sharedStrings.xml" in names else [])
    if not sheets:
        return " ".join(_xml_text(s) for s in shared[:200])
    out, size = [], 0
    for cell, kind in re.findall(r"<c\b([^>]*?)(?:/>|>(.*?)</c>)", z.read(sheets[0]).decode("utf-8", "ignore"), re.DOTALL):
        v = re.search(r"<v>(\d+)</v>", kind or "")
        word = _xml_text(shared[int(v.group(1))]) if 't="s"' in cell and v and int(v.group(1)) < len(shared) else _xml_text(kind or "")
        if word:
            out.append(word)
            size += len(word)
            if size >= FIRST_PAGE_CHARS:
                break
    return " ".join(out)


def first_page_text(name: str, data: bytes) -> str:
    """The first page of a file, for the "not for AI use" check (owner, 23 Nov 2026: "no file should be checked in
    full ... only check 1st page of every document"): a PDF's first page; a slide deck's first slide; a workbook's
    first sheet; a Word file's headers, footers and opening text; anything else its opening text. Reading every page
    of the 500-page pack books took about ten minutes."""
    ext = name.lower().rpartition(".")[2]
    try:
        if ext in ("xlsx", "xlsm", "pptx", "docx"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
                if ext == "pptx" and "ppt/slides/slide1.xml" in names:
                    return _xml_text(z.read("ppt/slides/slide1.xml").decode("utf-8", "ignore"))[:FIRST_PAGE_CHARS]
                if ext in ("xlsx", "xlsm"):
                    return _first_sheet(z, names)[:FIRST_PAGE_CHARS]
                if ext == "docx" and "word/document.xml" in names:
                    edges = [n for n in names if re.fullmatch(r"word/(header|footer)\d*\.xml", n)]
                    head = " ".join(_xml_text(z.read(n).decode("utf-8", "ignore")) for n in edges)
                    return head + " " + _xml_text(z.read("word/document.xml").decode("utf-8", "ignore"))[:FIRST_PAGE_CHARS]
                xml = [n for n in names if n.endswith(".xml")]
                return " ".join(_xml_text(z.read(n).decode("utf-8", "ignore")) for n in xml)[:FIRST_PAGE_CHARS]
        if ext == "pdf":
            import pypdf
            pages = pypdf.PdfReader(io.BytesIO(data)).pages
            return (pages[0].extract_text() or "") if len(pages) else ""
    except Exception:     # noqa: BLE001, S110 - an unreadable file is checked by its opening bytes
        pass
    return data[:FIRST_PAGE_CHARS * 4].decode("utf-8", "ignore")


def _files(source: Path):
    """(path for the industry, file name, bytes) for every pack file under source, zips opened."""
    for f in sorted(source.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() == ".zip":
            with zipfile.ZipFile(f) as z:
                for info in z.infolist():
                    if not info.is_dir() and info.filename.lower().endswith(WANTED):
                        yield f.parent / info.filename, Path(info.filename).name, z.read(info)
        elif f.suffix.lower() in WANTED:
            yield f, f.name, f.read_bytes()


def collect(sources: list[Path], dest: Path = DEST) -> dict:
    """Copy the packs into dest (see the module's text). Returns what was copied, skipped as a duplicate, split or refused."""
    copied, same, refused, split, unknown = [], [], [], [], []
    seen: dict[str, str] = {}
    for existing in dest.rglob("*") if dest.is_dir() else []:
        if not existing.is_file() or re.search(r"\.part\d+$", existing.name):
            continue
        if existing.name.endswith(".parts.json"):        # a split file: its checksum is in its manifest
            seen[json.loads(existing.read_text(encoding="utf-8"))["sha256"]] = str(existing.relative_to(dest))[:-len(".parts.json")]
        else:
            seen[hashlib.sha256(existing.read_bytes()).hexdigest()] = str(existing.relative_to(dest))
    for source in sources:
        if not source.is_dir():
            say(f"  not found, skipped: {source}", "yellow")
            continue
        for where, name, data in _files(source):
            industry = industry_for(where)
            if not industry:
                unknown.append(str(where))
                continue
            sha = hashlib.sha256(data).hexdigest()
            target = dest / industry / clean_name(name, industry)
            if sha in seen:
                same.append(f"{industry}/{target.name} (same as {seen[sha]})")
                continue
            if AI_MARK.search(first_page_text(name, data)):
                refused.append(f"{industry}/{name}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                target = target.with_name(f"{target.stem} ({sha[:6]}){target.suffix}")    # a different file of the same name
            seen[sha] = f"{industry}/{target.name}"
            if len(data) > SPLIT_LIMIT:
                parts = []
                for i in range(0, len(data), PART_SIZE):
                    part = target.with_name(f"{target.name}.part{i // PART_SIZE + 1:02d}")
                    part.write_bytes(data[i:i + PART_SIZE])
                    parts.append(part.name)
                target.with_name(target.name + ".parts.json").write_text(
                    json.dumps({"name": target.name, "parts": parts, "size": len(data), "sha256": sha}, indent=1), encoding="utf-8")
                split.append(f"{industry}/{target.name} ({len(parts)} parts)")
            else:
                target.write_bytes(data)
            copied.append(f"{industry}/{target.name}")
    total = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) if dest.is_dir() else 0
    return {"copied": copied, "duplicates": same, "refused": refused, "split": split, "unknown": unknown, "total": total}


SETTINGS = "settings.json"            # persist/settings.json (D558): {"packs_sources": [...]} survives resets
CACHE = "packs-cache.json"            # persist/: the sources' signature at the last copy, for the quick path


def configured_sources(root: Path = ROOT) -> tuple[list[Path], str]:
    """The pack source folders and where they came from: persist/settings.json, else EAX_PACKS_SOURCE (the config file
    or the environment; several separated by ;), else the owner's folders in the home folder."""
    import os

    from . import persist as P
    data, _w = P.read_json(P.folder(root) / SETTINGS, {})
    if data.get("packs_sources"):
        return [Path(x) for x in data["packs_sources"]], "persist/settings.json"
    given = os.environ.get("EAX_PACKS_SOURCE") or P._config_value(root, "EAX_PACKS_SOURCE")
    if given:
        return [Path(x.strip()) for x in given.split(";") if x.strip()], "EAX_PACKS_SOURCE"
    return default_sources(), "the default folders"


def signature(sources: list[Path]) -> str:
    """A quick fingerprint of the sources (every file's path, size and time), so an unchanged source is not read."""
    h = hashlib.sha256()
    for src in sources:
        if not src.is_dir():
            continue
        for f in sorted(src.rglob("*")):
            if f.is_file() and f.suffix.lower() in (*WANTED, ".zip"):
                st = f.stat()
                h.update(f"{f}|{st.st_size}|{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


def auto(root: Path = ROOT, dest: Path | None = None, quiet: bool = False) -> dict:
    """The pack step of every start (D584). Returns {state: none|same|copied, ...}; never raises for a missing source."""
    from . import persist as P
    dest = dest or root / "library" / "industry-packs"
    sources, where = configured_sources(root)
    present = [s for s in sources if s.is_dir()]
    if not present:
        if not quiet:
            say(f"Industry packs: no pack source folder here ({where}); the packs in library/industry-packs are used.")
        return {"state": "none", "sources": [str(s) for s in sources]}
    sig = signature(present)
    cache_path = P.folder(root) / CACHE
    cache, _w = P.read_json(cache_path, {})
    if cache.get("signature") == sig and dest.is_dir():
        if not quiet:
            say("Industry packs: no change in the pack sources.")
        return {"state": "same", "sources": [str(s) for s in present]}
    if not quiet:
        say(f"Industry packs: copying what is new or changed from {len(present)} source folder(s)...")
    out = collect(present, dest)
    P.write_json(cache_path, {"version": 1, "_comment": "eax packs auto: the pack sources' fingerprint at the last copy",
                              "signature": sig, "sources": [str(s) for s in present]})
    if not quiet:
        say(f"Industry packs: {len(out['copied'])} new or changed, {len(out['duplicates'])} unchanged"
            + (f", {len(out['refused'])} left out (marked not for AI use)" if out["refused"] else "")
            + ". They go into Documents as EA Explorer starts.")
    return {"state": "copied", **out}


def set_sources(folders: list[str], clear: bool = False, root: Path = ROOT) -> list[str]:
    """Sets the folders industry packs are taken from (persist)."""
    from . import persist as P
    path = P.folder(root) / SETTINGS
    data, _w = P.read_json(path, {})
    data.setdefault("version", 1)
    if clear:
        data.pop("packs_sources", None)
    else:
        data["packs_sources"] = [str(Path(f)) for f in folders]
    P.write_json(path, data)
    return data.get("packs_sources", [])


def main(args: list[str]) -> int:
    """eax packs: the industry packs (status, sources, load)."""
    from . import stack
    sub = args[0] if args else "status"
    rest = args[1:]
    if sub == "auto":
        try:
            auto()
        except Exception as exc:  # noqa: BLE001 - a start never fails because of the packs
            say(f"Industry packs: not copied ({exc}); the packs already in library/industry-packs are used.", "yellow")
        return 0
    if sub == "source":
        if rest:
            got = set_sources([a for a in rest if a != "--clear"], clear="--clear" in rest)
            say("Pack sources: " + ("; ".join(got) if got else "none set (EAX_PACKS_SOURCE or the default folders are used)"))
        else:
            srcs, where = configured_sources()
            say(f"Pack sources ({where}):")
            for x in srcs:
                say(f"  {x}  {'(there)' if x.is_dir() else '(not found)'}")
        return 0
    if sub == "collect":
        out = collect([Path(a) for a in rest] or default_sources())
        for k in ("copied", "split", "refused"):
            for x in out[k]:
                say(f"  {k}: {x}", "red" if k == "refused" else "")
        say(f"{len(out['copied'])} copied, {len(out['duplicates'])} duplicates kept once, {len(out['refused'])} refused "
            f"(marked not for AI use), {len(out['split'])} split. library/industry-packs is now {out['total'] / 1048576:.1f} MB.")
        say(f"They go into Documents at the next start ({EAX} up or {EAX} restart); commit library/industry-packs to ship them.")
        return 0
    if sub in ("load", "reload"):
        if rest and sub == "load":
            folder = Path(rest[0])
            if not folder.is_dir():
                raise Failure(f"No folder {folder}.")
            stack.compose_attached(["exec", "-T", "api", "rm", "-rf", "/tmp/eax-packs"])
            if stack.compose_attached(["cp", str(folder), "api:/tmp/eax-packs"]) != 0:
                raise Failure("Could not copy the folder into the api container: is EA Explorer running?")
            stack.interactive(["api", "python", "-m", "eax.industry_packs", "load", "/tmp/eax-packs"], [a for a in rest[1:]])
            return 0
        stack.interactive(["api", "python", "-m", "eax.industry_packs", "load", "shipped"], [a for a in rest if a.startswith("--")])
        return 0
    if sub == "status":
        stack.interactive(["api", "python", "-m", "eax.industry_packs", "status"], [])
        return 0
    raise Failure(f"Unknown: {EAX} packs {sub}. Use auto, source [folder...], load [folder], reload, status or collect [source...].")


if __name__ == "__main__":
    import sys
    try:
        sys.exit(main(sys.argv[1:]))
    except Failure as exc:
        say(f"ERROR: {exc}", "red")
        sys.exit(1)
