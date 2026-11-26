"""D950: the project report's CSV (run 22, 26 Nov 2026: "script error at #/projects/.../report: s.map is not a function"
on clicking "CSV (opens in Excel)"): downloadCsv takes rows of values with the headings first; the status rows are objects."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web" / "src"
TABS = (WEB / "ProjectTabs.jsx").read_text(encoding="utf-8").replace("\r\n", "\n")   # the file may be kept with CRLF
NODE = shutil.which("node")


def test_the_report_hands_the_csv_rows_of_values():
    assert "downloadCsv(statusCsv(rows), `${p.name} status`)" in TABS
    assert "downloadCsv(rows, `${p.name} status`)" not in TABS


@pytest.mark.skipif(not NODE, reason="node is not here")
def test_the_csv_has_headings_and_a_line_a_phase():
    cols = re.search(r"const STATUS_COLUMNS = (\[.*?\]\]);", TABS, re.S).group(1)
    fn = re.search(r"export const statusCsv = (.*?);\n", TABS).group(1)
    to_csv = re.search(r"(function cell\(v\) \{.*?\n\}\n\nexport function toCsv\(rows\) \{.*?\n\})", (WEB / "exporting.js").read_text(
        encoding="utf-8").replace("\r\n", "\n"), re.S).group(1).replace("export ", "")
    rows = [{"phase": "Phase A", "steps": 4, "steps_done": 1, "classes": 2, "classes_with_documents": 1, "documents": 3, "draft": 2,
             "in_review": 1, "accepted_or_approved": 0, "rejected": 0, "checked_out": 0}]
    script = f"{to_csv}\nconst STATUS_COLUMNS = {cols};\nconst statusCsv = {fn};\nconsole.log(toCsv(statusCsv({json.dumps(rows)})));"
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    assert lines[0].startswith("Phase,Steps done,Steps,Classes with documents") and lines[1] == "Phase A,1,4,1,2,3,2,1,0,0,0"
