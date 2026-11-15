"""R5.31 (owner, 15 Nov 2026, 21:43: "from this full test remove backup and restore testing of infrastructure,
application is ok. We will test backup and restore using a test backup-restore which can run from command line")."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "services/api"))


def test_the_full_test_takes_no_infrastructure_backup():
    src = (REPO / "services/api/eax/testing/backups_check.py").read_text()
    assert '"/api/v1/admin/backups/infrastructure", {"tag": tag}' not in src
    assert "eax test backup-restore" in src
    from eax.testing import FULL_SUITES, SUITES
    assert "restore" in SUITES and "backup" in FULL_SUITES          # the application backup stays in the full test
    assert "backup-restore" in (REPO / "services/ops/testruns.py").read_text()   # the command line's alias of restore


def test_web_backups_count_as_proven_from_either():
    assert "x.suite IN ('backup', 'restore')" in (REPO / "services/api/eax/api/backups.py").read_text()
