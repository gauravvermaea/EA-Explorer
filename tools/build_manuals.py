"""The printed guides (Release 7, D783; 25 with the error code guide, D790): PDF guides made from the content already in the repository, each with a
cover, a page saying what it is for (About this guide) and a table of contents with page numbers; people print them and
keep them (the owner, 18 Nov 2026, 19:11: "Please make pdf's professional with cover, purpose, TOC ... as seperate pdf
documents from the content we have created. We expect people to print and keep them").

    python tools/build_manuals.py [--only 01-overview,15-eax-commands] [--out documents] [--html]

What goes in each guide is docs/manuals/manuals.json: its chapters, and for each chapter the pages, the sections of
documents, the How do I pages (with their pictures, docs/site/shots) and the parts of the eax command's own help that
make it. Content written for the guides alone (where nothing existed) is in docs/manuals/new and was agreed with the
owner first. Notes kept for the people who build EA Explorer (decision numbers such as D255, phases, stories) are
left out of the printed text.

The PDFs go to documents/ at the top of the repository (in git, for anyone who has the code; the owner, 18 Nov 2026,
21:00: "I also want them to be copied in the root folder of git into documents"), with a README listing them; the
website copies them from there (tools/build_website.py, Printed guides). The HTML they were printed from is kept in
work/manuals/html. It is run by `eax site pdfs`, in the test runner (Chromium and pypdf are there), with the repository at /repo:
Chromium prints the cover and the body separately (the body's pages are numbered in the footer, the cover is not), the
body twice: the first time to find the page each chapter and section starts on, the second with those numbers in the
table of contents. pypdf joins the cover and the body and adds the bookmarks. --html writes the HTML only (no browser).
"""

from __future__ import annotations

import html
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "manuals" / "manuals.json"
SHOTS = ROOT / "docs" / "site" / "shots"
HOWDOI = ROOT / "docs" / "site" / "how-do-i"
HELP = ROOT / "eaxcli" / "help.txt"


def _website():
    """tools/build_website.py: its Markdown, front matter and version (one way of writing the pages, D776)."""
    spec = importlib.util.spec_from_file_location("build_website", ROOT / "tools" / "build_website.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_website"] = mod
    spec.loader.exec_module(mod)
    return mod


W = _website()


# ---------------------------------------------------------------- the words: from the repository, made fit to print
# notes for the people who build EA Explorer, in brackets: (D255), (phase 12.1, D255), (R6.6-J1), (owner, 18 Nov ...)
INTERNAL = re.compile(r"\s*\((?=[^()]*\b(?:D\d{2,4}|R\d+(?:\.\d+)*(?:-[A-Z]+\d*)?|[Pp]hases? \d[\d.,/ ]*|owner|story)\b)"
                      r"[^()]*\)")
WIKI = re.compile(r"\[\[([a-z0-9-]+)(?:\|([^\]]+))?\]\]")


def titles() -> dict[str, str]:
    """Every site page's name and its title, for [[wiki]] links written as words."""
    out = {}
    for d in ("concepts", "how-do-i", "guides", "integrate", "platform", "reports", "roles"):
        for p in (ROOT / "docs" / "site" / d).glob("*.md"):
            out[p.stem] = W.front_matter(_read(p))[0].get("title", p.stem.replace("-", " "))
    return out


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def for_print(md: str, names: dict[str, str]) -> str:
    """The Markdown made fit for paper: notes for builders out, wiki links as words, links as words (with the address
    for one outside EA Explorer), pictures of the web pages left to the How do I pictures."""
    md = join_items(md)
    md = WIKI.sub(lambda m: m.group(2) or names.get(m.group(1), m.group(1).replace("-", " ")), md)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    md = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                lambda m: m.group(1) if m.group(1).strip("<>") == m.group(2) else f"{m.group(1)} ({m.group(2)})", md)
    md = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1", md)   # before the notes, so a link inside one goes with it
    md = INTERNAL.sub("", md)
    md = re.sub(r"\(\s*\)", "", md)
    # bold around code (**`eax_migrator`**) is not drawn as bold by the site's Markdown: the code alone
    md = "\n".join(_bold_around_code(line) for line in md.split("\n"))
    # whole sentences that only point at the decisions ("Decisions D522 to D525 and D529; build notes in ...")
    md = re.sub(r"(?<![^\s.])Decisions? D\d[^.\n]*(?:\.|$)\s*", "", md, flags=re.M)
    # "since R2.0.1", "From phase 3.1": when it came, which a reader does not need
    md = re.sub(r"\b([Ss]ince|[Aa]fter|[Ff]rom) (?:R\d+(?:\.\d+)*(?:-[A-Z]+\d*)?|phase \d[\d.]*),?\s+(\w)",
                lambda m: m.group(2).upper() if m.group(1)[0].isupper() else m.group(2), md)
    # the site's own links to other pages ("Related", "Each task, one page" already lists the tasks that follow)
    md = re.sub(r"(?ms)^##\s+Related\s*\n.*?(?=^#{1,2}\s|\Z)", "", md)
    return md


def _bold_around_code(line: str) -> str:
    """Bold that holds code (**`eax_migrator`**, **`PACK.sha256`: the pack arrived whole.**) is not drawn by the site's
    Markdown, which reads code first: the code is left plain and only the words around it made bold. The ** of a line
    are paired from the left; a line with an odd number of them is left as it is."""
    parts = line.split("**")
    if len(parts) < 3 or len(parts) % 2 == 0:
        return line
    out = [parts[0]]
    for k in range(1, len(parts), 2):
        inner, after = parts[k], parts[k + 1]
        if "`" not in inner:
            out.append(f"**{inner}**")
        else:
            for piece in re.split(r"(`[^`]+`)", inner):
                if piece.startswith("`") or not piece.strip():
                    out.append(piece)
                else:
                    lead, trail = piece[:len(piece) - len(piece.lstrip())], piece[len(piece.rstrip()):]
                    out.append(f"{lead}**{piece.strip()}**{trail}")
        out.append(after)
    return "".join(out)


def join_items(md: str) -> str:
    """A list item written over several lines made one line, so bold or a link that runs over the break is drawn
    (the site's Markdown draws each carried-on line apart). Code blocks are left as they are."""
    out: list[str] = []
    in_code, in_item = False, False
    for line in md.split("\n"):
        if line.startswith("```"):
            in_code = not in_code
            in_item = False
            out.append(line)
            continue
        is_item = bool(re.match(r"^\s*([-*]|\d+\.)\s+\S", line))
        if not in_code and in_item and not is_item and re.match(r"^\s{2,}\S", line):
            out[-1] = out[-1].rstrip() + " " + line.strip()
            continue
        in_item = not in_code and (is_item or (in_item and bool(line.strip())))
        out.append(line)
    return "\n".join(out)


def shift(md: str, by: int) -> str:
    """Headings moved down by `by` levels (a page's ## becomes ### inside a chapter), at most ####."""
    return re.sub(r"^(#{1,4})(\s)", lambda m: "#" * min(4, len(m.group(1)) + by) + m.group(2), md, flags=re.M)


def sections_of(md: str, wanted: list[str]) -> str:
    """Only the ## sections named (each with what is under it, to the next ## or #)."""
    parts = re.split(r"(?m)^(?=#{1,2}\s)", md)
    keep = []
    for part in parts:
        m = re.match(r"#{1,2}\s+(.*)", part)
        if m and any(m.group(1).strip() == w.strip() for w in wanted):
            keep.append(part)
    return "\n".join(keep)


# ---------------------------------------------------------------- the eax command's own help, as a chapter
def help_markdown(sections: list[str] | None = None, commands: list[str] | None = None) -> str:
    """eaxcli/help.txt as Markdown: its sections and commands, each with its summary, detail and examples (D331)."""
    out: list[str] = []
    section, keep_section, keep = "", True, False
    detail: list[str] = []

    def flush():
        """The detail under a command: its prose as paragraphs, its option lines (indented) as a block."""
        block: list[str] = []
        prose: list[str] = []
        for d in detail + [""]:
            if d.startswith("  "):
                if prose:
                    out.extend([" ".join(prose), ""])
                    prose.clear()
                block.append(d[2:])
            elif block and d.startswith(" " * 6):   # an option's words carried on
                block.append(d[2:])
            else:
                if block:
                    out.extend(["```", *block, "```", ""])
                    block.clear()
                if d.strip():
                    prose.append(d.strip())
        if prose:
            out.extend([" ".join(prose), ""])
        detail.clear()
    for raw in _read(HELP).split("\n"):
        line = re.sub(r"^\[(?:win|unix|ps1|sh|py)\]", "", raw).replace("{eax}", "eax")
        if raw.startswith(";") or raw.startswith("@"):
            continue
        if raw.startswith("## "):
            flush()
            section = raw[3:].strip()
            keep_section = sections is None or section in sections
            keep = keep_section and commands is None
            if keep:
                out += [f"## {section}", ""]
            continue
        if raw.startswith("### "):
            flush()
            sig = raw[4:].strip()
            name = sig.split()[0].split("|")[0]
            keep = (commands is None and keep_section) or (commands is not None and name in commands)
            if keep:
                out += [f"### eax {name}", "", f"`eax {sig}`", ""]
            continue
        if not keep or not section:
            continue
        if line.startswith("> "):
            flush()
            out += [f"**{line[2:].strip()}**", ""]
        elif line.startswith("$ "):
            flush()
            out += ["```", line[2:].strip(), "```", ""]
        elif line.startswith(": "):
            flush()
            out += [f"> **Note** {line[2:].strip()}", ""]
        elif line.strip():
            detail.append(line)
        else:
            flush()
    flush()
    return "\n".join(out)


# ---------------------------------------------------------------- a guide, put together
def specs_listed() -> list[dict]:
    """Every guide manuals.json lists, in order."""
    return json.loads((ROOT / "docs" / "manuals" / "manuals.json").read_text(encoding="utf-8"))["manuals"]


class Guide:
    """One printed guide: its chapters, each made of sections (title, Markdown, its picture)."""

    def __init__(self, spec: dict, names: dict[str, str]):
        self.spec, self.names = spec, names
        self.chapters: list[dict] = []
        self.howdoi = {p.stem: p for p in HOWDOI.glob("*.md")}
        self.problems: list[str] = []
        for ch in spec["chapters"]:
            secs = []
            for src in ch["sources"]:
                secs += self.source(src)
            self.chapters.append({"title": ch["title"], "sections": secs})

    def source(self, src: str) -> list[dict]:
        kind, _, what = src.partition(":")
        if kind in ("page", "new"):
            path, _, heads = what.partition("#")
            p = ROOT / path
            if not p.is_file():
                self.problems.append(f"{self.spec['id']}: no {path}")
                return []
            meta, md = W.front_matter(_read(p))
            title, md = W._title_of(md, meta.get("title", p.stem.replace("-", " ").capitalize()))
            title = meta.get("title", title)
            if heads:
                md = sections_of(md, heads.split("|"))
                if not md.strip():
                    self.problems.append(f"{self.spec['id']}: {path} has none of: {heads}")
                    return []
                if len(heads.split("|")) == 1:   # one section: it is the section's own title
                    title = heads.strip()
                    md = re.sub(r"^#{1,2}\s+.*\n", "", md, count=1)
            return [{"title": INTERNAL.sub("", title), "summary": meta.get("summary", ""),
                     "md": shift(for_print(md, self.names), 1), "kind": kind}]
        if kind == "howdoi":
            opts = dict(x.split("=", 1) for x in what.split(";"))
            if "pages" in opts:
                names = [n.strip() for n in opts["pages"].split(",")]
            else:
                names = []
                for stem, p in sorted(self.howdoi.items()):
                    meta = W.front_matter(_read(p))[0]
                    if meta.get("group") == opts["group"] and ("role" not in opts or opts["role"] in meta.get("roles", [])):
                        names.append(stem)
            out = []
            for n in names:
                p = self.howdoi.get(n)
                if not p:
                    self.problems.append(f"{self.spec['id']}: no How do I page {n}")
                    continue
                meta, md = W.front_matter(_read(p))
                shots = [SHOTS / f"{n}.png"] + ([SHOTS / f"{n}-2.png"] if meta.get("screen2") else [])
                out.append({"title": meta.get("title", n), "summary": meta.get("summary", ""), "kind": "howdoi",
                            "md": shift(for_print(md, self.names), 1), "shots": [s for s in shots if s.is_file()],
                            "missing": [s.name for s in shots if not s.is_file()]})
            return out
        if kind == "help":
            opt, _, val = what.partition("=")
            md = help_markdown(sections=val.split("|") if opt == "sections" else None,
                               commands=[c.strip() for c in val.split(",")] if opt == "commands" else None)
            if opt == "all":   # one section per group of commands, so the contents list them
                parts = [x for x in re.split(r"(?m)^## ", md) if x.strip()]
                return [{"title": x.split("\n", 1)[0].strip(), "summary": "", "kind": "help",
                         "md": for_print(x.split("\n", 1)[1] if "\n" in x else "", self.names)} for x in parts]
            return [{"title": "The eax command", "summary": "", "kind": "help", "md": shift(for_print(md, self.names), 1)}]
        self.problems.append(f"{self.spec['id']}: not understood: {src}")
        return []

    # ---- HTML
    def body_html(self, pages: dict[str, int] | None, markers: bool = True) -> str:
        """The body: About this guide, the contents (with page numbers when known), the chapters. Each chapter and
        section starts with a marker the first printing is searched for, to know its page."""
        s = self.spec
        n = lambda key: str(pages.get(key, "")) if pages else ""
        toc = []
        for ci, ch in enumerate(self.chapters, 1):
            toc.append(f'<li class="c"><span class="t">{ci}. {html.escape(ch["title"])}</span><span class="n">{n(f"c{ci}")}</span></li>')
            for si, sec in enumerate(ch["sections"], 1):
                toc.append(f'<li class="s"><span class="t">{html.escape(sec["title"])}</span><span class="n">{n(f"c{ci}s{si}")}</span></li>')
        out = [f'''<section class="about"><h1>About this guide</h1>
<p class="lead">{html.escape(s["purpose"])}</p>
<h3>Who it is for</h3><p>{html.escape(s["audience"])}.</p>
<h3>How to use it</h3><p>Each chapter starts with what you need to know and why, then the tasks. A task ("How do I")
is one job, step by step, with a picture of the screen it is done on. Words in <b>bold</b> are what the screen shows:
a menu, a tab or a button. A path such as <b>System Admin › Backups</b> means the menu, then the item in it.
Commands are typed on the machine where EA Explorer runs: <code>eax</code> stands for <code>.\\eax</code> in
Windows PowerShell and <code>./eax.sh</code> on Linux and macOS.</p>
<h3>This edition</h3><p>EA Explorer {html.escape(W.version())}. The same content is on the EA Explorer website, inside the
application under Documentation, where it is kept current.</p></section>''',
               f'<section class="contents"><h1>Contents</h1><ol class="toc">{"".join(toc)}</ol></section>']
        for ci, ch in enumerate(self.chapters, 1):
            out.append(f'<section class="chapter"><h1><span class="mark">zzqm c{ci} zzqm</span>'
                       f'<span class="num">{ci}</span>{html.escape(ch["title"])}</h1>')
            for si, sec in enumerate(ch["sections"], 1):
                body, _ = W.markdown(sec["md"])
                pics = "".join(f'<figure><img src="{p.resolve().as_uri()}" alt=""><figcaption>The screen: '
                               f'{html.escape(sec["title"])}</figcaption></figure>' for p in sec.get("shots", []))
                pics += "".join(f'<div class="noshot">The picture of this screen ({html.escape(m)}) is added when '
                                f'<code>eax site shots</code> has run.</div>' for m in sec.get("missing", []))
                kind = sec["kind"]
                head = (f'<p class="kind">How do I</p>' if kind == "howdoi" else "")
                summary = f'<p class="summary">{W._inline(sec["summary"], lambda u: u)}</p>' if sec["summary"] else ""
                out.append(f'<article class="{kind}">{head}<h2><span class="mark">zzqm c{ci}s{si} zzqm</span>'
                           f'{html.escape(sec["title"])}</h2>{summary}{pics}{body}</article>')
            out.append("</section>")
        doc = self._doc("".join(out))
        # the markers are 1px and white: taking them out of the second printing moves nothing on the page
        return doc if markers else re.sub(r'<span class="mark">zzqm [^<]* zzqm</span>', "", doc)

    def cover_html(self) -> str:
        s = self.spec
        num = s["id"].split("-")[0]
        total = len(specs_listed())            # as many as manuals.json lists (24 at Release 7, 25 from 7.9, D790)
        return self._doc(f'''<section class="cover">
<div class="band"><div class="brand">EA Explorer</div><div class="series">Guide {num} of {total}</div></div>
<div class="titles"><h1>{html.escape(s["title"])}</h1><p class="for">For {html.escape(s["audience"])}</p>
<p class="purpose">{html.escape(s["purpose"])}</p></div>
<div class="foot"><div>EA Explorer {html.escape(W.version())}</div><div>An open-source enterprise architecture repository</div></div>
</section>''')

    @staticmethod
    def _doc(body: str) -> str:
        return f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'


CSS = """
@page { size: A4; margin: 20mm 18mm 22mm 18mm; }
* { box-sizing: border-box; }
html { font-family: "Segoe UI", "Liberation Sans", "DejaVu Sans", Arial, sans-serif; color: #1d2733; font-size: 10.5pt; line-height: 1.5; }
body { margin: 0; }
h1, h2, h3, h4 { color: #13243d; line-height: 1.25; break-after: avoid; }
code, pre { font-family: "Cascadia Mono", "DejaVu Sans Mono", Consolas, monospace; font-size: 9pt; }
code { background: #eef3fa; padding: 0 3px; border-radius: 3px; }
pre.code { background: #f6f8fb; border: 1px solid #d9dee5; border-left: 3px solid #1f5fb8; border-radius: 4px; padding: 7px 10px;
           white-space: pre-wrap; word-break: break-word; break-inside: avoid; }
pre.code code { background: none; padding: 0; }
a { color: inherit; text-decoration: none; }
.mark { font-size: 1px; color: #ffffff; line-height: 0; }
/* the cover: a page of its own, no footer */
.cover { height: 253mm; display: flex; flex-direction: column; justify-content: space-between; }
.cover .band { background: #1f5fb8; color: #fff; padding: 14mm 12mm 10mm; border-radius: 3mm; }
.cover .brand { font-size: 28pt; font-weight: 700; letter-spacing: .5px; }
.cover .series { font-size: 11pt; opacity: .9; margin-top: 2mm; }
.cover .titles { padding: 0 2mm; }
.cover h1 { font-size: 30pt; margin: 0 0 6mm; color: #13243d; border-left: 6px solid #1f5fb8; padding-left: 6mm; }
.cover .for { font-size: 13pt; color: #5b6775; margin: 0 0 8mm; }
.cover .purpose { font-size: 12pt; max-width: 150mm; }
.cover .foot { display: flex; justify-content: space-between; color: #5b6775; font-size: 10pt; border-top: 1px solid #d9dee5; padding-top: 4mm; }
/* about and contents */
.about h1, .contents h1 { font-size: 20pt; border-bottom: 2px solid #1f5fb8; padding-bottom: 2mm; margin-top: 0; }
.about { break-after: page; }
.about .lead { font-size: 12pt; }
.contents { break-after: page; }
ol.toc { list-style: none; padding: 0; margin: 0; }
ol.toc li { display: flex; align-items: baseline; gap: 6px; break-inside: avoid; }
ol.toc li .t { flex: none; max-width: 85%; }
ol.toc li::after { content: ""; order: 1; flex: 1; border-bottom: 1px dotted #9aa5b1; margin: 0 2px 3px; }
ol.toc li .n { order: 2; flex: none; min-width: 8mm; text-align: right; }
ol.toc li.c { font-weight: 600; margin-top: 3.5mm; font-size: 11pt; }
ol.toc li.s { padding-left: 7mm; font-size: 10pt; color: #33404f; }
/* chapters */
.chapter { break-before: page; }
.chapter > h1 { font-size: 22pt; margin: 0 0 6mm; padding-bottom: 3mm; border-bottom: 2px solid #1f5fb8; }
.chapter > h1 .num { display: inline-block; min-width: 12mm; color: #1f5fb8; }
article { margin-bottom: 7mm; }
article > h2 { font-size: 15pt; margin: 7mm 0 2mm; }
article.howdoi { border-top: 1px solid #d9dee5; padding-top: 3mm; }
article.howdoi > h2 { margin-top: 1mm; }
p.kind { margin: 0; font-size: 8.5pt; text-transform: uppercase; letter-spacing: 1px; color: #1f5fb8; font-weight: 600; }
p.summary { color: #5b6775; font-size: 11pt; margin-top: 0; }
article h3 { font-size: 12pt; margin: 5mm 0 1.5mm; }
article h4 { font-size: 10.5pt; margin: 4mm 0 1mm; }
figure { margin: 3mm 0 4mm; break-inside: avoid; }
figure img { width: 100%; border: 1px solid #c9d1db; border-radius: 3px; }
.noshot { border: 1px dashed #9aa5b1; color: #5b6775; font-size: 9pt; padding: 6mm; margin: 3mm 0; text-align: center; }
figcaption { font-size: 8.5pt; color: #5b6775; margin-top: 1mm; }
blockquote { margin: 3mm 0; padding: 2.5mm 4mm; background: #e8f0fb; border-left: 3px solid #1f5fb8; border-radius: 3px; break-inside: avoid; }
blockquote.careful { background: #fff4d6; border-left-color: #8a4b00; }
blockquote p { margin: 0; }
div.table { break-inside: auto; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 2mm 0 4mm; }
th, td { border: 1px solid #d9dee5; padding: 1.5mm 2mm; text-align: left; vertical-align: top; }
th { background: #eef3fa; }
tr { break-inside: avoid; }
ol, ul { padding-left: 6mm; }
li { margin: 1mm 0; }
"""


def footer(title: str) -> str:
    """The footer of every body page: the guide's name, and the page number."""
    return (f'<div style="font-size:8px;color:#5b6775;width:100%;padding:0 18mm;display:flex;justify-content:space-between;'
            f'font-family:Arial,sans-serif"><span>EA Explorer · {html.escape(title)}</span>'
            f'<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>')


# ---------------------------------------------------------------- printing
def print_guides(guides: list[Guide], out: Path) -> list[str]:
    """Each guide as a PDF in `out`: the cover and the body printed by Chromium, the body twice (the second time with
    the contents' page numbers), joined by pypdf with the bookmarks. Returns the files made."""
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter
    made = []
    work = ROOT / "work" / "manuals" / "html"
    work.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        def pdf(html_text: str, name: str, numbered_title: str | None) -> Path:
            src = work / f"{name}.html"
            src.write_text(html_text, encoding="utf-8")
            page.goto(src.resolve().as_uri(), wait_until="load")
            dest = work / f"{name}.pdf"
            opts = {"path": str(dest), "format": "A4", "print_background": True, "prefer_css_page_size": True}
            if numbered_title:
                opts.update(display_header_footer=True, header_template="<span></span>", footer_template=footer(numbered_title))
            page.pdf(**opts)
            return dest
        for g in guides:
            gid, title = g.spec["id"], g.spec["title"]
            cover = pdf(g.cover_html(), f"{gid}-cover", None)
            first = pdf(g.body_html(None), f"{gid}-body", title)
            where: dict[str, int] = {}
            for i, pg in enumerate(PdfReader(str(first)).pages, 1):
                for key in re.findall(r"zzqm\s*(c\d+(?:s\d+)?)\s*zzqm", (pg.extract_text() or "").replace("\n", " ")):
                    where.setdefault(key, i)
            body = pdf(g.body_html(where, markers=False), f"{gid}-body", title)
            w = PdfWriter()
            for f in (cover, body):
                for pg in PdfReader(str(f)).pages:
                    w.add_page(pg)
            w.add_metadata({"/Title": f"EA Explorer: {title}", "/Author": "EA Explorer", "/Subject": g.spec["purpose"]})
            for ci, ch in enumerate(g.chapters, 1):
                if f"c{ci}" not in where:
                    continue
                parent = w.add_outline_item(f"{ci}. {ch['title']}", where[f"c{ci}"])   # +1 for the cover, -1 to count from 0
                for si, sec in enumerate(ch["sections"], 1):
                    if f"c{ci}s{si}" in where:
                        w.add_outline_item(sec["title"], where[f"c{ci}s{si}"], parent=parent)
            dest = out / f"EA-Explorer-{gid}.pdf"
            with dest.open("wb") as fh:
                w.write(fh)
            made.append(dest.name)
            print(f"  {dest.name}: {len(w.pages)} pages", flush=True)
        browser.close()
    return made


def main(argv: list[str]) -> int:
    """Builds the guides asked for (all by default)."""
    only, out, html_only = set(), ROOT / "documents", False
    i = 0
    while i < len(argv):
        if argv[i] == "--only" and i + 1 < len(argv):
            only = {x.strip() for x in argv[i + 1].split(",") if x.strip()}
            i += 1
        elif argv[i] == "--out" and i + 1 < len(argv):
            out = Path(argv[i + 1])
            i += 1
        elif argv[i] == "--html":
            html_only = True
        else:
            print(f"Not understood: {argv[i]}. Usage: build_manuals.py [--only ID,ID] [--out FOLDER] [--html]")
            return 2
        i += 1
    specs = json.loads(MANIFEST.read_text(encoding="utf-8"))["manuals"]
    names = titles()
    guides = [Guide(s, names) for s in specs if not only or s["id"] in only]
    problems = [p for g in guides for p in g.problems]
    for p in problems:
        print(f"  {p}")
    if problems:
        print(f"{len(problems)} problem(s): nothing printed.")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    if html_only:
        for g in guides:
            (out / f"{g.spec['id']}.html").write_text(g.body_html(None), encoding="utf-8")
        print(f"{len(guides)} guide(s) written as HTML in {out}.")
        return 0
    made = print_guides(guides, out)
    if not only:
        (out / "README.md").write_text(readme(specs), encoding="utf-8")
    print(f"{len(made)} guide(s) printed in {out}.")
    return 0


def readme(specs: list[dict]) -> str:
    """documents/README.md: the guides, what each is for and who it is for."""
    rows = "\n".join(f"| {s['id'].split('-')[0]} | [{s['title']}](EA-Explorer-{s['id']}.pdf) | {s['audience']} |" for s in specs)
    return ("# EA Explorer: the printed guides\n\n"
            f"The {len(specs)} guides of EA Explorer {W.version()} as PDF, to print and keep. Each has a cover, what it is for, who it is\n"
            "for, and a table of contents. They are made from the documentation in this repository by `eax site pdfs`\n"
            "(tools/build_manuals.py); do not edit them here. The same guides are on the website under Printed guides, and in\n"
            "EA Explorer under Documentation › Printed guides.\n\n| No. | Guide | For |\n|---|---|---|\n" + rows + "\n")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
