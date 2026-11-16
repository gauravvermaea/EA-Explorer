"""What a file holds, as text, to see it in the browser without downloading it (owner, 16 Nov 2026, 14:03: "In tempalte
setup we should be able to download and see a template"; asked how, chose "Outline only").

  PDF and pictures   shown as they are by the browser (the file itself): {"show": "file"}
  Word (.docx)       the headings, each with its level, and the paragraphs under them
  PowerPoint (.pptx) each slide's title and its text
  Excel (.xlsx)      each sheet's name, size and its first rows
  text (.txt, .md, .csv)  its first lines
  anything else      what it is and its size, to download

Read with the standard library and openpyxl, the XML through defusedxml (no entities, no outside references); a file
over MAX_BYTES, or one that is not what its name says, is said so, never an error. Nothing is kept. Pure: tested alone.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from defusedxml import ElementTree as SafeET

MAX_BYTES = 30 * 1024 * 1024
MAX_BLOCKS = 400              # paragraphs, slides' lines, rows: the outline is a look, not the whole file
MAX_ROWS = 15
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
PICTURES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
TEXTS = (".txt", ".md", ".csv")


def _kind(name: str) -> str:
    n = (name or "").lower()
    if n.endswith(".pdf"):
        return "pdf"
    if n.endswith(PICTURES):
        return "picture"
    for ext in ("docx", "pptx", "xlsx"):
        if n.endswith(f".{ext}") or n.endswith(f".{ext[:-1]}m"):
            return ext
    if n.endswith(TEXTS):
        return "text"
    return "other"


def _docx(data: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = SafeET.fromstring(z.read("word/document.xml"))
    blocks: list[dict] = []
    for p in root.iter(f"{W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
        if not text:
            continue
        style = p.find(f"{W}pPr/{W}pStyle")
        sv = (style.get(f"{W}val") if style is not None else "") or ""
        low = sv.lower().replace(" ", "")
        if low == "title":
            blocks.append({"type": "heading", "level": 0, "text": text})
        elif low.startswith("heading") and low[7:].isdigit():
            blocks.append({"type": "heading", "level": int(low[7:]), "text": text})
        else:
            blocks.append({"type": "paragraph", "text": text[:600]})
        if len(blocks) >= MAX_BLOCKS:
            break
    return blocks


def _pptx(data: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        names.sort(key=lambda n: int("".join(ch for ch in n.rsplit("/", 1)[-1] if ch.isdigit()) or 0))
        slides = []
        for i, n in enumerate(names[:MAX_BLOCKS], start=1):
            root = SafeET.fromstring(z.read(n))
            title, lines = "", []
            for sp in root.iter(f"{P}sp"):
                ph = sp.find(f".//{P}nvPr/{P}ph")
                paras = ["".join(t.text or "" for t in para.iter(f"{A}t")).strip() for para in sp.iter(f"{A}p")]
                paras = [x for x in paras if x]
                if ph is not None and (ph.get("type") or "") in ("title", "ctrTitle") and not title:
                    title = " ".join(paras)
                else:
                    lines += paras
            slides.append({"type": "slide", "number": i, "title": title or f"Slide {i}", "lines": [x[:300] for x in lines[:30]]})
    return slides


def _xlsx(data: bytes) -> list[dict]:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheets = []
    try:
        for ws in wb.worksheets[:50]:
            rows = []
            for r in ws.iter_rows(max_row=MAX_ROWS, values_only=True):
                cells = ["" if v is None else str(v)[:120] for v in r[:20]]
                if any(cells):
                    rows.append(cells)
            sheets.append({"type": "sheet", "name": ws.title, "rows_total": ws.max_row or 0, "columns_total": ws.max_column or 0,
                           "rows": rows})
    finally:
        wb.close()
    return sheets


def outline(name: str, data: bytes) -> dict[str, Any]:
    """{name, kind, size, show: "file" | "outline" | "none", blocks, note}: what the file holds, as text."""
    kind, size = _kind(name), len(data or b"")
    out: dict[str, Any] = {"name": name, "kind": kind, "size": size, "show": "outline", "blocks": [], "note": ""}
    if kind in ("pdf", "picture"):
        return {**out, "show": "file"}
    if kind == "other":
        return {**out, "show": "none", "note": "This kind of file cannot be shown here: download it to open it."}
    if size > MAX_BYTES:
        return {**out, "show": "none", "note": f"Too large to show here ({size // (1024 * 1024)} MB): download it to open it."}
    try:
        if kind == "docx":
            out["blocks"] = _docx(data)
        elif kind == "pptx":
            out["blocks"] = _pptx(data)
        elif kind == "xlsx":
            out["blocks"] = _xlsx(data)
        else:
            text = data[:200_000].decode("utf-8", "replace")
            out["blocks"] = [{"type": "line", "text": ln[:300]} for ln in text.splitlines()[:MAX_BLOCKS]]
    except Exception as exc:  # noqa: BLE001 - a damaged file, or one that is not what its name says: said, never an error
        return {**out, "show": "none", "note": f"It could not be read as {kind.upper()}: download it to open it ({str(exc)[:120]})."}
    if not out["blocks"]:
        out["note"] = "It holds no text to show (pictures or an empty template): download it to see it all."
    elif len(out["blocks"]) >= MAX_BLOCKS:
        out["note"] = "The beginning only: download it to see it all."
    return out
