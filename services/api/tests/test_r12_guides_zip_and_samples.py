"""Release 12: the organisation's own guides as a zip (R12.12, D885) and what the Release 12 samples hold (R12.7).

Run while building (23 Nov 2026) on a real PostgreSQL, the document store stood in for: a zip with three guides in two
folders (and a computer's hidden files) went in under Organisation guides with its folders kept, each tagged; the same
zip again with one file changed kept a new version of that file only; a zip with a path climbing out, a file that is
not a zip, an empty zip and a zip bomb were refused. The risk, data, digital and plan content of the samples was made
through the screens' own functions on a model of the right kind; the risk register then listed both risks logged."""

from __future__ import annotations

import inspect
import io
import json
import zipfile
from pathlib import Path

import pytest

from eax import first_run as fr
from eax import reference_library as rl
from eax.metamodel_edit import EditError
from eax.seed import build, later
from eax.seed import sample_r12 as sr

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "web" / "src"


def _zip(files: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


# ---------------------------------------------------------------- the guides zip
def test_a_zip_keeps_its_folders_and_leaves_out_hidden_files():
    out = rl.zip_files(_zip({"Security/Passwords.md": "a", "Security/Cloud/Cloud use.md": "b", "Style.md": "c",
                             "__MACOSX/._Style.md": "x", ".DS_Store": "x"}))
    assert sorted((f, n) for f, n, _d in out) == [("", "Style.md"), ("Security", "Passwords.md"), ("Security/Cloud", "Cloud use.md")]


@pytest.mark.parametrize("data, says", [
    (_zip({"../../etc/passwd": "x"}), "leaves its folder"),
    (_zip({"/root.txt": "x"}), "leaves its folder"),
    (b"not a zip", "not a zip file"),
    (_zip({}), "holds no files"),
    (_zip({"big.txt": "0" * 5_000_000}), "unpacks to far more"),
])
def test_unsafe_zips_are_refused(data, says):
    with pytest.raises(EditError, match=says):
        rl.zip_files(data)


def test_too_many_files_refused(monkeypatch):
    monkeypatch.setattr(rl, "ZIP_MAX_FILES", 2)
    with pytest.raises(EditError, match="3 files: 2 at most"):
        rl.zip_files(_zip({"a": "1", "b": "2", "c": "3"}))


def test_the_guides_go_into_documents_tagged_and_again_as_versions():
    src = inspect.getsource(rl.add_zip)
    assert "add_file(conn, user," in src and "new_version(conn, user," in src and "same += 1" in src
    assert rl.GUIDES_FOLDER == "Organisation guides" and rl.GUIDE_TAG == "Organisation guide"
    assert "_need_write(user)" in src                                # Super Admins
    api = (ROOT / "eax" / "api" / "projects.py").read_text(encoding="utf-8")
    assert '"/reference-library/guides-zip")' in api


def test_an_optional_setup_step():
    step = [s for s in fr.STEPS if s[0] == "guides"][0]
    assert "(optional)" in step[1] and step[3] == "#/reference-library?upload=guides"
    assert '"Organisation guide"' in inspect.getsource(fr._seen)
    ui = (WEB / "ReferenceLibrary.jsx").read_text(encoding="utf-8")
    assert "function GuidesZipDialog(" in ui and "upload=guides" in ui and "⬆ Guides as a zip" in ui
    assert "button:⬆ Guides as a zip" in json.loads((WEB / "help" / "catalogue.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the samples
def test_every_release_12_sample_gets_a_plan_and_its_own_content():
    from eax.seed import sample_projects as sp
    names = {n for _c, n, *_ in sp.SAMPLES}
    assert {p for p, _r, _g in sr.PLANS} <= names                   # the samples, by the names agreed
    assert set(sr.FILL) == {sr.AGILE, sr.RISK, sr.DATA, sr.DIGITAL}
    src = inspect.getsource(sr)
    assert '"zero": True' in src and "rr.log(conn" in src and 'BuildingBlock="Solution building block"' in src
    assert "filled already" in inspect.getsource(sr.run)            # made once
    assert "sample_release_12" in inspect.getsource(later)


def test_existing_attributes_placed_on_more_types_reach_existing_models():
    assert ("Requirement", "Target") in build.UPGRADE_PLACES and ("Assessment", "Url") in build.UPGRADE_PLACES
    sql = build.model_upgrade_sql()
    assert "(rt.code = 'Requirement' AND ra.code = 'Target')" in sql
