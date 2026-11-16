"""Template setup: download and see a template (owner, 16 Nov 2026, 14:03: "In tempalte setup we should be able to
download and see a template. This is missing please add this feature"; asked how, chose "Outline only")."""
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
API = Path(__file__).resolve().parents[1]
REPO = API.parents[1]
WEB = REPO / "services/web/src"
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, t in files.items():
            z.writestr(n, t)
    return buf.getvalue()


def _para(text, style=""):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"


def test_word_shows_its_headings_and_paragraphs():
    from eax import file_outline as fo
    doc = _zip({"word/document.xml": f'<w:document {W}><w:body>{_para("Architecture Vision", "Title")}'
                f'{_para("1. Scope", "Heading1")}{_para("What the work covers.")}{_para("1.1 Out of scope", "Heading2")}'
                f'{_para("")}</w:body></w:document>'})
    out = fo.outline("vision.docx", doc)
    assert out["show"] == "outline" and out["kind"] == "docx"
    assert out["blocks"] == [{"type": "heading", "level": 0, "text": "Architecture Vision"},
                             {"type": "heading", "level": 1, "text": "1. Scope"},
                             {"type": "paragraph", "text": "What the work covers."},
                             {"type": "heading", "level": 2, "text": "1.1 Out of scope"}]


def test_powerpoint_shows_each_slides_title_and_text():
    from eax import file_outline as fo
    ns = ('xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
          'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')

    def slide(title, *lines):
        t = f'<p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>'
        b = "".join(f"<a:p><a:r><a:t>{x}</a:t></a:r></a:p>" for x in lines)
        return f'<p:sld {ns}><p:cSld><p:spTree>{t}<p:sp><p:nvSpPr><p:nvPr/></p:nvSpPr><p:txBody>{b}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    deck = _zip({"ppt/slides/slide2.xml": slide("Roadmap", "Q1", "Q2"), "ppt/slides/slide10.xml": slide("Next steps"),
                 "ppt/slides/slide1.xml": slide("Stakeholders", "Board")})
    out = fo.outline("deck.pptx", deck)
    assert [(s["number"], s["title"], s["lines"]) for s in out["blocks"]] == [
        (1, "Stakeholders", ["Board"]), (2, "Roadmap", ["Q1", "Q2"]), (3, "Next steps", [])]   # slide 10 after 2


def test_excel_shows_each_sheet_and_its_first_rows():
    from openpyxl import Workbook

    from eax import file_outline as fo
    wb = Workbook()
    ws = wb.active
    ws.title = "Principles"
    for i in range(40):
        ws.append([f"P{i}", "statement"])
    wb.create_sheet("Empty")
    buf = io.BytesIO()
    wb.save(buf)
    out = fo.outline("catalogue.xlsx", buf.getvalue())
    p, e = out["blocks"]
    assert p["name"] == "Principles" and p["rows_total"] == 40 and len(p["rows"]) == fo.MAX_ROWS and p["rows"][0] == ["P0", "statement"]
    assert e["name"] == "Empty" and e["rows"] == []


def test_pdf_and_pictures_are_shown_as_they_are_others_are_said():
    from eax import file_outline as fo
    assert fo.outline("a.pdf", b"%PDF-1.4")["show"] == "file"
    assert fo.outline("a.PNG", b"x")["show"] == "file"
    other = fo.outline("model.vsdx", b"x")
    assert other["show"] == "none" and "download it" in other["note"]
    assert fo.outline("notes.md", b"# A\nline two")["blocks"] == [{"type": "line", "text": "# A"}, {"type": "line", "text": "line two"}]


def test_a_damaged_or_hostile_file_is_said_never_an_error():
    from eax import file_outline as fo
    bad = fo.outline("broken.docx", b"not a zip")
    assert bad["show"] == "none" and "could not be read" in bad["note"]
    bomb = _zip({"word/document.xml": '<!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
                                      f'<w:document {W}><w:body>{_para("&b;")}</w:body></w:document>'})
    assert fo.outline("bomb.docx", bomb)["show"] == "none"          # defusedxml refuses entities
    assert fo.outline("big.docx", b"x" * (fo.MAX_BYTES + 1))["show"] == "none"


def test_the_api_the_screen_and_the_policy():
    api = (API / "eax/api/projects.py").read_text()
    assert '@blp.route("/projects/library/templates/<int:template_id>/outline")' in api and "file_outline.outline(name, data)" in api
    page = (WEB / "TemplateSetup.jsx").read_text()
    assert "setViewing(t)" in page and ">View</button>" in page and ">Download</button>" in page and "<TemplateView" in page
    assert "/templates/${t.id}/file`" in page and "/outline`" in page
    csp = (REPO / "deploy/proxy/templates/default.conf.template").read_text()
    assert "frame-src 'self' blob:;" in csp                         # a fetched PDF shown in a frame
