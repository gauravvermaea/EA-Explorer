"""The ArchiMate version on the New model form, and the database checks of the versions (owner, 28 Nov 2026, 07:59:
"for now just make a screen which during model creation shows a hard coded drop down to arhcimate 4 ... Please ensure
there are tests 1. this hard code 2. DB tests for the verision we just talked about"; D965, D966).

1. The form's drop-down is written in the screen (ARCHIMATE_VERSIONS): ArchiMate 4.0 and nothing else, chosen at the
   start, with its on-screen help; the self-test's browser journey opens the form and sees it.
2. The database side runs in every full test on the live database (eax/testing/db_checks.py, seven checks): ArchiMate
   4.0 is a version, the ArchiMate root metamodel says it (the extensions do not), an end is never before its start nor
   without one, what replaces an item is another item of its own model, a copy keeps its origin's versions. Each was
   run on PostgreSQL 16 when built: nothing found on a clean database, and each found the fault made for it."""

from __future__ import annotations

import json
import re
from pathlib import Path

from eax.seed import archimate4 as A
from eax.seed import build as B
from eax.testing import db_checks, ui_flows

WEB = Path(__file__).resolve().parents[2] / "web" / "src"
SRC = (WEB / "ModelOps.jsx").read_text(encoding="utf-8")


# ---------------------------------------------------------------- 1. the hard-coded drop-down
def test_the_versions_offered_are_archimate_40_only():
    m = re.search(r"export const ARCHIMATE_VERSIONS = (\[.*?\]);", SRC)
    assert m and json.loads(m.group(1)) == [["4.0", "ArchiMate 4.0"]]


def test_the_new_model_form_shows_it_chosen_from_the_start():
    form = SRC[SRC.index("export function NewModelDialog"):SRC.index("export function NewModelButton")]
    assert "useState(ARCHIMATE_VERSIONS[0][0])" in form
    assert '<Field label="ArchiMate version"' in form and 'aria-label="ArchiMate version"' in form
    assert "ARCHIMATE_VERSIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)" in form
    assert form.index('label="ArchiMate version"') < form.index('label="Start from"')       # beside the name, before the source


def test_it_has_on_screen_help():
    help_ = json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))
    assert "ArchiMate 4.0" in help_["field:ArchiMate version"]


def test_the_browser_journey_sees_it():
    j = next(f for f in ui_flows.JOURNEYS if f["name"] == "new model: the ArchiMate version is 4.0")
    steps = [s.get("expect") or s.get("click") or s.get("expect_not") for s in j["steps"]]
    assert steps == ["New model", "+ New model", "ArchiMate version", "ArchiMate 4.0", "Cancel", "ArchiMate version"]
    assert "+ New model" in (WEB / "ModelOps.jsx").read_text(encoding="utf-8")


# ---------------------------------------------------------------- 2. the database checks of the versions
NAMES = ["ArchiMate 4.0 is a standard version (D965)", "the ArchiMate root metamodel says its ArchiMate version (D965)",
         "an extension says no ArchiMate version (D965)", "an item's end version is not before its start (D965)",
         "an item has an end version only with a start (D965)",
         "what replaces an item is another item of its own model (D965)",
         "a copied metamodel item keeps its origin's version (D965)"]


def test_the_seven_checks_run_in_every_full_test():
    have = {n: (q, o) for n, q, o in db_checks.CHECKS}
    for n in NAMES:
        assert n in have and have[n][1] == "failed", n
        assert n not in db_checks.IN_TESTS_DB                                        # on the repository's database


def test_they_name_the_seeds_archimate_model_and_its_extensions():
    assert db_checks._ARCHIMATE_ROOT == B.TEMPLATE_ID  # noqa: SLF001 - the check's own constant against the seed's
    assert db_checks._EXTENSIONS == tuple(sorted(A.EXTENSION_DESCRIPTIONS))  # noqa: SLF001


def test_each_check_covers_every_versioned_table():
    have = {n: q for n, q, _ in db_checks.CHECKS}
    for n in NAMES[3:]:
        for t in ("domains", "entity_types", "relationship_types", "allowed_relationships"):
            assert f"core.{t} x" in have[n], (n, t)
    assert "e.sort_order < s.sort_order" in have[NAMES[3]] and "e.standard <> s.standard" in have[NAMES[3]]
    assert "r.model_id <> x.model_id OR r.id = x.id" in have[NAMES[5]]
    assert all(" LIMIT " in q for n, q in have.items() if n in NAMES[1:])        # read-only and bounded
    assert not any(re.search(r"\b(INSERT|UPDATE|DELETE)\b", have[n]) for n in NAMES)
