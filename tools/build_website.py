"""The EA Explorer website: plain HTML built from the repository (Release 7, R7.1 and R7.7, D738, D776).

The owner, 18 Nov 2026, 12:54: "There needs to be a Website. The website needs to be a sub folder inside the application
and I should be just able to copy it seperately and publish it. The help guides need to be sub pages inside the website";
"They should be able to print them as pdf so build them printable".

    python tools/build_website.py            writes services/web/public/site/ (committed; the app serves it at /site/)
    python tools/build_website.py --check    builds it in memory and says what is wrong (a test runs this)

Sources (Markdown, a small front matter between --- lines: title, summary, roles):
  docs/site/index.md                 the home page
  docs/site/roles/*.md               what EA Explorer has for each kind of person
  docs/site/how-do-i/*.md            one task each, printable (roles: who it is for)
  docs/site/*.md                     the other pages (videos, further reading)
  docs/guides/*.md                   Install and run: the setup guides (eaxcli/setup.py writes them)
  releases/*.md                      Releases: every release's notes

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
OUT = ROOT / "services" / "web" / "public" / "site"
YOUTUBE = "https://www.youtube.com/@ea-explorer-os"
GITHUB = "https://github.com/gauravvermaea/EA-Explorer"

ROLES = [   # (code, the name people know it by, one line)
    ("system-admin", "System Admin", "Run the installation: people, security, backups, updates, health"),
    ("model-admin", "Model Admin", "Look after models and their metamodels: people, quality, versions, merges"),
    ("project-admin", "Project Admin", "Run architecture projects: templates, phases, deliverables, sign-off"),
    ("user", "Users", "Find, change, draw, report and commit the architecture"),
    ("industry-modeller", "Industry model makers", "Build reference models and metamodels for an industry"),
    ("developer", "Developers", "Bring data in and take it out: the API, feeds, formats, scripts, AI"),
]
ROLE_NAME = {c: n for c, n, _ in ROLES}
# the How do I topics, in the order a person meets them (the owner, 18 Nov 2026, 13:01: "Group them by some common")
GROUP_ORDER = ["Getting around", "Working with content", "Views and reports", "Projects", "Models", "Metamodels",
               "Data quality", "Versions and merging", "Industry models", "Bringing data in", "Taking data out",
               "Access for systems", "People and access", "Security", "Backups and recovery", "Running it",
               "Surveys and maturity", "AI"]
SECTIONS = [("index.html", "Home"), ("roles/index.html", "Your role"), ("how-do-i/index.html", "How do I"),
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
        h = re.match(r"^(#{1,4})\s+(.*)$", line)
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
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]  # noqa: E731
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
        lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
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
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
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


def _title_of(md: str, fallback: str) -> tuple[str, str]:
    m = re.match(r"^#\s+(.+)\n?", md)
    return (m.group(1).strip(), md[m.end():]) if m else (fallback, md)


def _version_key(name: str) -> tuple:
    return tuple(int(x) if x.isdigit() else -1 for x in re.split(r"[.\-]", name))


def collect() -> list[Page]:
    """Every page of the site, from docs/site, docs/guides and releases."""
    pages: list[Page] = []

    def read(p: Path) -> tuple[dict, str]:
        return front_matter(p.read_text(encoding="utf-8"))
    # home, and the other pages at the top
    for p in sorted(SRC.glob("*.md")):
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
    for p in sorted((SRC / "how-do-i").glob("*.md")):
        meta, md = read(p)
        title, md = _title_of(md, p.stem)
        pages.append(Page(f"how-do-i/{p.stem}.html", meta.get("title", title), md, "how-do-i/index.html",
                          meta.get("summary", ""), meta.get("roles", []), meta.get("group", "Other"), str(p.relative_to(ROOT))))
    pages.append(Page("how-do-i/index.html", "How do I", "One task on each page, step by step, ready to print or save as "
                      "PDF. Choose your role, or type to find a task.", "how-do-i/index.html", printable=False))
    # Install and run: the setup guides
    for p in sorted((ROOT / "docs" / "guides").glob("*.md")):
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
    pages.append(Page("releases/index.html", "Releases", "What came in each release, newest first. EA Explorer tells "
                      "every installation about a new release on System Admin › Updates.", "releases/index.html",
                      printable=False, extra_html="<ul class=\"cards-list\">" + "".join(
                          f'<li><a href="{p.stem}.html">{html.escape(_title_of(p.read_text(encoding="utf-8"), p.stem)[0])}</a></li>'
                          for p in notes) + "</ul>"))
    return pages


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
    if not tasks:
        return ""
    return '<h2 id="your-tasks">How do I: your tasks</h2>' + _tiles(tasks, frm)


def _index_html(page: Page, pages: list[Page]) -> str:
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

    return ""


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
           if page.roles and page.out.startswith("how-do-i/") else "")
    tools = (f'<p class="page-tools"><button type="button" class="print">Print or save as PDF</button></p>'
             if page.printable else "")
    asset = lambda name: _rel(page.out, f"assets/{name}")  # noqa: E731
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
    {toc}
    {body}
    {extra}
  </article>
</main>
<footer class="foot">
  <span>EA Explorer: free and open source (AGPL-3.0).</span>
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


# ---------------------------------------------------------------- build and check
def build(write: bool = True, made: dict | None = None) -> list[str]:
    """Builds the site; returns what is wrong (a link to nowhere, a page with no title, a role with no page). `made`, when
    given, receives every file's text by its path in the site (a test compares them with the folder)."""
    pages = collect()
    sources: dict[str, str] = {}
    for p in pages:
        if p.source:
            sources[str((ROOT / p.source).resolve())] = p.out
    problems = []
    outs = {p.out for p in pages} | {"search.html"}
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
    for code, _name, _line in ROLES:
        if f"roles/{code}.html" not in outs:
            problems.append(f"no page for {code} (docs/site/roles/{code}.md)")
        if not any(code in p.roles for p in pages if p.out.startswith("how-do-i/")):
            problems.append(f"no How do I page for {code}")
    for p in pages:
        for r in p.roles:
            if r not in ROLE_NAME:
                problems.append(f"{p.source}: no role called {r}")
    files["search.html"] = search_page()
    files["assets/search-index.js"] = search_index(pages)
    for name in ("site.css", "site.js"):
        files[f"assets/{name}"] = (SRC / "assets" / name).read_text(encoding="utf-8")
    if made is not None:
        made.update(files)
    if write:
        if OUT.exists():
            shutil.rmtree(OUT)
        (OUT / "assets").mkdir(parents=True)
        for name, text in files.items():
            (OUT / name).parent.mkdir(parents=True, exist_ok=True)
            (OUT / name).write_text(text, encoding="utf-8")
        for name in ("site.css", "site.js"):
            shutil.copyfile(SRC / "assets" / name, OUT / "assets" / name)
        (OUT / "assets" / "search-index.js").write_text(search_index(pages), encoding="utf-8")
        (OUT / "README.txt").write_text(
            "The EA Explorer website, made by tools/build_website.py from docs/site, docs/guides and releases.\n"
            "Do not edit these files: change the Markdown and build again.\n"
            "To publish it anywhere (GitHub Pages, a web server, a file share), copy this whole folder.\n"
            "Inside EA Explorer it is at /site/.\n", encoding="utf-8")
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
