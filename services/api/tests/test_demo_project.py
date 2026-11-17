"""The demo project (owner, 17 Nov 2026, 15:18; D734): Protea Claims Transformation 2028 gathers every kind of content
in one project with its models, pinned for the demo account demo-super-admin."""
from pathlib import Path

from eax import permissions as perms
from eax.seed import sample_demo as sd

API = Path(__file__).resolve().parents[1]


def test_the_demo_account_is_a_super_admin_on_the_laptop():
    assert ("demo-super-admin", "eax-super-admin", {}) in perms.TEST_USERS
    assert '("demo-super-admin", "eax-super-admin"' in (API.parents[1] / "eaxcli" / "info.py").read_text(encoding="utf-8")


def test_the_demo_project_gets_every_kind_it_lacks_and_is_pinned():
    src = (API / "eax" / "seed" / "sample_demo.py").read_text(encoding="utf-8")
    for part in ("_governance", "_decisions", "_stakeholders", "_standards", "_tasks", "_signoff", "_pins", "_scenario", "_mark"):
        assert f"def {part}(" in src, part
    assert sd.PROJECT == "Protea Claims Transformation 2028 (sample)" and sd.DEMO_USER == "demo-super-admin"
    assert {"Protea Insurance (demo estate)", "Protea claims target 2028", "Protea claims transition 2027"} <= set(sd.MODELS)
    assert 'set_favourite(conn, DEMO_USER, "project"' in src and 'set_favourite(conn, DEMO_USER, "model"' in src


def test_it_runs_last_with_the_sample_data():
    later = (API / "eax" / "seed" / "later.py").read_text(encoding="utf-8")
    assert later.index("sample_branding))") < later.index("sample_demo))") < later.index("sample_tests))")
