"""D946: a dashboard's datasets are imported again, overwritten, with it (run 20, 26 Nov 2026: DR-01's dataset kept its
old SQL, "layer AS domain", after the database function's column became domain; DR-01, IT operations and Change manager
failed as both people)."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[3] / "deploy" / "superset" / "eax_import_reports.py"
spec = importlib.util.spec_from_file_location("eax_import_reports", HERE)
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

BUNDLE = {"metadata.yaml": "version: 1.0.0\ntype: Dashboard\n", "dashboards/DR-01.yaml": "x", "charts/c.yaml": "y",
          "databases/EA_Explorer.yaml": "d", "datasets/EA_Explorer/dr_dependencies.yaml": "sql: SELECT domain"}


def test_a_dashboard_bundle_becomes_a_dataset_bundle():
    ds = imp.datasets_only(BUNDLE)
    assert set(ds) == {"metadata.yaml", "databases/EA_Explorer.yaml", "datasets/EA_Explorer/dr_dependencies.yaml"}
    meta = yaml.safe_load(ds["metadata.yaml"])
    assert meta["type"] == "SqlaTable" and meta["version"] == "1.0.0" and meta["timestamp"]


def test_no_dataset_no_import():
    assert imp.datasets_only({"metadata.yaml": "m", "dashboards/x.yaml": "x"}) == {}


def test_the_stamp_carries_the_rules_so_every_dashboard_is_imported_again_once():
    assert imp.stamp("abc") == "abc:datasets-overwritten" != "abc"     # a stamp of before D946 never matches


def test_each_dashboard_imported_is_followed_by_its_datasets_overwritten():
    src = inspect.getsource(imp.main)
    assert "ImportDashboardsCommand(contents, overwrite=True).run()" in src
    assert "ImportDatasetsCommand(ds, overwrite=True).run()" in src
    assert src.index("ImportDashboardsCommand(contents") < src.index("ImportDatasetsCommand(ds")
    assert "stamps.get(z.name) == stamp(digest)" in src and "stamps[z.name] = stamp(digest)" in src
