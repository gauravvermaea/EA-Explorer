"""R5.14 and R5.15 (owner, 13 Nov 2026: "the code documented in detail"; "add to R4 a story for human readable code
comments"): every module, class and function of our Python says in plain words what it is for, and the comments can be
read by a person: not a bare decision number, not the name said again, no shorthand left for later."""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
ROOTS = ["services/api/eax", "services/ops", "services/library", "services/views", "eaxcli", "testbench", "tools"]
EXEMPT = {"Meta"}                                  # marshmallow's settings class: the schema around it says what it is
ONLY_A_NUMBER = re.compile(r"^[\s(\[]*(D\d+|R\d+(\.\d+)*)[\s)\].,;:]*$")
LEFT_FOR_LATER = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")


def files():
    for root in ROOTS:
        for p in sorted((REPO / root).rglob("*.py")):
            if "__pycache__" not in p.parts and "tests" not in p.parts and "migrations" not in p.parts:
                yield p


def documented():
    """(where, name, docstring) of every module and every public class, function and method."""
    for p in files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        rel = p.relative_to(REPO).as_posix()
        yield rel, "(module)", ast.get_docstring(tree)

        def walk(node, q="", rel=rel):
            for n in ast.iter_child_nodes(node):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not n.name.startswith("_") and n.name not in EXEMPT:
                        yield f"{rel}:{n.lineno}", q + n.name, ast.get_docstring(n)
                    if isinstance(n, ast.ClassDef):
                        yield from walk(n, q + n.name + ".", rel)
        yield from walk(tree)


ALL = list(documented())


def test_there_is_code_to_check():
    assert len(ALL) > 4000


def test_every_module_class_and_function_says_what_it_is_for():
    missing = [f"{w} {n}" for w, n, d in ALL if not d]
    assert not missing, f"{len(missing)} without a docstring (R5.15):\n  " + "\n  ".join(missing[:50])


def test_the_comments_can_be_read():
    bad = []
    for where, name, doc in ALL:
        text = " ".join((doc or "").split())
        short = name.split(".")[-1].replace("_", " ").lower()
        if len(text.split()) < 2:
            bad.append(f"{where} {name}: too short ({text!r})")
        elif ONLY_A_NUMBER.match(text):
            bad.append(f"{where} {name}: only a decision number; say what it means ({text!r})")
        elif text.rstrip(".").lower() == short:
            bad.append(f"{where} {name}: says its name again")
        elif LEFT_FOR_LATER.search(text):
            bad.append(f"{where} {name}: shorthand left for later ({text[:60]!r})")
    assert not bad, f"{len(bad)} docstrings to write again:\n  " + "\n  ".join(bad[:50])


@pytest.mark.parametrize("doc,ok", [("D123.", False), ("(R5.1)", False), ("Get.", False), ("TODO: explain", False),
                                    ("The model's tags, newest first (D172).", True)])
def test_the_readability_rules_themselves(doc, ok):
    text = " ".join(doc.split())
    fails = len(text.split()) < 2 or bool(ONLY_A_NUMBER.match(text)) or bool(LEFT_FOR_LATER.search(text))
    assert fails is not ok


def test_the_functional_description_and_the_handover_are_there():
    fd = (REPO / "docs/functional-description.md").read_text(encoding="utf-8")
    for area in ("Models", "Projects", "Reports", "Self-test", "Operations", "Security"):
        assert f"## {area}" in fd or f"### {area}" in fd, area
    ho = (REPO / "docs/handover.md").read_text(encoding="utf-8")
    for part in ("What was just done", "In progress", "Next", "Open questions", "The laptop and GitHub", "How the owner works"):
        assert part in ho, part


def test_eax_dev_check_is_in_every_form_and_finds_document_problems(tmp_path):
    import sys
    sys.path.insert(0, str(REPO))
    from eaxcli import dev_cli
    assert dev_cli.documents() == []
    (tmp_path / "docs").mkdir()
    (tmp_path / "eaxcli").mkdir()
    (tmp_path / "docs/decisions.md").write_text("| D1 | a |\n| D3 | b |\n| D3 | c |\n")
    (tmp_path / "eaxcli/help.txt").write_bytes("café".encode())
    found = " ".join(dev_cli.documents(tmp_path))
    assert "D3 recorded more than once" in found and "no D2" in found and "not ASCII" in found and "handover.md is missing" in found
    assert "|dev)" in (REPO / "eax.sh").read_text() and '"estimate", "dev")' in (REPO / "eax.ps1").read_text()
    assert "### dev check" in (REPO / "eaxcli/help.txt").read_text()
