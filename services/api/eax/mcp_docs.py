"""The person's AI reads all of EA Explorer's documentation through MCP (R9.3; owner, 19 Nov 2026: "Add a story for MCP
to have access to all the docs", "access of documents and pdf to everyone"; D796, D797).

Read only, for anyone signed in, whatever their role, always the documents of the installation's own version (the
read-only folder the API already has for the Documentation page, D550: docs/ with the website's pages and the developer
documents, README, the eax help, the release notes; and, for these tools, the printed guides as PDF files and the
on-screen help catalogue). Also every error code with what to do (eax/errors.json).

  docs_list       what there is, by kind: documents, printed guides (with their chapters), error codes, screens' help
  docs_search     words searched for everywhere, each hit with where it is
  docs_read       one document, or one section of it (by heading), in pages for a long one; an error code; a guide's
                  chapters and its PDF
  screen_help     the on-screen help of a screen, tab, pop-up, field or button (what it is for, how to use it)

A document marked NOT FOR AI USE OR AUTOMATED PROCESSING is never listed, found or read. Every call is in the AI
activity log, as every tool's is; nothing is written.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from . import shipped_docs as D
from .mcp_server import mcp

MARK = "NOT FOR AI USE OR AUTOMATED PROCESSING"
PAGE = 20_000                 # characters a read gives at once; ask for the next part with start
PDF_MAX = 15 * 1024 * 1024    # a guide's PDF given as a file only up to this size (else its link)


def _allowed(text: str) -> bool:
    """Whether a document may be given to an AI: never one marked NOT FOR AI USE (D796)."""
    return MARK not in text.upper()


def _text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def documents() -> list[dict]:
    """The shipped documents an AI may read: key, title, group (D.listing without the marked ones)."""
    out = []
    for d in D.listing()["documents"]:
        try:
            _k, p = D.find(d["key"])
        except LookupError:
            continue
        if _allowed(_text(p)):
            out.append({"key": d["key"], "title": d["title"], "group": d["group"], "summary": d.get("summary", "")})
    return out


def errors() -> list[dict]:
    """Every error code with what it means and what to do (eax/errors.json)."""
    try:
        return json.loads((Path(__file__).resolve().parent / "errors.json").read_text(encoding="utf-8"))["errors"]
    except (OSError, ValueError, KeyError):
        return []


def catalogue() -> dict:
    """The on-screen help catalogue (the web's help/catalogue.json, mounted beside the documents)."""
    for p in (D.root() / "help" / "catalogue.json", D.root() / "services" / "web" / "src" / "help" / "catalogue.json"):
        if p.is_file():
            try:
                return {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")}
            except ValueError:
                return {}
    return {}


def guides() -> list[dict]:
    """The printed guides: id, title, their chapters (each chapter's documents by key) and whether its PDF is here."""
    try:
        spec = json.loads((D.root() / "docs" / "manuals" / "manuals.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    pdfs = {p.name: p for p in (D.root() / "documents").glob("*.pdf")} if (D.root() / "documents").is_dir() else {}
    out = []
    for g in spec.get("manuals") or []:
        pdf = next((n for n in pdfs if n.startswith(f"EA-Explorer-{g['id']}")), "")
        chapters = []
        for c in g.get("chapters") or []:
            keys = [_key_of(s) for s in c.get("sources") or []]
            chapters.append({"title": c.get("title", ""), "documents": [k for k in keys if k]})
        out.append({"id": g["id"], "title": g.get("title", ""), "purpose": g.get("purpose", ""), "chapters": chapters,
                    "pdf": pdf, "pdf_bytes": pdfs[pdf].stat().st_size if pdf else 0})
    return out


def _key_of(source: str) -> str:
    """A guide's chapter source (page:docs/site/x/y.md) as a document key (site~x~y), "" for one that is not a page."""
    m = re.match(r"^page:docs/(.+)\.md$", source or "")
    return m.group(1).replace("/", "~") if m else ""


def sections(text: str) -> list[str]:
    """The headings of a document (## and ###), in order."""
    # spaces then the words, each of its own kind, so nothing backtracks (SonarQube S8786); a heading on its own line
    return [m.group(2).strip() for m in re.finditer(r"^(#{2,3})[ \t]+(\S.*)$", text, re.M)]


def section(text: str, heading: str) -> str:
    """One section of a document: from its heading to the next heading of the same or a higher level ("" if none)."""
    lines = text.splitlines()
    want = heading.strip().lower()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})[ \t]+(\S.*)$", line)
        if m and m.group(2).strip().lower() == want:
            level = len(m.group(1))
            end = next((j for j in range(i + 1, len(lines))
                        if (n := re.match(r"^(#{1,6})\s", lines[j])) and len(n.group(1)) <= level), len(lines))
            return "\n".join(lines[i:end]).strip()
    return ""


def read(key: str, heading: str = "", start: int = 0) -> dict:
    """A document (or one section), in pages of PAGE characters; an error code; a printed guide."""
    key = (key or "").strip()
    if re.fullmatch(r"EAX-[A-Z]+-\d{3}", key.upper()):
        found = next((e for e in errors() if e["code"] == key.upper()), None)
        return found or {"error": f"No error code {key}."}
    if key.startswith("guide:"):
        g = next((x for x in guides() if x["id"] == key[6:]), None)
        return g or {"error": f"No printed guide {key[6:]}: docs_list kind=guides lists them."}
    try:
        _k, p = D.find(key)
    except LookupError:
        return {"error": f"No document {key}: docs_list lists them, docs_search finds them."}
    text = _text(p)
    if not _allowed(text):
        return {"error": f"{key} is not for AI use."}
    body = section(text, heading) if heading else text
    if heading and not body:
        return {"error": f"No section {heading!r} in {key}.", "sections": sections(text)}
    start = max(0, int(start or 0))
    part = body[start:start + PAGE]
    more = start + PAGE < len(body)
    return {"key": key, "title": D._title(text, key), "version": D.__version__, "section": heading or None,
            "sections": sections(text) if not heading else None, "text": part, "start": start,
            "next_start": start + PAGE if more else None, "length": len(body),
            "link": f"#/documentation/{key}"}


def search(words: str, limit: int = 20) -> list[dict]:
    """Every word searched for in the documents, the error codes and the screens' help; the best first."""
    allowed = {d["key"] for d in documents()}
    out = [{"kind": "document", **h} for h in D.search(words, limit=limit * 2) if h["key"] in allowed]
    ws = [w for w in (words or "").lower().split() if w]
    if ws:
        for e in errors():
            blob = " ".join(str(e.get(k, "")) for k in ("code", "title", "meaning", "cause", "to_do")).lower()
            if all(w in blob for w in ws):
                out.append({"kind": "error code", "key": e["code"], "title": e["title"], "snippet": e.get("to_do", "")})
        for k, v in catalogue().items():
            blob = (k + " " + json.dumps(v, ensure_ascii=False)).lower()
            if all(w in blob for w in ws):
                what = v.get("what", "") if isinstance(v, dict) else str(v)
                out.append({"kind": "screen help", "key": k, "title": k, "snippet": what[:200]})
    return out[:limit]


def screen(key: str) -> dict:
    """The on-screen help of a screen (page:#/route), tab (tab:Label), pop-up (popup:Title), field or button; a key
    without its kind is looked for as each kind; a route matched by its pattern (* for the parts that change)."""
    cat = catalogue()
    key = (key or "").strip()
    tries = [key] if ":" in key.split("#")[0] else [f"{k}:{key}" for k in ("page", "tab", "popup", "step", "field", "button")]
    for t in tries:
        if t in cat:
            return {"key": t, "help": cat[t]}
    for t in tries:                                 # a pattern: page:#/projects/*/home and the like
        for k, v in cat.items():
            if "*" in k and re.fullmatch(re.escape(k).replace(r"\*", "[^/]+"), t):
                return {"key": k, "help": v}
    near = [k for k in cat if key.lower() in k.lower()][:20]
    return {"error": f"No help for {key}.", "near": near}


# ================================================================ the tools
def _signed_in() -> dict | None:
    from . import permissions
    return None if permissions.current.get() is not None else {"error": "Sign in required."}


@mcp.tool()
async def docs_list(kind: str = "") -> Any:
    """EA Explorer's own documentation, of the version this installation runs: kind = documents (the website's pages,
    How do I, guides, the command line's help, release notes, the developer documents), guides (the printed guides with
    their chapters and PDFs), errors (every error code) or screens (every screen, pop-up and field with on-screen help);
    empty for how many of each. Read one with docs_read; find words with docs_search."""
    if (no := _signed_in()):
        return no
    kind = (kind or "").lower()
    if kind == "documents":
        return {"documents": documents()}
    if kind == "guides":
        return {"guides": [{k: g[k] for k in ("id", "title", "purpose", "pdf")} for g in guides()]}
    if kind == "errors":
        return {"errors": [{"code": e["code"], "title": e["title"]} for e in errors()]}
    if kind == "screens":
        return {"screens": sorted(catalogue())}
    return {"version": D.__version__, "documents": len(documents()), "guides": len(guides()), "errors": len(errors()),
            "screens": len(catalogue()), "kinds": ["documents", "guides", "errors", "screens"]}


@mcp.tool()
async def docs_search(words: str, limit: int = 20) -> Any:
    """Search all of EA Explorer's documentation, the error codes and the screens' help for every word given (any
    case), e.g. "restore one model" or "EAX-AUTH-001"; each hit with its kind, key, title and a snippet. Read a hit with
    docs_read (documents and error codes) or screen_help (screens)."""
    if (no := _signed_in()):
        return no
    return {"hits": search(words, max(1, min(int(limit or 20), 50)))}


@mcp.tool()
async def docs_read(key: str, section: str = "", start: int = 0) -> Any:
    """Read one document by its key (from docs_list or docs_search; e.g. site~how-do-i~back-up-now, operations,
    command-line-help), or only one section of it by its heading; a long one comes in parts (start = next_start). An
    error code (EAX-AUTH-001) gives what it means and what to do; guide:<id> (e.g. guide:04-system-admin) a printed
    guide's chapters, each with the documents to read, and its PDF's name (docs_pdf gives the file)."""
    if (no := _signed_in()):
        return no
    return read(key, section, start)


@mcp.tool()
async def docs_pdf(guide: str) -> Any:
    """A printed guide's PDF file (guide's id, e.g. 04-system-admin, from docs_list kind=guides), as base64 for an
    assistant that can take a file, with the link to download it in EA Explorer; a very large one gives the link only."""
    if (no := _signed_in()):
        return no
    g = next((x for x in guides() if x["id"] == (guide or "").removeprefix("guide:")), None)
    if not g or not g["pdf"]:
        return {"error": f"No printed guide {guide} here: docs_list kind=guides lists them."}
    p = D.root() / "documents" / g["pdf"]
    out = {"guide": g["id"], "title": g["title"], "file": g["pdf"], "bytes": g["pdf_bytes"],
           "link": f"/site/{D.__version__}/manuals/{g['pdf']}"}
    if g["pdf_bytes"] <= PDF_MAX:
        out["base64"] = base64.b64encode(p.read_bytes()).decode("ascii")
    return out


@mcp.tool()
async def screen_help(key: str) -> Any:
    """The on-screen help (what the F1 panel shows) of a screen, tab, pop-up, wizard step, field or button: what it is
    for, how to use it and an example. key: page:#/admin/backups, tab:Stakeholders, popup:Set up the authenticator
    again, field:..., button:...; or just the words (each kind is tried)."""
    if (no := _signed_in()):
        return no
    return screen(key)
