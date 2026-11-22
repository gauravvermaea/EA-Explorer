"""The EA Explorer website: plain HTML built from the repository (Release 7, R7.1 and R7.7, D738, D776).

The owner, 18 Nov 2026, 12:54: "There needs to be a Website. The website needs to be a sub folder inside the application
and I should be just able to copy it seperately and publish it. The help guides need to be sub pages inside the website";
"They should be able to print them as pdf so build them printable".

    python tools/build_website.py            writes services/web/public/site/ (committed; the app serves it at /site/)
    python tools/build_website.py --check    builds it in memory and says what is wrong (a test runs this)

Sources (Markdown, a small front matter between --- lines: title, summary, roles; a How do I page also group and
screen, the screen its picture shows, screen2 for a second one, and do (do2) where the picture is of a tab or a dialog
on that screen rather than the screen as it opens: tab "Deliveries"; open "Make a key..." - D781):
  docs/site/index.md                 the home page
  docs/site/roles/*.md               what EA Explorer has for each kind of person
  docs/site/how-do-i/*.md            one simple task each, printable (roles: who it is for)
  docs/site/concepts/*.md            the ideas behind the work: the ADM, metamodels, kinds of project, quality...
  docs/site/reports/*.md             every standard report and dashboard (tools/build_report_pages.py writes them)
  docs/site/integrate, platform      the developers' and platform developers' sections
  docs/site/guides/*.md              a topic from start to end (making a model, restoring, merging...): how its tasks fit
                                     together, each task linked to its own How do I page; printable
  docs/site/*.md                     the other pages (videos, further reading)
  docs/guides/*.md                   Install and run: the setup guides (eaxcli/setup.py writes them)
  releases/*.md                      Releases: every release's notes
  docs/site/shots/<page>.png         a How do I page's picture (<page>-2.png the second), taken by `eax site shots`
                                     from the screen its front matter names; a page with none shows where it will go

Every How do I page is one task (the owner, 18 Nov 2026, 13:48: "a seperate how do I file per task with screenshots.
This will help in future pdf generations and making videos"; 14:02: "For each user case and each how do I seperate
task page"). docs/site/shots/screens.json lists each page's screens for `eax site shots` (written by this builder).

Any page links another by its name, as in a wiki: [[data-quality]] (the page's own title as the words) or
[[data-quality|why data quality matters]]; the name is a file in concepts, how-do-i or guides.

Each release has its own copy (the owner, 18 Nov 2026, 16:37: "All documents to be inside a release sub folder"):
services/web/public/site/<version>/ (the version in services/api/version.toml); site/index.html opens the newest and
lists the others, which are kept.

The folder it writes is the whole site: plain HTML, CSS and JavaScript with relative links, nothing loaded from the
internet, search that works offline (search-index.js), a print layout on every page. Copy the folder anywhere (GitHub
Pages, a web server, a file share) and it works the same. No library is needed: Python's own.
"""

from __future__ import annotations

import html
import json
import posixpath
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "site"
SITE = ROOT / "services" / "web" / "public" / "site"   # every release's copy, and the page that opens the newest


def listed(folder: Path, pattern: str = "*.md") -> list[Path]:
    """The files in a folder, ordered by plain name, the same on every machine (D798).

    Sorting Path objects is case-blind on Windows and case-aware on Linux, so README.md
    came first in the test runner and after backups.md on the laptop."""
    return sorted(folder.glob(pattern), key=lambda f: f.name)


def version() -> str:
    """The release this copy of the site describes: services/api/version.toml."""
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "services" / "api" / "version.toml").read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else "dev"


OUT = SITE / version()
WIKI = re.compile(r"\[\[([a-z0-9-]+)(?:\|([^\]]+))?\]\]")
WIKI_MISSES: list[str] = []
SHOTS = SRC / "shots"
DOCUMENTS = ROOT / "documents"          # the printed guides, made by eax site pdfs (D783, D785, D790)
MANUALS = ROOT / "docs" / "manuals" / "manuals.json"
YOUTUBE = "https://www.youtube.com/@ea-explorer-os"
VIDEOS = ROOT / "docs" / "site" / "videos.json"   # a How do I page's video, once it is out: {"tag-a-model": "https://..."}
GITHUB = "https://github.com/gauravvermaea/EA-Explorer"

ROLES = [   # (code, the name people know it by, one line)
    ("system-admin", "System Admin", "Run the installation: people, security, backups, updates, health"),
    ("model-admin", "Model Admin", "Look after models and their metamodels: people, quality, versions, merges"),
    ("project-admin", "Project Admin", "Run architecture projects: templates, phases, deliverables, sign-off"),
    ("user", "Practising architects", "Find, change, draw, report and commit the architecture"),
    ("industry-modeller", "Industry model makers", "Build reference models and metamodels for an industry"),
    ("developer", "Developers", "Bring data in and take it out: the API, feeds, formats, scripts, AI"),
    ("executive", "Executives", "See where the architecture and its projects stand, and approve what needs you"),
    ("platform-developer", "Platform developers", "Change EA Explorer itself: run it locally, debug, test, release"),
]
# the sections of pages that explain rather than instruct (the owner, 18 Nov 2026, 16:36 and 16:51), each a folder of
# docs/site: (folder, its name in the site's top bar, what its index page says)
READING = [
    ("concepts", "Concepts", ("The ideas behind the work: what enterprise architecture is for, the ADM, metamodels and "
                              "models, the kinds of project and what each is for, and how EA Explorer maps to TOGAF.")),
    ("reports", "Reports", ("Every standard report and dashboard: what it shows, who it is for, how to use it and how "
                            "to read it, and where it sits in TOGAF. Open them on any model's Reports tab.")),
    ("integrate", "Integrate", ("For developers connecting other systems: connectors, the published formats, deliveries, "
                                "push sources, OData in and out, reports, webhooks, the API and MCP.")),
    ("platform", "Platform", ("For developers working on EA Explorer itself: the code, running it locally, debugging, "
                              "testing, making a change and releasing it.")),
]
ROLE_NAME = {c: n for c, n, _ in ROLES}
# the How do I topics, in the order a person meets them (the owner, 18 Nov 2026, 13:01: "Group them by some common")
GROUP_ORDER = ["Start here", "The practice", "Getting around", "Working with content", "Views and reports", "Projects", "Models", "Metamodels",
               "Data quality", "Versions and merging", "Industry models", "Bringing data in", "Taking data out",
               "Access for systems", "People and access", "Security", "Backups and recovery", "Running it",
               "Surveys and maturity", "AI", "Connectors", "Reading and reporting", "Running locally", "The code"]
SECTIONS = [("index.html", "Home"), ("roles/index.html", "Your role"), ("concepts/index.html", "Concepts"),
            ("how-do-i/index.html", "How do I"), ("faq.html", "Questions"), ("guides/index.html", "Guides"),
            ("printed-guides/index.html", "Printed guides"), ("reports/index.html", "Reports"),
            ("integrate/index.html", "Integrate"),
            ("platform/index.html", "Platform"),
            ("install/index.html", "Install and run"), ("releases/index.html", "Releases"), ("videos.html", "Videos"),
            ("further-reading.html", "Further reading")]


# ---------------------------------------------------------------- Markdown, the part the pages use
def _inline(text: str, link) -> str:
    """Inline Markdown: code, images, links, bold, italic; everything else escaped."""
    out, i = [], 0
    for m in re.finditer(r"`([^`]+)`", text):
        out.append(_inline_plain(text[i:m.start()], link))
        out.append(f"<code>{html.escape(m.group(1))}</code>")
        i = m.end()
    out.append(_inline_plain(text[i:], link))
    return "".join(out)


def _inline_plain(text: str, link) -> str:
    t = html.escape(text, quote=False)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: f'<img src="{link(m.group(2))}" alt="{m.group(1)}">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: _a(m.group(1), link(html.unescape(m.group(2)))), t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", t)
    return t


def _a(label: str, href: str) -> str:
    outside = href.startswith(("http://", "https://", "mailto:"))
    extra = ' target="_blank" rel="noopener"' if outside else ""
    return f'<a href="{html.escape(href)}"{extra}>{label}{" <span class=\"out\" aria-label=\"opens elsewhere\">↗</span>" if outside else ""}</a>'


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-") or "section"


def markdown(text: str, link=lambda u: u) -> tuple[str, list[tuple[int, str, str]]]:
    """HTML of the Markdown, and its headings (level, id, text) for the page's contents."""
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    heads: list[tuple[int, str, str]] = []
    i = 0
    para: list[str] = []
    used: set[str] = set()

    def flush():
        if para:
            out.append(f"<p>{_inline(' '.join(s.strip() for s in para), link)}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            j = i + 1
            code = []
            while j < len(lines) and not lines[j].startswith("```"):
                code.append(lines[j])
                j += 1
            out.append(f'<pre class="code"><code>{html.escape(chr(10).join(code))}</code></pre>')
            i = j + 1
            continue
        h = re.match(r"^(#{1,4})\s+(\S.*|)$", line)
        if h:
            flush()
            level, words = len(h.group(1)), h.group(2).strip()
            hid = _slug(words)
            n = 2
            while hid in used:
                hid = f"{_slug(words)}-{n}"
                n += 1
            used.add(hid)
            heads.append((level, hid, re.sub(r"`", "", words)))
            out.append(f'<h{level} id="{hid}">{_inline(words, link)}</h{level}>')
            i += 1
            continue
        if re.match(r"^\s*(---|\*\*\*)\s*$", line):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{3,}", lines[i + 1]):
            flush()
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]
            head = cells(line)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(cells(lines[j]))
                j += 1
            out.append('<div class="table"><table><thead><tr>' + "".join(f"<th>{_inline(c, link)}</th>" for c in head)
                       + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_inline(c, link)}</td>" for c in r) + "</tr>"
                                                          for r in rows) + "</tbody></table></div>")
            i = j
            continue
        if line.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            kind = "note"
            if quote and re.match(r"^\*\*(Tip|Note|Careful|Before you start)\b", quote[0]):
                kind = quote[0][2:].split("*")[0].split()[0].lower()
            out.append(f'<blockquote class="{kind}"><p>{_inline(" ".join(quote), link)}</p></blockquote>')
            continue
        lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(\S.*|)$", line)
        if lm:
            flush()
            html_list, i = _list(lines, i, link)
            out.append(html_list)
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        para.append(line)
        i += 1
    flush()
    return "\n".join(out), heads


def _list(lines: list[str], i: int, link) -> tuple[str, int]:
    """A list from line i, with lists inside it by indent; (its HTML, the next line)."""
    first = re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i])
    indent, ordered = len(first.group(1)), first.group(2)[0].isdigit()
    items: list[str] = []
    while i < len(lines):
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(\S.*|)$", lines[i])
        if not m or len(m.group(1)) < indent:
            if lines[i].startswith(" " * (indent + 2)) and lines[i].strip() and items:   # an item carried on
                items[-1] += " " + _inline(lines[i].strip(), link)
                i += 1
                continue
            break
        if len(m.group(1)) > indent:
            inner, i = _list(lines, i, link)
            items[-1] += inner
            continue
        items.append(_inline(m.group(3), link))
        i += 1
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>", i


def front_matter(text: str) -> tuple[dict, str]:
    """(the --- block's fields, the rest); roles split on commas."""
    meta: dict = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end > 0:
            for line in text[4:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[end + 4:].lstrip("\n")
    if "roles" in meta:
        meta["roles"] = [r.strip() for r in meta["roles"].split(",") if r.strip()]
    return meta, text


# ---------------------------------------------------------------- the pages
@dataclass
class Page:
    """One page of the site: where it goes, its words, and where it came from."""
    out: str                      # its path in the site, e.g. how-do-i/add-a-user.html
    title: str
    body_md: str
    section: str                  # the SECTIONS page it sits under
    summary: str = ""
    roles: list[str] = field(default_factory=list)
    group: str = ""               # a How do I page's topic: its tiles are grouped by it
    source: str = ""              # where it came from, for messages
    printable: bool = True
    extra_html: str = ""          # lists made by the builder (the role's tasks, a section's index)
    screens: list[str] = field(default_factory=list)   # a How do I page's screens: its pictures, in order
    does: list[str] = field(default_factory=list)      # what to open on each screen first (D781), "" for nothing


def _title_of(md: str, fallback: str) -> tuple[str, str]:
    m = re.match(r"^#\s+(.+)\n?", md)
    return (m.group(1).strip(), md[m.end():]) if m else (fallback, md)


def _version_key(name: str) -> tuple:
    return tuple(int(x) if x.isdigit() else -1 for x in re.split(r"[.\-]", name))


def collect() -> list[Page]:
    """Every page of the site, from docs/site, docs/guides and releases."""
    pages: list[Page] = []

    named = {f.stem: f for d in ("concepts", "reports", "integrate", "platform", "how-do-i", "guides") for f in listed(SRC / d)}
    WIKI_MISSES.clear()

    def wiki(m: re.Match, here: Path) -> str:
        target = named.get(m.group(1))
        if not target:
            WIKI_MISSES.append(f"{here.relative_to(ROOT)}: [[{m.group(1)}]] names no page")
            return m.group(0)
        words = m.group(2) or front_matter(target.read_text(encoding="utf-8"))[0].get("title", target.stem)
        return f"[{words}]({posixpath.relpath(target.as_posix(), here.parent.as_posix())})"

    def read(p: Path) -> tuple[dict, str]:
        meta, md = front_matter(p.read_text(encoding="utf-8"))
        return meta, WIKI.sub(lambda m: wiki(m, p), md)
    # home, and the other pages at the top
    for p in listed(SRC):
        meta, md = read(p)
        title, md = _title_of(md, p.stem)
        name = "index.html" if p.stem == "index" else f"{p.stem}.html"
        pages.append(Page(name, meta.get("title", title), md, name, meta.get("summary", ""), source=str(p.relative_to(ROOT))))
    # the roles
    for code, name, line in ROLES:
        p = SRC / "roles" / f"{code}.md"
        if p.exists():
            meta, md = read(p)
            title, md = _title_of(md, name)
            pages.append(Page(f"roles/{code}.html", meta.get("title", title), md, "roles/index.html",
                              meta.get("summary", line), [code], source=str(p.relative_to(ROOT))))
    pages.append(Page("roles/index.html", "Your role", "Choose what you do with EA Explorer: each page says what the "
                      "platform has for you, how it is put together, and the tasks you will do.", "roles/index.html",
                      printable=False))
    # How do I
    guides = {g.stem for g in (SRC / "guides").glob("*.md")}
    for p in listed(SRC / "how-do-i"):
        if p.stem in guides:   # an older copy of a page that became a Guide (D777): the Guide is the page
            print(f"  left out {p.relative_to(ROOT)}: it is now docs/site/guides/{p.name} (delete the old copy)")
            continue
        meta, md = read(p)
        title, md = _title_of(md, p.stem)
        pages.append(Page(f"how-do-i/{p.stem}.html", meta.get("title", title), md, "how-do-i/index.html",
                          meta.get("summary", ""), meta.get("roles", []), meta.get("group", "Other"), str(p.relative_to(ROOT)),
                          screens=[meta[k] for k in ("screen", "screen2") if meta.get(k)],
                          does=[meta.get(d, "") for k, d in (("screen", "do"), ("screen2", "do2")) if meta.get(k)]))
    pages.append(Page("faq.html", "Questions: how do I...?", "Every question with its quick steps, the guide to read and "
                      "its video. Choose your role, or type to find a question.", "faq.html", printable=False))
    pages.append(Page("how-do-i/index.html", "How do I", "One task on each page, step by step, ready to print or save as "
                      "PDF. Choose your role, or type to find a task.", "how-do-i/index.html", printable=False))
    # Concepts, Integrate, Platform: the ideas behind the work and the developers' sections (the owner, 16:36: "pages
    # around phelosphy of project ADM, meta model..."; 16:51: "a whole section for developers... another section for
    # platform developers")
    for folder, name, intro in READING:
        for p in listed(SRC / folder):
            meta, md = read(p)
            title, md = _title_of(md, p.stem)
            pages.append(Page(f"{folder}/{p.stem}.html", meta.get("title", title), md, f"{folder}/index.html",
                              meta.get("summary", ""), meta.get("roles", []), meta.get("group", "Other"), str(p.relative_to(ROOT))))
        pages.append(Page(f"{folder}/index.html", name, intro, f"{folder}/index.html", printable=False))
    # Guides: a topic from start to end, its tasks linked to their How do I pages (owner, 18 Nov 2026, 14:12: "Each is
    # simple one task only", "and then other pages as discussed")
    for p in listed(SRC / "guides"):
        meta, md = read(p)
        title, md = _title_of(md, p.stem)
        pages.append(Page(f"guides/{p.stem}.html", meta.get("title", title), md, "guides/index.html",
                          meta.get("summary", ""), meta.get("roles", []), meta.get("group", "Other"), str(p.relative_to(ROOT))))
    pages.append(Page("guides/index.html", "Guides", "A topic from start to end: how its tasks fit together, each task "
                      "with its own How do I page.", "guides/index.html", printable=False))
    # Install and run: the setup guides
    for p in listed(ROOT / "docs" / "guides"):
        md = p.read_text(encoding="utf-8")
        title, md = _title_of(md, p.stem)
        out = "install/index.html" if p.stem == "README" else f"install/{p.stem}.html"
        pages.append(Page(out, "Install and run" if p.stem == "README" else title, md, "install/index.html",
                          roles=["system-admin"], source=str(p.relative_to(ROOT))))
    # Releases
    notes = sorted((p for p in (ROOT / "releases").glob("*.md") if re.match(r"^\d", p.stem)), key=lambda p: _version_key(p.stem),
                   reverse=True)
    for p in notes:
        md = p.read_text(encoding="utf-8")
        title, md = _title_of(md, p.stem)
        pages.append(Page(f"releases/{p.stem}.html", title, md, "releases/index.html", source=str(p.relative_to(ROOT))))
    pages.append(printed_guides_page())
    pages.append(Page("releases/index.html", "Releases", "What came in each release, newest first. EA Explorer tells "
                      "every installation about a new release on System Admin › Updates.", "releases/index.html",
                      printable=False, extra_html="<ul class=\"cards-list\">" + "".join(
                          f'<li><a href="{p.stem}.html">{html.escape(_title_of(p.read_text(encoding="utf-8"), p.stem)[0])}</a></li>'
                          for p in notes) + "</ul>"))
    return pages


def printed_guides() -> list[dict]:
    """The printed guides (docs/manuals/manuals.json) with their PDF in documents/ where it has been made: id, title,
    audience, purpose, file, bytes (0 when not made yet)."""
    if not MANUALS.is_file():
        return []
    out = []
    for g in json.loads(MANUALS.read_text(encoding="utf-8"))["manuals"]:
        f = DOCUMENTS / f"EA-Explorer-{g['id']}.pdf"
        out.append({"id": g["id"], "title": g["title"], "audience": g["audience"], "purpose": g["purpose"],
                    "file": f.name, "bytes": f.stat().st_size if f.is_file() else 0})
    return out


def printed_guides_page() -> Page:
    """Printed guides (the owner, 18 Nov 2026, 21:00: "I want them to be in documentation of website as links to
    download", D785): each guide, who it is for and what it is for, and its PDF to download."""
    rows = []
    for g in printed_guides():
        size = f"{g['bytes'] / 1048576:.1f} MB" if g["bytes"] else ""
        link = (f'<a class="download" href="../manuals/{html.escape(g["file"])}" download>Download the PDF</a> '
                f'<span class="quiet small">{size}</span>' if g["bytes"] else
                '<span class="quiet small">Not printed yet: <code>eax site pdfs</code></span>')
        rows.append(f'<li><strong>{html.escape(g["id"].split("-")[0])}. {html.escape(g["title"])}</strong>'
                    f'<span class="who">For {html.escape(g["audience"])}</span><span>{html.escape(g["purpose"])}</span>{link}</li>')
    return Page("printed-guides/index.html", "Printed guides",
                f"The {len(printed_guides())} guides to print and keep, each with a cover, what it is for and a table of contents, made from "
                "the same pages as this website, with a picture of every screen.", "printed-guides/index.html",
                printable=False, extra_html='<ul class="cards-list printed">' + "".join(rows) + "</ul>")


# ---------------------------------------------------------------- links, layout, the index pages
def _rel(frm: str, to: str) -> str:
    """The relative address of `to` from page `frm` (both site paths)."""
    up = "../" * frm.count("/")
    return up + to


def _linker(page: Page, sources: dict[str, str]):
    """Rewrites a source's link to the page it became: x.md to x.html, ../releases/5.7.0.md to releases/5.7.0.html."""
    src_dir = (ROOT / page.source).parent if page.source else SRC

    def link(u: str) -> str:
        if u.startswith(("http://", "https://", "mailto:", "#")):
            return u
        path, _, frag = u.partition("#")
        target = (src_dir / path).resolve()
        hit = sources.get(str(target))
        if hit:
            return _rel(page.out, hit) + (f"#{frag}" if frag else "")
        if path.endswith(".html"):                       # already the site's own address, from this page
            return u
        if target.is_file() and ROOT in target.parents:  # a file of the repository not on the site: on GitHub
            return f"{GITHUB}/blob/main/{target.relative_to(ROOT).as_posix()}" + (f"#{frag}" if frag else "")
        return u                                         # left as it is; --check names it
    return link


def _nav(page: Page) -> str:
    return "".join(f'<a href="{_rel(page.out, href)}"{" class=\"here\"" if page.section == href else ""}>{name}</a>'
                   for href, name in SECTIONS)


def _tasks_of(pages: list[Page], role: str) -> list[Page]:
    return [p for p in pages if p.out.startswith("how-do-i/") and p.out != "how-do-i/index.html" and role in p.roles]


def _tiles(tasks: list[Page], frm: str) -> str:
    """The tasks as tiles, grouped by topic (the owner, 18 Nov 2026, 13:01: "tiles in tabs for roles"; "Group them by
    some common"); each tile carries its words for the filter."""
    groups: dict[str, list[Page]] = {}
    for t in sorted(tasks, key=lambda t: t.title):
        groups.setdefault(t.group or "Other", []).append(t)
    out = []
    for g in sorted(groups, key=lambda g: (GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER), g)):
        out.append(f'<section class="group"><h3>{html.escape(g)}</h3><ul class="tiles">' + "".join(
            f'<li data-words="{html.escape((t.title + " " + t.summary + " " + g).lower())}"><a href="{_rel(frm, t.out)}">'
            f'<strong>{html.escape(t.title)}</strong><span>{html.escape(t.summary)}</span></a></li>' for t in groups[g])
            + "</ul></section>")
    return "".join(out)


def _role_tasks(pages: list[Page], role: str, frm: str) -> str:
    tasks = _tasks_of(pages, role)
    reading = tuple(f"{f}/" for f in ("guides", *(r[0] for r in READING)))
    guides = [p for p in pages if p.out.startswith(reading) and not p.out.endswith("/index.html") and role in p.roles]
    out = ('<h2 id="your-guides">Read first: concepts and guides for you</h2>' + _tiles(guides, frm)) if guides else ""
    return out + ('<h2 id="your-tasks">How do I: your tasks</h2>' + _tiles(tasks, frm) if tasks else "")


# ---------------------------------------------------------------- Questions (the FAQ)
# owner, 21 Nov 2026, 20:51: "build a FAQ / How do I page ... Have some sort of by role tabs + search ... in questions
# 1. Give quick steps on the question in How do I 2. Point to the document 3. Point to the video (comming)"; "Also add
# them to website" (D838)
def _guides_of_tasks(pages: list[Page]) -> dict[str, list[dict]]:
    """Each How do I page's printed guides (docs/manuals/manuals.json: a chapter names a page, or the How do I pages of a
    topic and role), as {its address: [guide]}."""
    if not MANUALS.is_file():
        return {}
    tasks = [p for p in pages if p.out.startswith("how-do-i/") and p.out != "how-do-i/index.html"]
    by: dict[str, list[dict]] = {}
    files = {g["id"]: g for g in printed_guides()}
    for g in json.loads(MANUALS.read_text(encoding="utf-8"))["manuals"]:
        for ch in g.get("chapters", []):
            for src in ch.get("sources", []):
                hits = []
                if src.startswith("howdoi:"):
                    q = dict(kv.split("=", 1) for kv in src[7:].split(";") if "=" in kv)
                    if "pages" in q:                       # a list of pages by name: howdoi:pages=a,b,c
                        names = {f"how-do-i/{n.strip()}.html" for n in q["pages"].split(",")}
                        hits = [t for t in tasks if t.out in names]
                    else:                                  # the pages of a topic, for a role: howdoi:group=X;role=Y
                        hits = [t for t in tasks if t.group == q.get("group") and ("role" not in q or q["role"] in t.roles)]
                elif "how-do-i/" in src:
                    stem = src.split("how-do-i/", 1)[1].split(".md", 1)[0]
                    hits = [t for t in tasks if t.out == f"how-do-i/{stem}.html"]
                for t in hits:
                    if all(x["id"] != g["id"] for x in by.get(t.out, [])):
                        by.setdefault(t.out, []).append({**files.get(g["id"], {"id": g["id"], "title": g["title"],
                                                                               "file": "", "bytes": 0}), "chapter": ch["title"]})
    return by


def videos() -> dict[str, str]:
    """The How do I videos that are out (docs/site/videos.json): {page name: its address}; the rest are coming."""
    try:
        got = json.loads(VIDEOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in (got.get("videos") or {}).items() if isinstance(v, str) and v.startswith("https://")}


def _quick_steps(page: Page) -> str:
    """The page's steps, as its How do I page has them (or what it is for, where it has no steps)."""
    m = re.search(r"^## Steps\s*\n(.*?)(?=^## |\Z)", page.body_md, re.M | re.S)
    md = m.group(1).strip() if m else ""
    if not re.search(r"^\s*\d+\.\s", md, re.M):
        return f'<p>{html.escape(page.summary)}</p>'
    body, _heads = markdown(md, lambda u: u)
    return re.sub(r'<a href="[^"]*">(.*?)</a>', r"\1", body)          # the steps only: their links are on the page


def _question(t: Page, frm: str, guides: list[dict], video: str) -> str:
    q = t.title[0].lower() + t.title[1:]
    words = " ".join([t.title, t.summary, t.group, re.sub(r"[`*#>|\[\]()_]", " ", t.body_md)[:600]]).lower()
    docs = [f'<a href="{_rel(frm, t.out)}">How do I: {html.escape(t.title)}</a> (with pictures, to print)']
    for g in guides:
        name = f'{g["id"].split("-")[0]}. {html.escape(g["title"])}'
        docs.append((f'<a href="{_rel(frm, "manuals/" + g["file"])}" download>{name} (PDF)</a>' if g.get("bytes") else
                     f'<a href="{_rel(frm, "printed-guides/index.html")}">{name}</a>')
                    + f' <span class="quiet small">chapter {html.escape(g["chapter"])}</span>')
    vid = (f'<a href="{html.escape(video)}" target="_blank" rel="noopener">Watch the video ↗</a>' if video else
           '<span class="quiet">Coming soon</span>')
    return (f'<li data-roles="{html.escape(" ".join(t.roles))}" data-words="{html.escape(re.sub(r"\s+", " ", words))}">'
            f'<details><summary>How do I {html.escape(q)}?</summary>'
            f'<div class="answer"><h4>Quick steps</h4>{_quick_steps(t)}<h4>Read more</h4><ul>'
            + "".join(f"<li>{d}</li>" for d in docs) + f'</ul><h4>Video</h4><p>{vid}</p></div></details></li>')


def _faq_html(page: Page, pages: list[Page]) -> str:
    """Every How do I page as a question, once, by topic: the role tabs and the filter show only those that match (each
    question carries its roles and words); each opens to its quick steps, the page and printed guides to read, and its
    video (or coming soon)."""
    every = [p for p in pages if p.out.startswith("how-do-i/") and p.out != "how-do-i/index.html"]
    guides, vids = _guides_of_tasks(pages), videos()
    by: dict[str, list[Page]] = {}
    for t in sorted(every, key=lambda t: t.title):
        by.setdefault(t.group or "Other", []).append(t)
    body = "".join(
        f'<section class="group"><h3>{html.escape(g)}</h3><ul class="faq">'
        + "".join(_question(t, page.out, guides.get(t.out, []), vids.get(t.out[9:-5], "")) for t in by[g]) + "</ul></section>"
        for g in sorted(by, key=lambda g: (GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER), g)))
    tabs = [("all", "Every question")] + [(c, n) for c, n, _l in ROLES if _tasks_of(pages, c)]
    bar = ('<div class="howto-tools"><input type="search" class="filter" placeholder="Type to find a question" '
           'aria-label="Find a question"><p class="filter-none quiet" hidden>No question matches.</p></div>'
           '<div class="role-tabs" role="tablist">' + "".join(
               f'<button type="button" role="tab" data-tab="{c}"{" aria-selected=\"true\"" if c == "all" else ""}>{n}</button>'
               for c, n in tabs) + "</div>")
    return f'<div class="faq-page">{bar}<p class="faq-count quiet small"></p>{body}</div>'


def _index_html(page: Page, pages: list[Page]) -> str:
    if page.out == "faq.html":
        return _faq_html(page, pages)
    if page.out == "roles/index.html":
        return '<ul class="cards">' + "".join(
            f'<li><a href="{code}.html"><strong>{name}</strong><span>{line}</span></a></li>' for code, name, line in ROLES) + "</ul>"
    if page.out == "how-do-i/index.html":
        every = [p for p in pages if p.out.startswith("how-do-i/") and p.out != page.out]
        tabs = [("all", "Every task", every)] + [(c, n, _tasks_of(pages, c)) for c, n, _l in ROLES]
        bar = ('<div class="howto-tools"><input type="search" class="filter" placeholder="Type to find a task" '
               'aria-label="Find a task"><p class="filter-none quiet" hidden>No task matches.</p></div>'
               '<div class="role-tabs" role="tablist">' + "".join(
                   f'<button type="button" role="tab" data-tab="{c}"{" aria-selected=\"true\"" if c == "all" else ""}>{n}</button>'
                   for c, n, _t in tabs) + "</div>")
        panes = "".join(f'<div class="role-pane" data-pane="{c}"><h2 id="{c}">{n}</h2>{_tiles(t, page.out)}</div>'
                        for c, n, t in tabs)
        return f'<div class="howto">{bar}{panes}</div>'
    for folder, _name, _intro in READING:
        if page.out == f"{folder}/index.html":
            return _tiles([p for p in pages if p.out.startswith(f"{folder}/") and p.out != page.out], page.out)
    if page.out == "guides/index.html":
        return _tiles([p for p in pages if p.out.startswith("guides/") and p.out != page.out], page.out)

    return ""


def shot_name(slug: str, n: int) -> str:
    """The picture of a How do I page's nth screen (0 the first): <page>.png, <page>-2.png."""
    return f"{slug}.png" if n == 0 else f"{slug}-{n + 1}.png"


def _figures(page: Page) -> str:
    """The page's pictures, after its summary; where one has not been taken yet, a box saying which screen it shows."""
    if not page.screens:
        return ""
    slug = page.out.rsplit("/", 1)[-1].removesuffix(".html")
    out = []
    for n, screen in enumerate(page.screens):
        name = shot_name(slug, n)
        where = html.escape(screen)
        if (SHOTS / name).is_file():
            out.append(f'<figure class="shot"><img src="../shots/{name}" alt="The screen: {html.escape(page.title)}" '
                       f'loading="lazy"><figcaption>The screen: <code>{where}</code></figcaption></figure>')
        else:
            out.append(f'<figure class="shot missing"><div>Picture to come: <code>{where}</code></div>'
                       f'<figcaption>Taken by <code>eax site shots</code> on an installation with the demo data.</figcaption></figure>')
    return "".join(out)


def screens_list(pages: list[Page]) -> str:
    """docs/site/shots/screens.json: every How do I page's screens and the picture each makes, for eax site shots."""
    rows = []
    for p in pages:
        slug = p.out.rsplit("/", 1)[-1].removesuffix(".html")
        for n, screen in enumerate(p.screens):
            row = {"page": slug, "title": p.title, "screen": screen, "file": shot_name(slug, n)}
            if n < len(p.does) and p.does[n]:
                row["do"] = p.does[n]
            rows.append(row)
    return json.dumps(rows, indent=1, ensure_ascii=False) + "\n"


def render(page: Page, pages: list[Page], sources: dict[str, str]) -> str:
    """One page as HTML: the top bar, the page, the lists the builder makes, the footer."""
    body, heads = markdown(page.body_md, _linker(page, sources))
    extra = page.extra_html or _index_html(page, pages)
    if page.out.startswith("roles/") and page.out != "roles/index.html":
        extra += _role_tasks(pages, page.roles[0], page.out)
    contents = [h for h in heads if h[0] == 2]
    toc = ('<nav class="toc" aria-label="On this page"><strong>On this page</strong><ul>'
           + "".join(f'<li><a href="#{hid}">{html.escape(words)}</a></li>' for _l, hid, words in contents) + "</ul></nav>"
           ) if len(contents) > 2 else ""
    who = (f'<p class="who">For: {", ".join(html.escape(ROLE_NAME.get(r, r)) for r in page.roles)}</p>'
           if page.roles and page.out.startswith(("how-do-i/", "guides/", *(f"{r[0]}/" for r in READING))) else "")
    tools = ('<p class="page-tools"><button type="button" class="print">Print or save as PDF</button></p>'
             if page.printable else "")
    asset = lambda name: _rel(page.out, f"assets/{name}")
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page.title)} · EA Explorer</title>
<meta name="description" content="{html.escape(page.summary or page.title)}">
<link rel="stylesheet" href="{asset('site.css')}">
</head>
<body data-root="{_rel(page.out, '')}">
<a class="skip" href="#main">Skip to the page</a>
<header class="top">
  <a class="brand" href="{_rel(page.out, 'index.html')}">EA Explorer</a>
  <nav class="sections" aria-label="The site">{_nav(page)}</nav>
  <form class="search" role="search" action="{_rel(page.out, 'search.html')}">
    <input type="search" name="q" placeholder="Search the site" aria-label="Search the site">
  </form>
</header>
<main id="main" class="page">
  <article>
    <h1>{html.escape(page.title)}</h1>
    {who}{tools}
    {f'<p class="summary">{html.escape(page.summary)}</p>' if page.summary and not page.body_md.strip().startswith(page.summary[:30]) else ''}
    {_figures(page)}
    {toc}
    {body}
    {extra}
  </article>
</main>
<footer class="foot">
  <span>EA Explorer: free and open source (AGPL-3.0).</span>
  <span class="site-build" data-version="{html.escape(version())}">Version {html.escape(version())}</span>
  <a href="{YOUTUBE}" target="_blank" rel="noopener">Videos on YouTube ↗</a>
  <a href="{GITHUB}" target="_blank" rel="noopener">The code on GitHub ↗</a>
  <span class="printed-from">Printed from the EA Explorer website: {html.escape(page.out)}</span>
</footer>
<script src="{asset('search-index.js')}"></script>
<script src="{asset('site.js')}"></script>
</body>
</html>
"""


def search_page() -> str:
    """The search page: the results are filled in by assets/site.js from assets/search-index.js."""
    page = Page("search.html", "Search", "", "", printable=False)
    out = render(page, [], {})
    return out.replace("<article>", '<article><div id="results" aria-live="polite"><p class="quiet">Type in the search box above.</p></div>', 1)


def search_index(pages: list[Page]) -> str:
    """Every page's title, address, summary and words, for the search that works offline."""
    rows = []
    for p in pages:
        words = re.sub(r"[`*#>|\[\]()_]", " ", p.body_md)
        rows.append({"t": p.title, "u": p.out, "s": p.summary, "w": re.sub(r"\s+", " ", words).strip()[:6000]})
    return "window.EAX_SEARCH = " + json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + ";\n"


# ---------------------------------------------------------------- one copy for each release
def _release_dir(name: str) -> bool:
    return bool(re.fullmatch(r"\d+\.\d+\.\d+|dev", name))


def releases_on_disk() -> list[str]:
    """The releases with a copy of the site, newest first (this one always among them)."""
    found = {d.name for d in SITE.iterdir() if d.is_dir() and _release_dir(d.name)} if SITE.is_dir() else set()
    return sorted(found | {version()}, key=_version_key, reverse=True)


def front_page(releases: list[str]) -> str:
    """site/index.html: opens the newest release's copy at once (a refresh the page itself asks for) and lists every copy
    kept; with #to=<page> (the screens' links, D838) it opens that page of the newest copy."""
    newest = releases[0]
    rows = "".join(f'<li><a href="{r}/index.html">EA Explorer {html.escape(r)}</a>{" (newest)" if r == newest else ""}</li>'
                   for r in releases)
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>/* index.html#to=faq.html opens that page of the newest copy (the screens' links, D838); a page of the site only */
var m = /^#to=([A-Za-z0-9_][A-Za-z0-9_./-]*\\.html(#[A-Za-z0-9_-]+)?)$/.exec(window.location.hash || "");
if (m && m[1].indexOf("..") < 0 && m[1].indexOf("//") < 0) {{ window.location.replace("{newest}/" + m[1]); }}</script>
<meta http-equiv="refresh" content="0; url={newest}/index.html">
<title>EA Explorer: the website</title>
<link rel="stylesheet" href="{newest}/assets/site.css">
</head>
<body>
<main class="page"><article>
<h1>EA Explorer: the website</h1>
<p>Opening the website for EA Explorer {html.escape(newest)}. Each release has its own copy:</p>
<ul class="cards-list">{rows}</ul>
</article></main>
</body>
</html>
"""


# ---------------------------------------------------------------- build and check
def build(write: bool = True, made: dict | None = None) -> list[str]:
    """Builds the site; returns what is wrong (a link to nowhere, a page with no title, a role with no page). `made`, when
    given, receives every file's text by its path in the site (a test compares them with the folder)."""
    if write:       # the error guide, from the one list of error codes (Release 7.9, D787)
        import importlib.util
        spec = importlib.util.spec_from_file_location("error_guide", Path(__file__).with_name("error_guide.py"))
        guide = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guide)
        guide.PAGE.write_text(guide.page(), encoding="utf-8", newline="\n")
    pages = collect()
    sources: dict[str, str] = {}
    for p in pages:
        if p.source:
            sources[str((ROOT / p.source).resolve())] = p.out
    problems = []
    outs = {p.out for p in pages} | {"search.html"} | {f"manuals/{g['file']}" for g in printed_guides() if g["bytes"]}
    files: dict[str, str] = {}
    for p in pages:
        if not p.title.strip():
            problems.append(f"{p.source or p.out}: no title")
        page_html = render(p, pages, sources)
        files[p.out] = page_html
        for href in re.findall(r'href="([^"]+)"', page_html):
            if href.startswith(("http://", "https://", "mailto:", "#")) or href.endswith(".css"):
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(p.out), href.split("#")[0]))
            if target.startswith("..") or (target not in outs and not target.startswith("assets/")):
                problems.append(f"{p.source or p.out}: a link to nowhere: {href}")
    problems += WIKI_MISSES
    for code, _name, _line in ROLES:
        if f"roles/{code}.html" not in outs:
            problems.append(f"no page for {code} (docs/site/roles/{code}.md)")
        if not any(code in p.roles for p in pages if p.out.startswith("how-do-i/")):
            problems.append(f"no How do I page for {code}")
    for p in pages:
        for r in p.roles:
            if r not in ROLE_NAME:
                problems.append(f"{p.source}: no role called {r}")
        if p.out.startswith("how-do-i/") and p.out != "how-do-i/index.html":
            if not p.screens:
                problems.append(f"{p.source}: no screen (the screen its picture shows)")
            for s in p.screens:
                if not re.fullmatch(r"(#/|/)[A-Za-z0-9_\-/{}?=&%.]*", s):
                    problems.append(f"{p.source}: a screen is an address in EA Explorer (#/... or /...): {s}")
    pictures: dict[str, bytes] = {f"shots/{s.name}": s.read_bytes() for s in listed(SHOTS, "*.png")} if SHOTS.is_dir() else {}
    guides = printed_guides()
    printed: dict[str, bytes] = {f"manuals/{g['file']}": (DOCUMENTS / g["file"]).read_bytes() for g in guides if g["bytes"]}
    files["manuals/manuals.json"] = json.dumps({"version": version(), "guides": [g for g in guides if g["bytes"]]}, indent=1)
    files["search.html"] = search_page()
    files["assets/search-index.js"] = search_index(pages)
    for name in ("site.css", "site.js"):
        files[f"assets/{name}"] = (SRC / "assets" / name).read_text(encoding="utf-8")
    if made is not None:
        made.update(files)
        made.update(pictures)
        made.update(printed)   # the PDFs are part of the site too (D799)
    if write:
        if SITE.is_dir():   # what an older build left at the top (before each release had its own folder)
            for old in SITE.iterdir():
                if not (old.is_dir() and _release_dir(old.name)) and old.name not in ("index.html", "README.txt"):
                    shutil.rmtree(old) if old.is_dir() else old.unlink()
        if OUT.exists():
            shutil.rmtree(OUT)
        (OUT / "assets").mkdir(parents=True)
        for name, text in files.items():
            (OUT / name).parent.mkdir(parents=True, exist_ok=True)
            (OUT / name).write_text(text, encoding="utf-8")
        for name in ("site.css", "site.js"):
            shutil.copyfile(SRC / "assets" / name, OUT / "assets" / name)
        (OUT / "assets" / "search-index.js").write_text(search_index(pages), encoding="utf-8")
        for name, data in pictures.items():
            (OUT / name).parent.mkdir(parents=True, exist_ok=True)
            (OUT / name).write_bytes(data)
        for name, data in printed.items():   # the printed guides, from documents/ (D785)
            (OUT / name).parent.mkdir(parents=True, exist_ok=True)
            (OUT / name).write_bytes(data)
        SHOTS.mkdir(parents=True, exist_ok=True)
        (SHOTS / "screens.json").write_text(screens_list(pages), encoding="utf-8")
        (OUT / "README.txt").write_text(
            "The EA Explorer website, made by tools/build_website.py from docs/site, docs/guides and releases.\n"
            "Do not edit these files: change the Markdown and build again.\n"
            "To publish it anywhere (GitHub Pages, a web server, a file share), copy this whole folder.\n"
            f"Inside EA Explorer it is at /site/{version()}/.\n", encoding="utf-8")
        (SITE / "index.html").write_text(front_page(releases_on_disk()), encoding="utf-8")
        (SITE / "README.txt").write_text(
            "The EA Explorer website: one folder for each release (made by tools/build_website.py); index.html opens\n"
            "the newest. To publish it, copy this whole folder, or one release's folder on its own.\n", encoding="utf-8")
    return problems


def main(argv: list[str]) -> int:
    """python tools/build_website.py [--check]."""
    problems = build(write="--check" not in argv)
    for p in problems:
        print(f"  {p}")
    print("The website: " + (f"{len(problems)} problem(s)" if problems else f"built in {OUT.relative_to(ROOT)}"
                             if "--check" not in argv else "no problems"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
