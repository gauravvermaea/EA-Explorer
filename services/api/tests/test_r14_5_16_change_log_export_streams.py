"""The change log export reads and writes a line at a time (self-test 14, 25 Nov 2026: exporting the whole change log of the
owner's laptop took the API past its 2 GB, Docker restarted it and every call for the next minute failed; owner, 19:33:
"please fix bugs"). Before, every row was held three times: the rows, the lines, and the workbook's cells. Now the rows
are read a batch at a time (stream_results) and written as they come (CSV, or openpyxl's write-only workbook). What the
file holds is unchanged: the same headings, a line a changed field, the newest first."""

import csv
import io
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax import change_log as cl  # noqa: E402


def _row(i, details):
    return {"at": datetime(2026, 11, 25, 10, 0, i), "model_name": "M", "username": "eaadmin", "kind_name": "Content",
            "action": "update", "item_type": "entity", "item_name": f"App {i}", "entity_type": "ApplicationComponent",
            "details": details, "summary": f"changed {i}", "commit_number": i, "commit_message": "msg"}


class Log:
    """The change log's connection: keeps the options it was given and hands the rows out one by one."""
    def __init__(self, rows):
        self.rows, self.options, self.handed = rows, {}, 0

    def execution_options(self, **k):
        self.options.update(k)
        return self

    def execute(self, sql, params):
        log = self

        class Result:
            def mappings(self):
                for r in log.rows:
                    log.handed += 1
                    yield r
        return Result()


@pytest.fixture()
def plain(monkeypatch):
    monkeypatch.setattr(cl, "_need_super", lambda *a, **k: None)
    monkeypatch.setattr(cl, "scope", lambda *a, **k: None)
    monkeypatch.setattr(cl, "_where", lambda *a, **k: ("true", {}))
    monkeypatch.setattr(cl, "_out", lambda r: r)
    monkeypatch.setattr(cl, "schema", lambda: "changelog")
    monkeypatch.setattr(cl, "text", lambda s: s)


ROWS = [_row(1, [{"field": "Owner", "old": "A", "new": "B"}, {"field": "Cost", "old": None, "new": 5}]), _row(2, None)]


def test_the_rows_are_read_a_batch_at_a_time_and_given_a_line_at_a_time(plain):
    log = Log(ROWS)
    lines = cl.export_lines(log, "SELECT 1", {})
    assert isinstance(lines, types.GeneratorType) and log.handed == 0        # nothing read until a line is wanted
    first = next(lines)
    assert log.handed == 1 and log.options == {"stream_results": True, "max_row_buffer": cl.EXPORT_BATCH}
    assert first[:3] == ["2026-11-25 10:00:01", "M", "eaadmin"] and first[8:11] == ["Owner", "A", "B"]
    rest = list(lines)
    assert [x[8:11] for x in rest] == [["Cost", "", 5], ["", "", ""]]       # a line a field; none: one line


def test_the_csv_is_as_before(plain):
    data, name, ctype = cl.export(None, None, {}, "csv", cl=Log(ROWS))
    assert name.startswith("change-log-") and name.endswith(".csv") and ctype == "text/csv; charset=utf-8"
    text = data.decode("utf-8")
    assert text.startswith("﻿")
    got = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert got[0] == cl.EXPORT_HEAD and len(got) == 4
    assert got[1][6] == "App 1" and got[1][11:] == ["changed 1", "1", "msg"]


def test_the_workbook_is_written_as_it_goes_and_reads_as_before(plain):
    openpyxl = pytest.importorskip("openpyxl")
    if isinstance(openpyxl, mock.Mock):                       # a stand-in where openpyxl is not installed
        pytest.skip("openpyxl not installed here")
    data, name, ctype = cl.export(None, None, {}, "xlsx", cl=Log(ROWS))
    assert name.endswith(".xlsx") and "spreadsheetml" in ctype
    ws = openpyxl.load_workbook(io.BytesIO(data))["Change log"]
    assert [c.value for c in ws[1]] == cl.EXPORT_HEAD and ws["A1"].font.bold
    assert ws.max_row == 4 and ws.freeze_panes == "A2" and ws.auto_filter.ref == "A1:N4"
    assert ws["I2"].value == "Owner" and ws["K3"].value == "5" and ws.column_dimensions["L"].width == 60


def test_the_file_is_never_built_from_a_list_of_every_row():
    src = (API / "eax/change_log.py").read_text(encoding="utf-8")
    body = src[src.index("def export(conn"):src.index("def export(conn") + 2400]
    assert "Workbook(write_only=True)" in body and ".all()" not in body and "flat = []" not in body
