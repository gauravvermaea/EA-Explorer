"""Imports the EA Explorer report dashboards into Superset in one process (phase 8.2).

Phase 5 ran `superset import-dashboards` once per dashboard. Each run starts the whole of Superset again
(10 to 20 seconds), which was fine for 32 dashboards and far too slow for 111. This script starts Superset
once and imports every zip in /rendered/superset/reports with the same command the CLI uses, one dashboard at
a time, so one that fails does not stop the others. A dashboard whose zip has not changed since the last
import (same SHA-256, kept in superset_home) and still in Superset is skipped, so later starts are quick.

Importing a dashboard does not change a dataset Superset has already (D946; run 20, 26 Nov 2026: DR-01's dataset kept
its old SQL, "layer AS domain", after the database function's column became domain, and three dashboards failed). So each
dashboard imported is followed by its datasets, imported on their own and overwritten. RULES is part of each stamp: when
how a dashboard is imported changes, every dashboard is imported again once, whatever its zip.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from zipfile import ZipFile

REPORTS = Path("/rendered/superset/reports")
STAMPS = Path("/app/superset_home/eax-report-imports.json")
RULES = "datasets-overwritten"          # D946: the datasets too; changing it imports every dashboard again once


def _contents(bundle: ZipFile) -> dict[str, str]:
    try:   # what `superset import-dashboards` reads (the zip's top folder removed)
        from superset.commands.importers.v1.utils import get_contents_from_bundle
        return get_contents_from_bundle(bundle)
    except ImportError:
        return {name.split("/", 1)[1] if "/" in name else name: bundle.read(name).decode("utf-8")
                for name in bundle.namelist() if not name.endswith("/")}


def datasets_only(contents: dict[str, str]) -> dict[str, str]:
    """A dashboard bundle's databases and datasets, as a dataset bundle (what ImportDatasetsCommand accepts)."""
    out = {k: v for k, v in contents.items() if k.startswith(("databases/", "datasets/"))}
    if not any(k.startswith("datasets/") for k in out):
        return {}
    out["metadata.yaml"] = f"version: 1.0.0\ntype: SqlaTable\ntimestamp: '{time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())}'\n"
    return out


def stamp(digest: str) -> str:
    """What is kept for a zip imported: its SHA-256 and the import rules it was imported by."""
    return f"{digest}:{RULES}"


def main() -> int:
    if not REPORTS.is_dir():         # the full self-test, 14 Nov 2026: Reports' container had no /rendered, none imported
        print(f"EA Explorer WARNING: {REPORTS} is not in this container (the volume eax-rendered is not mounted): "
              "no report dashboard can be imported", flush=True)
        return 1
    zips = sorted(REPORTS.glob("*.zip"))
    if not zips:
        print("EA Explorer: no report dashboards to import")
        return 0
    from flask import g

    from superset.app import create_app

    app = create_app()
    with app.app_context():
        from superset import db
        from superset import security_manager as sm
        try:
            from superset.commands.dashboard.importers.dispatcher import ImportDashboardsCommand
        except ImportError:   # Superset before 4.0
            from superset.dashboards.commands.importers.dispatcher import ImportDashboardsCommand
        try:
            from superset.commands.dataset.importers.dispatcher import ImportDatasetsCommand
        except ImportError:   # Superset before 4.0
            from superset.datasets.commands.importers.dispatcher import ImportDatasetsCommand

        from superset.models.dashboard import Dashboard

        g.user = sm.find_user(username="admin")
        have = {d.slug for d in db.session.query(Dashboard.slug).all()}
        try:
            stamps = json.loads(STAMPS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stamps = {}
        done = skipped = failed = 0
        started = time.monotonic()
        for i, z in enumerate(zips, 1):
            digest = hashlib.sha256(z.read_bytes()).hexdigest()
            if stamps.get(z.name) == stamp(digest) and z.stem in have:   # unchanged and still there
                skipped += 1
                continue
            try:
                with ZipFile(z) as bundle:
                    contents = _contents(bundle)
                ImportDashboardsCommand(contents, overwrite=True).run()
                ds = datasets_only(contents)
                if ds:                       # the dashboard's datasets as they are now, their SQL and columns (D946)
                    ImportDatasetsCommand(ds, overwrite=True).run()
                stamps[z.name] = stamp(digest)
                done += 1
                print(f"EA Explorer: imported report {z.stem} ({i} of {len(zips)})", flush=True)
            except Exception as exc:  # noqa: BLE001 - one failure must not stop the others
                db.session.rollback()
                stamps.pop(z.name, None)
                failed += 1
                print(f"EA Explorer WARNING: report {z.stem} failed to import ({exc}); the other reports still work", flush=True)
        for gone in set(stamps) - {z.name for z in zips}:
            stamps.pop(gone, None)
        try:
            STAMPS.write_text(json.dumps(stamps, indent=1), encoding="utf-8")
        except OSError as exc:
            print(f"EA Explorer WARNING: could not keep the import stamps ({exc}); every report is imported again next start")
        print(f"EA Explorer: report dashboards imported: {done} new or changed, {skipped} unchanged, {failed} failed "
              f"({time.monotonic() - started:.0f} s)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - Superset still works without the reports
        print(f"EA Explorer WARNING: importing the report dashboards failed: {exc}")
        sys.exit(0)
