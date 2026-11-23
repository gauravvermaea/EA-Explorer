"""D895: the "not for AI use" check reads the first page of a file only (owner, 23 Nov 2026: "no file should be checked
in full ... only check 1st page of every document"). The full test sat at 24% for over an hour on the shipped-packs
test, which read every page of the thirteen 230 to 500 page pack books (ten minutes without coverage). The product's
loader (eax/industry_packs.py) and `eax packs` (eaxcli/packs.py) read the same first page."""

from __future__ import annotations

import io
import sys
import time
import zipfile
from pathlib import Path

import pytest

from eax import industry_packs as ip

ROOT = Path(__file__).resolve().parents[3]
MARK = "NOT FOR AI USE OR AUTOMATED PROCESSING"


def _pdf(*pages: str) -> bytes:
    """A small PDF with one line of text on each page."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids, font = [], 3
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {len(objs)} 0 R "
                    f"/Resources << /Font << /F1 {font} 0 R >> >> >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def _zip(parts: dict[str, str]) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, x in parts.items():
            z.writestr(n, x)
    return b.getvalue()


def _xlsx(first: str, second: str) -> bytes:
    """A workbook: the first sheet's cell uses shared word 0, the second sheet's uses shared word 1."""
    return _zip({"xl/sharedStrings.xml": f"<sst><si><t>{first}</t></si><si><t>{second}</t></si></sst>",
                 "xl/worksheets/sheet1.xml": '<worksheet><sheetData><row><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>',
                 "xl/worksheets/sheet2.xml": '<worksheet><sheetData><row><c r="A1" t="s"><v>1</v></c></row></sheetData></worksheet>'})


def _pptx(first: str, second: str) -> bytes:
    return _zip({"ppt/slides/slide1.xml": f"<p:sld><a:t>{first}</a:t></p:sld>",
                 "ppt/slides/slide2.xml": f"<p:sld><a:t>{second}</a:t></p:sld>"})


def _docx(header: str, body: str) -> bytes:
    return _zip({"word/header1.xml": f"<w:hdr><w:t>{header}</w:t></w:hdr>",
                 "word/document.xml": f"<w:document><w:t>{body}</w:t></w:document>"})


LATER = "x " * 4000                         # more than a page of words before the marking


def _pypdf():
    try:
        import pypdf  # noqa: F401
    except Exception:                       # noqa: BLE001 - a machine without the PDF reader
        pytest.skip("no PDF reader here")


def test_a_pdf_is_checked_on_its_first_page_only():
    _pypdf()
    assert ip.restricted("a.pdf", _pdf(MARK, "Chapter one"))
    assert not ip.restricted("a.pdf", _pdf("Retail - the architecture workbook", MARK))


def test_a_workbook_deck_and_word_file_are_checked_on_their_first_page_only():
    assert ip.restricted("a.xlsx", _xlsx(MARK, "Capabilities"))
    assert not ip.restricted("a.xlsx", _xlsx("Capabilities", MARK))
    assert ip.restricted("a.pptx", _pptx(MARK, "Views"))
    assert not ip.restricted("a.pptx", _pptx("Views", MARK))
    assert ip.restricted("a.docx", _docx(MARK, "Body"))                       # a header is on the first page
    assert ip.restricted("a.docx", _docx("", "Title. " + MARK))
    assert not ip.restricted("a.docx", _docx("", LATER + MARK))
    assert ip.restricted("a.txt", (MARK + " " + LATER).encode())
    assert not ip.restricted("a.txt", (LATER * 4 + MARK).encode())


def test_eax_packs_reads_the_same_first_page_as_the_loader():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eaxcli import packs
    samples = [("a.xlsx", _xlsx(MARK, "x")), ("a.xlsx", _xlsx("x", MARK)), ("a.pptx", _pptx("x", MARK)),
               ("a.docx", _docx(MARK, LATER)), ("a.txt", (LATER * 4 + MARK).encode()), ("broken.docx", b"not a zip")]
    for name, data in samples:
        assert packs.first_page_text(name, data) == ip.first_page_text(name, data), name
        assert bool(packs.AI_MARK.search(packs.first_page_text(name, data))) == ip.restricted(name, data), name


def test_the_shipped_packs_are_checked_in_seconds():
    """Every shipped pack file through the check: was ten minutes (every page), now the first page of each."""
    _pypdf()
    files = [f for f in (ROOT / "library" / "industry-packs").rglob("*")
             if f.is_file() and not f.name.endswith(".parts.json") and ".part" not in f.suffix]
    t0 = time.perf_counter()
    for f in files:
        ip.restricted(f.name, f.read_bytes())
    assert time.perf_counter() - t0 < 120


def test_a_test_that_runs_long_says_where_it_is():
    """The unit tests print a long-running test's stack after 5 minutes (pytest's faulthandler_timeout), so a run that
    seems stuck names its test (23 Nov 2026)."""
    import tomllib
    conf = tomllib.loads((ROOT / "services" / "api" / "pyproject.toml").read_text(encoding="utf-8"))
    assert conf["tool"]["pytest"]["ini_options"]["faulthandler_timeout"] == 300
