"""R5.23 (bug, 15 Nov 2026): the clean rebuild failed. The Reports image asked for Pillow 13, which needs Python 3.11, and
Superset 6.1.0's image is Python 3.10, so uv found no solution and `eax up` stopped. Pillow stays Superset's own and its
findings on that image are accepted until the version review (D699)."""
from datetime import date
from pathlib import Path

from eax.testing import security_gate

ROOT = Path(__file__).resolve().parents[3]


def _fixed() -> str:
    df = (ROOT / "deploy/superset/Dockerfile").read_text(encoding="utf-8")
    return df.split("FIXED='", 1)[1].split("'", 1)[0]


def test_the_reports_image_does_not_ask_for_a_pillow_its_python_cannot_install():
    df = (ROOT / "deploy/superset/Dockerfile").read_text(encoding="utf-8")
    assert "apache/superset:6.1.0" in df                       # Python 3.10 (the rebuild's log: 3.10.21)
    assert "pillow" not in _fixed().lower()                     # Pillow 13 requires Python >= 3.11
    assert "Brotli>=1.2.1" in _fixed() and "import psycopg2, authlib, PIL" in df


def _pillow(where="image superset"):
    return security_gate.finding("trivy", "CVE-2026-0001", "CRITICAL", "pillow 11.3.0 (fixed in 13.0.0)", where, fix=True)


def test_pillow_on_the_superset_image_is_accepted_until_the_version_review():
    accept = security_gate.accepted([ROOT / "services/api/eax/testing/security_accepted.json"])
    entry = next(a for a in accept if a["id"] == "package:pillow")
    assert entry["where"] == "image superset" and entry["until"] == "2027-02-01" and entry["reason"]
    got = security_gate.gate([_pillow()], accept, today=date(2026, 11, 15))
    assert not got["failing"] and len(got["accepted"]) == 1
    # after the date it fails again
    assert security_gate.gate([_pillow()], accept, today=date(2027, 2, 2))["failing"]


def test_a_package_acceptance_is_kept_to_its_package_and_its_image():
    accept = [{"id": "package:pillow", "where": "image superset", "reason": "r", "until": "2099-01-01", "by": "", "file": ""}]
    other_image = _pillow("image api")
    other_pkg = security_gate.finding("trivy", "CVE-2026-0002", "HIGH", "pillowx 1.0 (fixed in 2.0)", "image superset")
    not_trivy = security_gate.finding("code", "package:pillow", "HIGH", "pillow", "image superset")
    got = security_gate.gate([other_image, other_pkg, not_trivy], accept, today=date(2026, 11, 15))
    assert len(got["failing"]) == 3 and not got["accepted"]
    # a package acceptance with no image named accepts nothing
    loose = [{**accept[0], "where": ""}]
    assert security_gate.gate([_pillow()], loose, today=date(2026, 11, 15))["failing"]
