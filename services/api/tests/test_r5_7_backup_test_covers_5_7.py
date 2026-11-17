"""R5.7-T1 (owner, 17 Nov 2026, 13:48): the backup and restore test (and so the DR drill, which runs it) makes, reads
back, compares and checks after the restores what Release 5.7 adds: a customer journey with every kind of part, a
part of a kind added by people, a link to a model element, a target copy and a comparison; an uploaded theme and a
person's own theme; and the deck tools reading the restored project."""
from pathlib import Path

from eax.testing import backup_restore as br

SRC = (Path(__file__).resolve().parents[1] / "eax" / "testing" / "backup_restore.py").read_text(encoding="utf-8")


def test_the_test_makes_what_5_7_adds():
    for want in ('"change_customer_journey"', '"template": "starter"', '"score": -1', '"part": "persona"', "journey-kinds",
                 '"action": "link"', '"action": "copy"', '"compare_with": target', "/api/v1/admin/branding/themes",
                 "/api/v1/me/settings/theme", '"deck_outline"'):
        assert want in SRC, want


def test_it_reads_back_compares_and_checks_after_the_restores():
    assert br.READ_BACK_PROJECT["journeys"] and br.READ_BACK["branding_themes"]
    assert "proj.journey_items" in SRC and "core.branding_themes" in SRC          # in the snapshot compared after B1 and B2
    assert '"deck_sources"' in SRC and "the restored journey compares with its target" in SRC


def test_it_never_changes_what_everyone_sees_and_cleans_up():
    assert "/api/v1/admin/branding\"" not in SRC and "/api/v1/admin/branding/logo" not in SRC
    assert 'f"/api/v1/admin/branding/themes/{state[\'ids\'][\'theme\']}"' in SRC
