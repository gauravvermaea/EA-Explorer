"""A model package with data whose extras are not a deep package's histories (self-test 15, 25 Nov 2026: downloading the
run's model as a package, and planning a merge, which reads a package of the model it comes from, both failed with
KeyError 'metamodel_versions'). A package with data always carries the model's icons and reports, and its drawn views
when it has any, in the same parts as a deep package's histories, and the writer took any part at all for the histories.
Now the histories are written only when they are there; the extras as before (owner, 25 Nov 2026, 19:33: "please fix
bugs")."""

import io
import json
import sys
import zipfile
from pathlib import Path
from unittest import mock

import pytest

API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API))

from eax import model_ops as mo  # noqa: E402

MANIFEST = {"format": "eax-package/1", "counts": {}, "model": {"name": "m"}}
SPEC = {"entity_types": [], "relationship_types": [], "pick_lists": [], "rules": [], "allowed": []}
CONTENT = {"entities": {}, "relationships": []}
EXTRAS = {"icons": [{"key": "app", "content_type": "image/svg+xml", "content": "<svg/>"}], "reports": {"kpis": [1]},
          "views": {"drawn_views": [{"id": 1}]}}


def _names(data: bytes) -> set[str]:
    return set(zipfile.ZipFile(io.BytesIO(data)).namelist())


def test_a_package_with_data_and_no_histories_is_written():
    data, name, ctype = mo.write_package(MANIFEST, SPEC, CONTENT, dict(EXTRAS), "zip", "m")
    names = _names(data)
    assert name == "m.zip" and ctype == "application/zip"
    assert {"icons/app.svg", "icons/icons.json", "reports/reports.json", "views/drawn_views.json"} <= names
    assert not any(n.startswith("history/") for n in names)


def test_a_deep_package_still_writes_its_histories():
    hist = {**EXTRAS, "metamodel_versions": [{"version": 1}], "metamodel_changes": [], "rows": [], "changes": []}
    names = _names(mo.write_package(MANIFEST, SPEC, CONTENT, hist, "zip", "m-deep")[0])
    assert {"history/metamodel-versions.csv", "history/metamodel-changes.csv", "history/changes.csv",
            "history/history.json"} <= names


def test_a_package_without_data_has_no_extras_at_all():
    """hist is None for a package without data (run 16's dev check: test_relationship_attributes caught it)."""
    names = _names(mo.write_package(MANIFEST, SPEC, CONTENT, None, "zip", "m")[0])
    assert not any(n.startswith(("history/", "icons/", "views/")) for n in names)


def test_the_workbook_takes_the_same_rule():
    openpyxl = pytest.importorskip("openpyxl")
    if isinstance(openpyxl, mock.Mock):
        pytest.skip("openpyxl not installed here")
    data = mo.write_package(MANIFEST, SPEC, CONTENT, {"icons": EXTRAS["icons"]}, "xlsx", "m")[0]
    assert "Metamodel versions" not in openpyxl.load_workbook(io.BytesIO(data)).sheetnames


def test_the_rule_is_the_histories_being_there():
    src = (API / "eax/model_ops.py").read_text(encoding="utf-8")
    assert src.count('if hist and "metamodel_versions" in hist:') == 2     # hist may be None (a package without data)
    assert json.dumps(MANIFEST)                       # unchanged by the writer
