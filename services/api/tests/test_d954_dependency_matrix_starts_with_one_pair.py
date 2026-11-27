"""D954: the dependency matrix (DR-02) opens with one row type and one column type (full tests of 26 and 27 Nov 2026: as
the Super Admin, with no type chosen, the matrix of every entity against every other froze the browser; the next
dashboard, DR-01, then never opened: "Page.goto: Timeout 300000ms exceeded")."""

from __future__ import annotations

from eax.setup import superset_reports as sr


def _filters(code: str) -> dict[str, dict]:
    report = next(r for r in sr.REPORTS if r["code"] == code)
    return {f["name"]: f for f in sr.dashboard_filters(report, sr.charts_for(report))}


def test_the_row_and_column_types_are_needed_and_the_first_is_chosen():
    f = _filters("DR-02")
    for name in ("Row type", "Column type"):
        assert f[name]["controlValues"]["enableEmptyFilter"] is True
        assert f[name]["controlValues"]["defaultToFirstItem"] is True
        assert f[name]["controlValues"]["multiSelect"] is False
    assert f["Relationship type"]["controlValues"]["enableEmptyFilter"] is False


def test_other_filters_stay_optional():
    for r in sr.REPORTS:
        if r["code"] == "DR-02":
            continue
        for f in sr.dashboard_filters(r, sr.charts_for(r)):
            assert f["controlValues"]["enableEmptyFilter"] is False, (r["code"], f["name"])
