"""The restore drills as PDF (R5.6; owner, 16 Nov 2026, 15:49, on the restore drills: "document this for someone and
also have them available as pdf for download. Steps in comman line"; 15:55: "we only needed pdf for drills not
everything else"): the drill documents (shipped_docs.PDF_DOCS) can be downloaded as a PDF, made here with ReportLab from
their Markdown (no browser needed). It can draw any shipped document; only the drills are offered.

What is drawn: headings (#, ##, ###, ####), paragraphs, bullet and numbered lists (one level of nesting), code blocks
(the command-line steps, in a box, kept whole), tables, rules; inline **bold**, *italics*, `code` and [links](...) as
their text. Every character is escaped before the few marks are turned into ReportLab's own tags, so nothing in a
document is read as markup. The command line's help (plain text) is drawn as it is.
"""

from __future__ import annotations

import html
import io
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_ss = getSampleStyleSheet()
H = {1: ParagraphStyle("dh1", parent=_ss["Heading1"], fontSize=18, spaceAfter=6),
     2: ParagraphStyle("dh2", parent=_ss["Heading2"], fontSize=14, spaceBefore=10, spaceAfter=4),
     3: ParagraphStyle("dh3", parent=_ss["Heading3"], fontSize=11.5, spaceBefore=8, spaceAfter=3),
     4: ParagraphStyle("dh4", parent=_ss["Heading4"], fontSize=10, spaceBefore=6, spaceAfter=2)}
P = ParagraphStyle("dp", parent=_ss["BodyText"], fontSize=9.5, leading=13)
CELL = ParagraphStyle("dc", parent=P, fontSize=8, leading=10)
CODE = ParagraphStyle("dcode", parent=_ss["Code"], fontSize=8, leading=10, backColor=colors.HexColor("#f1f3f5"),
                      borderColor=colors.HexColor("#ced4da"), borderWidth=0.5, borderPadding=4, leftIndent=4, rightIndent=4,
                      spaceBefore=4, spaceAfter=8)
LONG_CELL = 900                 # characters: a table with a longer cell is drawn a paragraph a row
FOOT = ParagraphStyle("dfoot", parent=P, fontSize=7, textColor=colors.HexColor("#868e96"))


def inline(s: str) -> str:
    """One line's text, escaped first, then **bold**, *italics*, `code` and [text](link) (as its text). Code is set
    aside first, so a mark inside it stays as it is."""
    t = html.escape(s, quote=False)
    codes: list[str] = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"
    t = re.sub(r"`([^`]+)`", keep, t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*\s][^*]*)\*(?!\w)", r"<i>\1</i>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: f'<font face="Courier">{codes[int(m.group(1))]}</font>', t)


CODE_WIDTH = 92                 # characters of a command line that fit the page at the code's size


def wrap_code(lines: list[str], width: int = CODE_WIDTH) -> list[str]:
    """A command line longer than the page broken at spaces, its continuation indented (pure): nothing is cut off."""
    out: list[str] = []
    for ln in lines:
        lead = len(ln) - len(ln.lstrip(" "))
        while len(ln) > width:
            cut = ln.rfind(" ", lead + 10, width)
            if cut < 0:
                cut = width
            out.append(ln[:cut])
            ln = " " * (lead + 4) + ln[cut:].lstrip(" ")
        out.append(ln)
    return out


def para(text: str, style) -> Paragraph:
    """A paragraph of Markdown text; one the PDF library cannot read is drawn as its plain text instead."""
    try:
        return Paragraph(inline(text), style)
    except ValueError:
        return Paragraph(html.escape(text, quote=False), style)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def flowables(text: str) -> list:
    """The document's Markdown as ReportLab flowables."""
    out: list = []
    lines = text.splitlines()
    i, lines_open, items, numbered = 0, [], [], False

    def flush_para():
        nonlocal lines_open
        if lines_open:
            out.append(para(" ".join(x.strip() for x in lines_open), P))
            lines_open = []

    def flush_list():
        nonlocal items
        if items:
            out.append(ListFlowable([ListItem(para(x, P), leftIndent=12) for _n, x in items],
                                    bulletType="1" if numbered else "bullet", start=str(items[0][0]) if numbered else None,
                                    leftIndent=14, bulletFontSize=8))     # a numbered list keeps its own numbers
            items = []

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```"):
            flush_para()
            flush_list()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            out.append(KeepTogether([Preformatted("\n".join(wrap_code(block)), CODE)]))
        elif m := re.match(r"^(#{1,4})\s+(\S.*|)$", s):
            flush_para()
            flush_list()
            out.append(para(m.group(2), H[len(m.group(1))]))
        elif s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
            flush_para()
            flush_list()
            rows = [_cells(s)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            width = max(len(r) for r in rows)
            if any(len(c) > LONG_CELL for r in rows for c in r):     # a cell longer than a page: one paragraph a row
                head = rows[0]
                for r in rows[1:]:
                    out.append(para(" · ".join(f"**{h}**: {c}" if h else c for h, c in zip(head, r, strict=False) if c), P))
                continue
            data = [[para(c, CELL) for c in r + [""] * (width - len(r))] for r in rows]
            t = Table(data, repeatRows=1, colWidths=[(A4[0] - 36 * mm) / width] * width)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ced4da")),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            out.append(t)
            out.append(Spacer(1, 6))
            continue
        elif m := re.match(r"^(?:[-*+]|(\d+)[.)])\s+(\S.*|)$", s):
            flush_para()
            is_num = m.group(1) is not None
            if items and is_num != numbered:
                flush_list()
            numbered = is_num
            items.append([int(m.group(1)) if is_num else 0, m.group(2)])
        elif re.match(r"^(-{3,}|\*{3,})$", s):
            flush_para()
            flush_list()
            out.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#ced4da"), spaceBefore=4, spaceAfter=4))
        elif not s:
            flush_para()
            flush_list()
        elif items and ln.startswith(("  ", "\t")) and not lines_open:
            items[-1][1] += " " + s                   # a list item's continuation line
        else:
            flush_list()
            lines_open.append(s)
        i += 1
    flush_para()
    flush_list()
    return out


def pdf(title: str, text: str, version: str, plain: bool = False) -> bytes:
    """The document as a PDF: its title, its body, and on every page the version and the page number."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=title, author="EA Explorer")
    body = [Preformatted(text, CODE)] if plain else flowables(text)
    if not body or not isinstance(body[0], Paragraph) or body[0].style is not H[1]:
        body.insert(0, para(title, H[1]))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#868e96"))
        canvas.drawString(18 * mm, 9 * mm, f"EA Explorer {version} · {title}"[:120])
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"page {d.page}")
        canvas.restoreState()
    doc.build(body, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
